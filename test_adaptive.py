import pytest
from adaptiveStrategy import AdaptiveConcurrencyController
from stats import RequestStats


@pytest.fixture
def controller():
    return AdaptiveConcurrencyController(
        base_concurrency=3,
        min_concurrency=1,
        max_concurrency=5
    )


def test_initial_concurrency(controller):
    assert controller.get_concurrency("http://api.test") == 3


def test_adjust_on_high_error_rate(controller):
    stats = RequestStats(url="http://api.test", window_size=5)
    for _ in range(4):
        stats.record(success=False, latency_ms=100)
    stats.record(success=True, latency_ms=100)
    
    new_conc = controller.adjust("http://api.test", stats)
    assert new_conc == 2  


def test_adjust_on_high_latency(controller):
    stats = RequestStats(url="http://api.test", window_size=3)
    stats.record(success=True, latency_ms=3000) 
    stats.record(success=True, latency_ms=2500)
    stats.record(success=True, latency_ms=2800)
    
    new_conc = controller.adjust("http://api.test", stats)
    assert new_conc == 2


def test_adjust_on_good_performance(controller):
    stats = RequestStats(url="http://api.test", window_size=5)
    for _ in range(5):
        stats.record(success=True, latency_ms=100)  
    
    new_conc = controller.adjust("http://api.test", stats)
    assert new_conc == 4  


def test_concurrency_bounds(controller):
    stats_bad = RequestStats(url="http://api.test", window_size=20)
    for _ in range(20):
        stats_bad.record(success=False, latency_ms=100)

    for _ in range(10):
        controller.adjust("http://api.test", stats_bad)
    
    assert controller.get_concurrency("http://api.test") == 1 
    
    stats_good = RequestStats(url="http://api.test2", window_size=20)
    for _ in range(20):
        stats_good.record(success=True, latency_ms=50)
    
    for _ in range(20):
        controller.adjust("http://api.test2", stats_good)
    
    assert controller.get_concurrency("http://api.test2") == 5  