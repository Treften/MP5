import asyncio
import random
from aiohttp import web
from typing import Callable, Optional


class APIEmulator:
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = None,
        latency_ms: tuple = (50, 150),
        error_rate: float = 0.0, 
        error_codes: list = None
    ):
        self.host = host
        self.port = port or random.randint(8001, 8999)
        self.latency_range = latency_ms
        self.error_rate = error_rate
        self.error_codes = error_codes or [500, 503, 504]
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
    
    async def handler(self, request: web.Request) -> web.Response:
        """Обработчик всех запросов"""
        latency = random.uniform(*self.latency_range) / 1000
        await asyncio.sleep(latency)
        
        if random.random() < self.error_rate:
            code = random.choice(self.error_codes)
            return web.Response(
                status=code,
                text=f"Simulated {code} error",
                content_type="text/plain"
            )
        
        return web.json_response({
            "source": f"{self.host}:{self.port}",
            "path": request.path,
            "data": {"message": "OK", "timestamp": asyncio.get_event_loop().time()}
        })
    
    async def start(self):
        """Запустить эмулятор"""
        self._app = web.Application()
        self._app.router.add_get("/{tail:.*}", self.handler)
        self._app.router.add_post("/{tail:.*}", self.handler)
        
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        print(f"🔌 Emulator started at http://{self.host}:{self.port}")
    
    async def stop(self):
        """Остановить эмулятор"""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def create_scenario_a_emulators() -> list[APIEmulator]:
    return [
        APIEmulator(port=8101, latency_ms=(30, 80), error_rate=0.0),
        APIEmulator(port=8102, latency_ms=(40, 100), error_rate=0.0),
        APIEmulator(port=8103, latency_ms=(20, 70), error_rate=0.0),
    ]


def create_scenario_b_emulators() -> list[APIEmulator]:
    return [
        APIEmulator(port=8201, latency_ms=(30, 80), error_rate=0.0),
        APIEmulator(port=8202, latency_ms=(3000, 5000), error_rate=0.0), 
        APIEmulator(port=8203, latency_ms=(40, 90), error_rate=0.0),
    ]


def create_scenario_c_emulators() -> list[APIEmulator]:
    return [
        APIEmulator(port=8301, latency_ms=(50, 150), error_rate=0.4),  
        APIEmulator(port=8302, latency_ms=(60, 200), error_rate=0.3),  
        APIEmulator(port=8303, latency_ms=(40, 120), error_rate=0.0),  
    ]