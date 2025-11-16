"""Evaluation script for the scoring agent."""

import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx
from rich.console import Console
from rich.table import Table
from rich.progress import track

console = Console()

API_BASE = "http://localhost:8000"


async def load_test_dataset():
    """Load test dataset."""
    dataset_path = Path("tests/test_dataset.json")
    with open(dataset_path) as f:
        return json.load(f)


async def score_message(client: httpx.AsyncClient, message: str) -> dict:
    """Score a single message."""
    try:
        response = await client.post(
            f"{API_BASE}/score",
            json={"message": message},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


async def evaluate_category(client: httpx.AsyncClient, category_name: str, messages: list) -> dict:
    """Evaluate a category of messages."""
    console.print(f"\n[bold cyan]Evaluating {category_name}...[/bold cyan]")

    results = []
    latencies = []
    tokens = []

    for msg_data in track(messages, description=f"Testing {category_name}"):
        start = time.time()
        result = await score_message(client, msg_data["message"])
        latency = (time.time() - start) * 1000

        if "error" not in result:
            latencies.append(latency)
            tokens.append(result.get("tokens_used", 0))

            # Check accuracy
            expected = msg_data.get("expected_score")
            actual = result.get("score")

            if expected is not None:
                error = abs(actual - expected)
                results.append(
                    {
                        "message": msg_data["message"][:50] + "...",
                        "expected": expected,
                        "actual": actual,
                        "error": error,
                        "confidence": result.get("confidence", 0),
                        "action": result.get("recommended_action", ""),
                        "latency_ms": int(latency),
                        "tokens": result.get("tokens_used", 0),
                        "injection_detected": result.get("injection_detected", False),
                    }
                )

    return {
        "results": results,
        "latencies": latencies,
        "tokens": tokens,
    }


async def evaluate_attacks(client: httpx.AsyncClient, attacks: list) -> dict:
    """Evaluate attack scenarios."""
    console.print("\n[bold red]Evaluating Attack Scenarios...[/bold red]")

    results = []

    for attack in track(attacks, description="Testing attacks"):
        result = await score_message(client, attack["message"])

        if "error" not in result:
            results.append(
                {
                    "category": attack["category"],
                    "message": attack["message"][:50] + "...",
                    "injection_detected": result.get("injection_detected", False),
                    "score": result.get("score"),
                    "expected_behavior": attack["expected_behavior"],
                }
            )

    return results


def print_category_results(category_name: str, data: dict):
    """Print results for a category."""
    results = data["results"]
    latencies = data["latencies"]
    tokens_list = data["tokens"]

    if not results:
        console.print(f"[yellow]No results for {category_name}[/yellow]")
        return

    # Create table
    table = Table(title=f"{category_name} Results")
    table.add_column("Message", style="cyan", no_wrap=False, width=40)
    table.add_column("Expected", justify="center")
    table.add_column("Actual", justify="center")
    table.add_column("Error", justify="center")
    table.add_column("Confidence", justify="center")
    table.add_column("Latency", justify="right")

    for r in results:
        error_color = "green" if r["error"] <= 1 else "yellow" if r["error"] <= 2 else "red"
        table.add_row(
            r["message"],
            str(r["expected"]),
            str(r["actual"]),
            f"[{error_color}]{r['error']}[/{error_color}]",
            f"{r['confidence']:.2f}",
            f"{r['latency_ms']}ms",
        )

    console.print(table)

    # Print statistics
    errors = [r["error"] for r in results]
    within_1 = sum(1 for e in errors if e <= 1)
    within_2 = sum(1 for e in errors if e <= 2)

    console.print(f"\n[bold]Statistics:[/bold]")
    console.print(f"  Accuracy (±1): {within_1}/{len(results)} ({within_1/len(results)*100:.1f}%)")
    console.print(f"  Accuracy (±2): {within_2}/{len(results)} ({within_2/len(results)*100:.1f}%)")
    console.print(f"  Mean Error: {statistics.mean(errors):.2f}")

    if latencies:
        console.print(f"\n[bold]Performance:[/bold]")
        console.print(f"  p50 Latency: {statistics.median(latencies):.0f}ms")
        console.print(f"  p95 Latency: {sorted(latencies)[int(len(latencies)*0.95)]:.0f}ms")
        console.print(f"  Mean Tokens: {statistics.mean(tokens_list):.0f}")


def print_attack_results(results: list):
    """Print attack evaluation results."""
    table = Table(title="Attack Scenarios")
    table.add_column("Category", style="cyan")
    table.add_column("Message", no_wrap=False, width=40)
    table.add_column("Detected", justify="center")
    table.add_column("Score", justify="center")

    for r in results:
        detected_color = "green" if r["injection_detected"] else "red"
        table.add_row(
            r["category"],
            r["message"],
            f"[{detected_color}]{'Yes' if r['injection_detected'] else 'No'}[/{detected_color}]",
            str(r["score"]),
        )

    console.print(table)

    # Statistics
    detected = sum(1 for r in results if r["injection_detected"])
    console.print(f"\n[bold]Detection Rate:[/bold] {detected}/{len(results)} ({detected/len(results)*100:.1f}%)")


async def main():
    """Run evaluation."""
    console.print("[bold green]Fertility Support Agent Evaluation[/bold green]")
    console.print("=" * 60)

    # Check server health
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE}/health", timeout=5.0)
            health = response.json()
            console.print(f"\n[bold]Server Status:[/bold] {health['status']}")
            console.print(f"[bold]Bedrock:[/bold] {'✓' if health['bedrock_available'] else '✗'}")
    except Exception as e:
        console.print(f"[red]Error: Server not available at {API_BASE}[/red]")
        console.print(f"[red]Please start the server with: uv run uvicorn main:app[/red]")
        return

    # Load dataset
    dataset = await load_test_dataset()

    # Evaluate each category
    async with httpx.AsyncClient() as client:
        all_results = {}

        # Test normal categories
        for category in ["crisis_messages", "high_distress", "moderate_concern", "low_concern", "out_of_domain"]:
            if category in dataset:
                results = await evaluate_category(client, category, dataset[category])
                all_results[category] = results
                print_category_results(category, results)

        # Test attacks
        if "attack_scenarios" in dataset:
            attack_results = await evaluate_attacks(client, dataset["attack_scenarios"])
            print_attack_results(attack_results)

    # Overall summary
    console.print("\n" + "=" * 60)
    console.print("[bold green]Evaluation Complete![/bold green]")

    # Calculate overall metrics
    all_latencies = []
    all_tokens = []
    all_errors = []

    for category, data in all_results.items():
        all_latencies.extend(data["latencies"])
        all_tokens.extend(data["tokens"])
        for r in data["results"]:
            all_errors.append(r["error"])

    if all_latencies:
        console.print(f"\n[bold]Overall Performance:[/bold]")
        console.print(f"  Total Tests: {len(all_errors)}")
        console.print(f"  Mean Latency: {statistics.mean(all_latencies):.0f}ms")
        console.print(f"  p95 Latency: {sorted(all_latencies)[int(len(all_latencies)*0.95)]:.0f}ms")
        console.print(f"  Mean Tokens: {statistics.mean(all_tokens):.0f}")
        console.print(f"  Mean Error: {statistics.mean(all_errors):.2f}")

        within_1 = sum(1 for e in all_errors if e <= 1)
        console.print(f"  Accuracy (±1): {within_1}/{len(all_errors)} ({within_1/len(all_errors)*100:.1f}%)")

        # Cost estimation
        total_tokens = sum(all_tokens)
        cost = (total_tokens / 1_000_000) * 9  # Rough estimate
        console.print(f"  Estimated Cost: ${cost:.4f}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Evaluation interrupted[/yellow]")
