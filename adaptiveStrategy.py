import asyncio
import time
from typing import Dict

from config import settings
from stats import stats_registry, RequestStats


class AdaptiveConcurrencyController:

    def __init__(
        self,
        base_concurrency: int = None,
        min_concurrency: int = None,
        max_concurrency: int = None
    ):

        self.base = (
            base_concurrency
            or settings.default_max_concurrent
        )

        self.min_conc = (
            min_concurrency
            or settings.adaptive_min_concurrency
        )

        self.max_conc = (
            max_concurrency
            or settings.adaptive_max_concurrency
        )

        self._current: Dict[str, int] = {}

        self._last_adjustment: Dict[str, float] = {}

        self._semaphores: Dict[str, asyncio.Semaphore] = {}

        self.cooldown_seconds = 0.5

    def get_concurrency(self, host: str) -> int:

        if host not in self._current:
            self._current[host] = self.base

        return self._current[host]

    def get_semaphore(
        self,
        host: str,
        concurrency: int
    ) -> asyncio.Semaphore:

        existing = self._semaphores.get(host)

        if existing is None:
            self._semaphores[host] = asyncio.Semaphore(
                concurrency
            )

        return self._semaphores[host]

    def adjust(
        self,
        host: str,
        stats: RequestStats
    ) -> int:

        current = self.get_concurrency(host)

        now = time.time()

        last = self._last_adjustment.get(host, 0)

        #print(host, current,stats.request_count,round(stats.success_rate, 2),round(stats.avg_latency_ms, 1))
        if now - last < self.cooldown_seconds:
            return current

        if stats.request_count  < 3:
            return current
        if stats.success_rate < 0.5:
            new_value = self.min_conc
        elif stats.success_rate < 0.8:

            new_value = max(
                self.min_conc,
                int(current * 0.5)
            )

        elif stats.avg_latency_ms > 2000:

            new_value = max(
                self.min_conc,
                int(current * 0.7)
            )

        elif (
            stats.success_rate > 0.98
            and stats.avg_latency_ms < 300
        ):

            new_value = min(
                self.max_conc,
                current + 1
            )

        else:
            new_value = current

        self._current[host] = new_value

        self._last_adjustment[host] = now

        if new_value != current:

            self._semaphores[host] = asyncio.Semaphore(
                new_value
            )

        return new_value
    def reset(self):
        self._current: Dict[str, int] = {}
    def get_adaptive_stats(self):

        result = {}
        #print(self._current.items())
        for host, concurrency in self._current.items():

            stats = stats_registry.get_or_create(host)

            result[host] = {
                "success_rate": round(
                    stats.success_rate,
                    3
                ),
                "avg_ms": round(
                    stats.avg_latency_ms,
                    2
                ),
                "adjusted_concurrency": concurrency
            }

        return result