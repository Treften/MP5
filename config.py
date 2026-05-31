from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
 
    default_strategy: str = "fixed"
    default_max_concurrent: int = 3
    default_timeout_sec: float = 5.0
    
    adaptive_window_size: int = 20  
    adaptive_error_threshold: float = 0.30  
    adaptive_latency_threshold_ms: float = 2000  
    adaptive_min_concurrency: int = 1
    adaptive_max_concurrency: int = 10
    adaptive_increase_step: int = 1
    adaptive_decrease_step: int = 1

    test_output_dir: str = "report"
    
    class Config:
        env_file = ".env"

settings = Settings()