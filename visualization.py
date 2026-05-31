import json
import csv
from pathlib import Path
from typing import List, Dict
import matplotlib.pyplot as plt
import pandas as pd


def save_results_json(data: Dict, filepath: str):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_results_csv(metrics: List[Dict], filepath: str):
    if not metrics:
        return
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=metrics[0].keys())
        writer.writeheader()
        writer.writerows(metrics)


def plot_strategy_comparison(results: Dict, output_dir: str = "report"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    scenarios = list(results.keys())
    strategies = ["fixed", "timeout_race", "adaptive"]
    
    data = []
    for scenario in scenarios:
        for strategy in strategies:
            if strategy in results[scenario]:
                data.append({
                    "scenario": scenario,
                    "strategy": strategy,
                    "avg_time_ms": results[scenario][strategy]["avg_time_ms"]
                })
    
    df = pd.DataFrame(data)
    
    plt.figure(figsize=(10, 6))
    for scenario in scenarios:
        subset = df[df["scenario"] == scenario]
        plt.bar(
            [f"{s}\n({scenario})" for s in subset["strategy"]],
            subset["avg_time_ms"],
            label=scenario,
            alpha=0.8
        )
    
    plt.ylabel("Среднее время (мс)")
    plt.title("Сравнение стратегий по сценариям")
    plt.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(f"{output_dir}/strategy_comparison.png", dpi=300)
    plt.close()


def plot_adaptive_concurrency(
    all_history: dict,
    output_dir: str = "report"
):

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    scenario_titles = {
        "a": "Стабильный",
        "b": "Медленный",
        "c": "Нестабильный"
    }

    for scenario, history in all_history.items():

        if not history:
            continue

        plt.figure(figsize=(12, 6))

        for host, values in history.items():

            port = host.split(":")[-1]

            plt.plot(
                range(1, len(values) + 1),
                values,
                marker="o",
                linewidth=2,
                label=port
            )

        plt.xlabel("Номер запроса")
        plt.ylabel("Concurrency")
        plt.title(
            f"Адаптивная параллельность — сценарий "
            f"{scenario.upper()} ({scenario_titles.get(scenario, scenario)})"
        )

        plt.xticks(range(1, max(len(v) for v in history.values()) + 1))
        plt.grid(True, alpha=0.3)
        plt.legend(title="Порт")

        plt.tight_layout()

        filename = (
            f"{output_dir}/adaptive_concurrency_{scenario}.png"
        )

        plt.savefig(filename, dpi=300)
        plt.close()

        print(f"{filename}")

def plot_success_failure(results: Dict, output_dir: str = "report"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    data = []
    for scenario, strategies in results.items():
        for strategy, metrics in strategies.items():
            data.append({
                "scenario": scenario,
                "strategy": strategy,
                "successful": metrics["avg_successful"],
                "failed": metrics["avg_failed"]
            })
    
    df = pd.DataFrame(data)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(df))
    
    ax.bar(x, df["successful"], label="Успешные", color="#2ecc71")
    ax.bar(x, df["failed"], bottom=df["successful"], label="Неудачные", color="#e74c3c")
    
    ax.set_xlabel("Сценарий + Стратегия")
    ax.set_ylabel("Количество запросов")
    ax.set_title("Распределение успешных/неудачных запросов")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r['scenario']}\n{r['strategy']}" for _, r in df.iterrows()], rotation=45, ha="right")
    ax.legend()
    plt.tight_layout()
    plt.savefig(f"{output_dir}/success_failure.png", dpi=300)
    plt.close()