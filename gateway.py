import asyncio
import time
import uuid
from collections import defaultdict
from contextlib import nullcontext
from enum import Enum
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientTimeout, ClientError

from config import settings
from stats import stats_registry
from adaptiveStrategy import AdaptiveConcurrencyController


class Strategy(Enum):
    FIXED = "fixed"
    TIMEOUT_RACE = "timeout_race"
    ADAPTIVE = "adaptive"

adaptive_controller = AdaptiveConcurrencyController(
    base_concurrency=settings.default_max_concurrent
)

def resetController():
    adaptive_controller.reset()
async def fetch_single(
    session: aiohttp.ClientSession,
    url: str,
    timeout_sec: float,
    semaphore: Optional[asyncio.Semaphore] = None,
    use_internal_timeout: bool = True
) -> Dict[str, Any]:

    result = {"url": url}
    host = urlparse(url).netloc

    try:
        timeout = (
            ClientTimeout(total=timeout_sec)
            if use_internal_timeout
            else None
        )

        async with semaphore or nullcontext():

            start = time.time()

            async with session.get(url, timeout=timeout) as resp:

                elapsed_ms = (time.time() - start) * 1000

                result.update({
                    "status": resp.status,
                    "elapsed_ms": round(elapsed_ms, 2)
                })

                if resp.status >= 400:

                    result["error"] = resp.reason

                    stats_registry.get_or_create(host).record(
                        success=False,
                        latency_ms=elapsed_ms
                    )

                else:
                    try:
                        result["data"] = await resp.json()
                    except Exception:
                        result["data"] = await resp.text()

                    stats_registry.get_or_create(host).record(
                        success=True,
                        latency_ms=elapsed_ms
                    )

    except asyncio.TimeoutError:

        elapsed_ms = timeout_sec * 1000

        result.update({
            "timeout": True,
            "elapsed_ms": round(elapsed_ms, 2),
            "error": f"Timeout after {timeout_sec}s"
        })

        stats_registry.get_or_create(host).record(
            success=False,
            latency_ms=elapsed_ms
        )

    except ClientError as e:

        result.update({
            "status": 0,
            "error": str(e),
            "elapsed_ms": 0
        })

        stats_registry.get_or_create(host).record(
            success=False,
            latency_ms=0
        )

    return result

async def execute_fixed(
    urls: List[str],
    max_concurrent: int,
    timeout_sec: float
) -> List[Dict[str, Any]]:

    semaphore = asyncio.Semaphore(max_concurrent)

    async with aiohttp.ClientSession() as session:

        tasks = [
            fetch_single(session, url, timeout_sec, semaphore)
            for url in urls
        ]

        return await asyncio.gather(*tasks)

async def execute_timeout_race(
    urls: List[str],
    timeout_sec: float
) -> List[Dict[str, Any]]:

    async with aiohttp.ClientSession() as session:

        tasks = [
            asyncio.wait_for(
                fetch_single(
                    session,
                    url,
                    timeout_sec,
                    None,
                    use_internal_timeout=False
                ),
                timeout=timeout_sec
            )
            for url in urls
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True
        )

        processed = []

        for i, r in enumerate(results):

            if isinstance(r, asyncio.TimeoutError):

                processed.append({
                    "url": urls[i],
                    "timeout": True,
                    "elapsed_ms": timeout_sec * 1000,
                    "error": f"Timeout after {timeout_sec}s"
                })

            elif isinstance(r, Exception):

                processed.append({
                    "url": urls[i],
                    "status": 0,
                    "error": str(r),
                    "elapsed_ms": 0
                })

            else:
                processed.append(r)

        return processed


async def process_host_group(
    session: aiohttp.ClientSession,
    host: str,
    host_urls: List[str],
    timeout_sec: float,
    controller: AdaptiveConcurrencyController
) -> List[Dict[str, Any]]:

    stats = stats_registry.get_or_create(host)

    concurrency = controller.adjust(host, stats)

    semaphore = controller.get_semaphore(host, concurrency)
    tasks = [
        fetch_single(
            session,
            url,
            timeout_sec,
            semaphore
        )
        for url in host_urls
    ]

    return await asyncio.gather(*tasks)


async def execute_adaptive(
    urls: List[str],
    timeout_sec: float,
    controller: AdaptiveConcurrencyController
) -> List[Dict[str, Any]]:

    url_groups: Dict[str, List[str]] = defaultdict(list)

    for url in urls:
        host = urlparse(url).netloc
        url_groups[host].append(url)

    async with aiohttp.ClientSession() as session:

        host_tasks = [
            process_host_group(
                session=session,
                host=host,
                host_urls=host_urls,
                timeout_sec=timeout_sec,
                controller=controller
            )
            for host, host_urls in url_groups.items()
        ]

        grouped_results = await asyncio.gather(*host_tasks)

        results = []

        for group in grouped_results:
            results.extend(group)

        return results


async def aggregate(
    urls: List[str],
    strategy: str = "fixed",
    max_concurrent: Optional[int] = None,
    timeout_sec: Optional[float] = None
) -> Dict[str, Any]:

    max_conc = (
        max_concurrent
        or settings.default_max_concurrent
    )

    timeout = (
        timeout_sec
        or settings.default_timeout_sec
    )

    strat = Strategy(strategy.lower())
    
    request_id = str(uuid.uuid4())

    start_time = time.time()


    if strat == Strategy.FIXED:

        results = await execute_fixed(
            urls,
            max_conc,
            timeout
        )

        concurrent_used = max_conc

    elif strat == Strategy.TIMEOUT_RACE:

        results = await execute_timeout_race(
            urls,
            timeout
        )

        concurrent_used = len(urls)

    elif strat == Strategy.ADAPTIVE:
        
        results = await execute_adaptive(
            urls,
            timeout,
            adaptive_controller
        )

        concurrent_used = "adaptive"

    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    total_time_ms = (
        (time.time() - start_time) * 1000
    )

    successful = sum(
        1
        for r in results
        if isinstance(r, dict)
        and r.get("status") == 200
    )

    response = {
        "request_id": request_id,
        "results": results,
        "summary": {
            "total": len(urls),
            "successful": successful,
            "failed": len(urls) - successful,
            "total_time_ms": round(total_time_ms, 2),
            "strategy_used": strategy,
            "concurrent_used": concurrent_used
        }
    }

    if strat == Strategy.ADAPTIVE:
        #print(adaptive_controller.get_adaptive_stats())
        response["adaptive_stats"] = (
            adaptive_controller.get_adaptive_stats()
        )

    return response