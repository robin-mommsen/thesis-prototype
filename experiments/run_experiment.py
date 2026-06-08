#!/usr/bin/env python3
import json
import httpx
import time
import argparse
import random
from datetime import datetime
from pathlib import Path
from collections import Counter

RESULTS_DIR = Path(__file__).parent / "results"
MAX_ATTEMPTS = 10
RUNS_PER_INPUT = 1


def run_single(client: httpx.Client, base_url: str, text: str, mode: str) -> dict:
    start = time.time()
    try:
        response = client.post(
            f"{base_url}/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": text}],
                "model": mode,
                "stream": False,
                "user": "experiment-runner",
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return {
            "success": True,
            "response": content,
            "duration_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "duration_ms": int((time.time() - start) * 1000),
        }


def run_until_success(
        client: httpx.Client,
        base_url: str,
        text: str,
        mode: str,
        max_attempts: int,
        retry_delay: float,
) -> dict:
    attempt = 1
    last_result = None

    while max_attempts == 0 or attempt <= max_attempts:
        result = run_single(client, base_url, text, mode)
        result["attempt"] = attempt
        last_result = result

        if result["success"]:
            return result

        print(f"Attempt {attempt} failed: {result.get('error', '')}")
        attempt += 1
        time.sleep(retry_delay)

    raise RuntimeError(
        f"{mode} failed after {max_attempts} attempts. "
        f"Last error: {last_result.get('error', '')}"
    )


def print_separator():
    print("-" * 70)


def main():
    parser = argparse.ArgumentParser(description="RAG vs. Baseline Experiment Runner")
    parser.add_argument("--url", default="http://localhost:8080", help="Base API URL")
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=MAX_ATTEMPTS
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.0,
        help="Pause in seconds between retries",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for randomized order RAG/Baseline",
    )
    args = parser.parse_args()

    random.seed(args.seed)

    inputs_path = Path(__file__).parent / "test_inputs.json"
    if not inputs_path.exists():
        print(f"Error: {inputs_path} not found")
        return

    with open(inputs_path, encoding="utf-8") as f:
        test_data = json.load(f)

    inputs = test_data["inputs"]
    total = len(inputs)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    RESULTS_DIR.mkdir(exist_ok=True)
    results_path = RESULTS_DIR / f"experiment_{timestamp}.json"

    print("=" * 70)
    print("  RAG vs. Baseline Experiment")
    print(f"  API:        {args.url}")
    print(f"  Inputs:     {total}")
    print(f"  Runs/Input: {RUNS_PER_INPUT}")
    print(f"  Attempts:   {'unlimited' if args.max_attempts == 0 else args.max_attempts}")
    print(f"  Seed:       {args.seed}")
    print(f"  Output:     {results_path}")
    print("=" * 70)
    print()

    results = []
    retry_count = 0

    with httpx.Client() as client:
        try:
            client.get(f"{args.url}/factsheets", timeout=5.0)
        except Exception:
            print(f"Error: server at {args.url} not reachable")
            print("Make sure the server is running: docker-compose up")
            return

        for i, item in enumerate(inputs, 1):
            input_type = item["type"].upper()
            input_text = item["text"]

            print(f"[{i:2}/{total}] [{input_type:8}] {input_text}")
            print_separator()

            rag_runs = []
            baseline_runs = []

            modes = [
                ("rag", "RAG", rag_runs),
                ("no-rag", "Baseline", baseline_runs),
            ]
            random.shuffle(modes)

            execution_order = []

            print("  Run 1/1")

            for mode, label, target_list in modes:
                execution_order.append(mode)

                print(f"    {label}:")
                result = run_until_success(
                    client,
                    args.url,
                    input_text,
                    mode,
                    args.max_attempts,
                    args.retry_delay,
                )

                retry_count += result["attempt"] - 1

                print(f"OK attempt={result['attempt']} duration={result['duration_ms']}ms")
                for line in result["response"].splitlines():
                    print(f"      {line}")

                target_list.append(result)
                time.sleep(0.5)

            print()

            results.append({
                "id": item["id"],
                "type": item["type"],
                "input": input_text,
                "execution_order": execution_order,
                "rag_runs": rag_runs,
                "baseline_runs": baseline_runs,
            })

    type_counts = Counter(r["type"] for r in results)

    output = {
        "experiment_timestamp": timestamp,
        "api_url": args.url,
        "runs_per_input": RUNS_PER_INPUT,
        "order_randomized": True,
        "random_seed": args.seed,
        "max_attempts_per_request": args.max_attempts,
        "total_inputs": total,
        "valid_responses": total * 2,
        "retry_count": retry_count,
        "type_distribution": dict(type_counts),
        "results": results,
    }

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("=" * 70)
    print(f"  Done: {total} inputs")
    print(f"  Valid responses: {total * 2}/{total * 2}")
    print(f"  Retries: {retry_count}")
    print()
    print("  Inputs after type:")
    for t, c in type_counts.items():
        print(f"    {t}: {c}")
    print()
    print(f"  Results saved: {results_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
