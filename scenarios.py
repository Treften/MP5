from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import asyncio
from gateway import aggregate
import time
from stats import stats_registry

@dataclass
class TestMetrics:
    total_time_ms: float
    successful: int
    failed: int
    timeouts: int
    adaptive_concurrency_changes: List[int] = None


async def run_single_test(
    urls: List[str],
    strategy: str,
    max_concurrent: int = 3,
    timeout_sec: float = 5.0
) -> TestMetrics:

    
    start = time.monotonic()
    result = await aggregate(
        urls=urls,
        strategy=strategy,
        max_concurrent=max_concurrent,
        timeout_sec=timeout_sec
    )
    elapsed = (time.monotonic() - start) * 1000
    
    timeouts = sum(1 for r in result["results"] if r.get("timeout"))
    
    return TestMetrics(
        total_time_ms=elapsed,
        successful=result["summary"]["successful"],
        failed=result["summary"]["failed"],
        timeouts=timeouts,
        adaptive_concurrency_changes=(
            [s["adjusted_concurrency"] for s in result.get("adaptive_stats", {}).values()]
            if strategy == "adaptive" else []
        )
    )


async def run_scenario(
    urls: List[str],  
    strategy: str,
    repeats: int = 10
) -> dict:
    
    metrics_list = []
    concurrency_history = {} 
    stats_registry.clear() 
        
    for i in range(repeats):


        start = time.monotonic()
        result = await aggregate(
            urls=urls, 
            strategy=strategy,
            max_concurrent=3,
            timeout_sec=5.0
        )
        elapsed = (time.monotonic() - start) * 1000
        
        timeouts = sum(1 for r in result["results"] if r.get("timeout"))
        
        metrics_list.append({
            "time_ms": elapsed,
            "successful": result["summary"]["successful"],
            "failed": result["summary"]["failed"],
            "timeouts": timeouts
        })
        
        if strategy == "adaptive" and "adaptive_stats" in result:
            #print(result["adaptive_stats"].items())
            for host, host_stats in result["adaptive_stats"].items():
                if host not in concurrency_history:
                    concurrency_history[host] = []
                concurrency_history[host].append(host_stats.get("adjusted_concurrency", 3))
        
        await asyncio.sleep(0.05) 
    
    
    return {
        "strategy": strategy,
        "avg_time_ms": sum(m["time_ms"] for m in metrics_list) / len(metrics_list),
        "avg_successful": sum(m["successful"] for m in metrics_list) / len(metrics_list),
        "avg_failed": sum(m["failed"] for m in metrics_list) / len(metrics_list),
        "total_timeouts": sum(m["timeouts"] for m in metrics_list),
        "concurrency_history": concurrency_history
    }