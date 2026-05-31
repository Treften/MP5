import asyncio
import sys
from pathlib import Path
from stats import stats_registry
import typer
import uvicorn
from fastapi import FastAPI
import time
from endpoints import router as api_router
from config import settings
from emulators import (
    create_scenario_a_emulators,
    create_scenario_b_emulators,
    create_scenario_c_emulators
)
from gateway import resetController
from scenarios import run_scenario
from visualization import (
    save_results_json,
    plot_strategy_comparison,
    plot_adaptive_concurrency,
    plot_success_failure
)

app = FastAPI(
    title="Async Gateway",
    description="Агрегатор данных из нескольких внешних API",
    version="1.0.0"
)
app.include_router(api_router, prefix="/api/v1")

cli = typer.Typer(no_args_is_help=True, name="gateway")


@cli.command()
def serve(
    host: str = typer.Option(settings.host, "--host"),
    port: int = typer.Option(settings.port, "--port"),
    reload: bool = typer.Option(settings.reload, "--reload/--no-reload")
):
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


@cli.command()
def test(
    scenario: str = typer.Option(
        "all", 
        "--scenario", 
        case_sensitive=False,
        help="Сценарий: a, b, c или all"
    ),
    repeats: int = typer.Option(10, "--repeats", min=1, max=100),
    output: str = typer.Option(settings.test_output_dir, "--output")
):
    
    scenarios_map = {
        "a": ("Стабильный", create_scenario_a_emulators),
        "b": ("Медленный", create_scenario_b_emulators),
        "c": ("Нестабильный", create_scenario_c_emulators),
    }
    
    strategies = ["fixed", "timeout_race", "adaptive"]
    results = {}
    
    async def run_tests():
        nonlocal results
        adaptive_histories = {}
        targets = []
        if scenario == "all":
            targets = list(scenarios_map.items())
        elif scenario.lower() in scenarios_map:
            targets = [(scenario.upper(), scenarios_map[scenario.lower()])]
        else:
            typer.echo(f"Unknown scenario: {scenario}")
            sys.exit(1)
        
        for scen_name, (scen_desc, emulator_factory) in targets:
            typer.echo(f"\nСценарий {scen_name}: {scen_desc}")
            results[scen_name] = {}
            
            emulators = emulator_factory() 
            for emu in emulators:
                await emu.start()
            
            try:
                urls = [f"{emu.base_url}/data" for emu in emulators]
                
                for strategy in strategies:
                    if strategy == "adaptive":
                        resetController()
                    typer.echo(f" Стратегия: {strategy}...")
                    stats_registry.clear()
                    metrics = await run_scenario(urls, strategy, repeats)
                    results[scen_name][strategy] = metrics
                    if strategy == "adaptive":
                        adaptive_histories[scen_name] = metrics["concurrency_history"]
                    typer.echo(f" Среднее время: {metrics['avg_time_ms']:.0f}мс")
                    typer.echo(metrics['avg_successful'])
                    typer.echo(metrics['avg_failed'])
                    typer.echo(metrics['total_timeouts'])
                    typer.echo(metrics['concurrency_history'])
            
            finally:
                for emu in emulators:
                    await emu.stop()
                
        Path(output).mkdir(parents=True, exist_ok=True)
        
        save_results_json(results, f"{output}/results.json")
        typer.echo(f"\n Результаты сохранены в {output}/results.json")
        plot_strategy_comparison(results, output)
        plot_success_failure(results, output)
        #typer.echo(results)
        if "c" in scenario.lower() or scenario == "all":
            if "c" in results and "adaptive" in results["c"]:
                history = results["c"]["adaptive"]["concurrency_history"]
                #typer.echo(adaptive_histories)
                plot_adaptive_concurrency(adaptive_histories, output)
        
        typer.echo(f"Графики сохранены в {output}/")
    
    asyncio.run(run_tests())

@cli.command()
def clear_stats():
    stats_registry.clear()
    typer.echo("Статистика очищена")


def create_app():
    return app


if __name__ == "__main__":
    cli()