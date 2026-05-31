import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional
import threading

@dataclass
class RequestStats:
    url: str
    window_size: int = 20
    
    _successes: Deque[bool] = field(default_factory=lambda: deque(maxlen=20))
    _latencies: Deque[float] = field(default_factory=lambda: deque(maxlen=20))
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    
    def record(self, success: bool, latency_ms: float):
        with self._lock:
            self._successes.append(success)
            self._latencies.append(latency_ms)
    
    @property
    def success_rate(self) -> float:
        if not self._successes:
            return 1.0
        return sum(self._successes) / len(self._successes)
    
    @property
    def avg_latency_ms(self) -> float:
        if not self._latencies:
            return 0.0
        return sum(self._latencies) / len(self._latencies)
    
    @property
    def request_count(self) -> int:
        return len(self._successes)


class StatsRegistry:
    
    def __init__(self, window_size: int = 20):
        self._registry: dict[str, RequestStats] = {}
        self._window_size = window_size
        self._lock = threading.Lock()
    
    def get_or_create(self, url: str) -> RequestStats:
        with self._lock:
            if url not in self._registry:
                self._registry[url] = RequestStats(
                    url=url, 
                    window_size=self._window_size
                )
            return self._registry[url]
    
    def get_all_stats(self) -> dict[str, dict]:
        result = {}
        with self._lock:
            for url, stats in self._registry.items():
                result[url] = {
                    "success_rate": round(stats.success_rate, 3),
                    "avg_ms": round(stats.avg_latency_ms, 2),
                    "request_count": stats.request_count
                }
        return result
    
    def clear(self):
        with self._lock:
            self._registry.clear()

stats_registry = StatsRegistry()