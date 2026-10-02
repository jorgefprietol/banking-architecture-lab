"""Seeded concurrent synthetic transfers; verify exact balances and idempotent receipts."""
import argparse
import concurrent.futures
import hashlib
import json
import math
from pathlib import Path
import random
import time
import uuid
ROOT = Path(__file__).resolve().parents[1]

def workload(seed, count, pairs):
    rng = random.Random(seed)
    operations = [(i, rng.randrange(pairs), rng.randint(1, 100)) for i in range(count)]
    operations += [item for item in operations if item[0] % 10 == 0]
    rng.shuffle(operations)
    return operations

def percentile(values, percentile):
    return sorted(values)[max(0, math.ceil(len(values)*percentile)-1)]

def run(args):
    from integration_test import TARGETS, request, token_for, subject, wait_for
    operations = workload(args.seed, args.iterations, args.pairs)
    fingerprint = hashlib.sha256(json.dumps(operations, separators=(",", ":")).encode()).hexdigest()
    run_id = uuid.uuid4()
    reports = []
    for language, base in TARGETS:
        wait_for(lambda: request(base, "GET", "/health/ready")[0] == 200, timeout=600)
        token = token_for("alice"); owner = subject(token)
        namespace = uuid.uuid5(run_id, language)
        identity = lambda value: str(uuid.uuid5(namespace, value))
        opening = args.iterations * 100
        accounts = [(identity(f"source-{i}"), identity(f"destination-{i}")) for i in range(args.pairs)]
        for source, destination in accounts:
            for account, balance in ((source, opening), (destination, 0)):
                status, _, _ = request(base, "POST", "/api/accounts", token, {"id": account, "ownerId": owner, "openingMinor": balance, "currency": "USD"})
                if status != 201: raise AssertionError(f"{language}: fixture creation HTTP {status}")
        def transfer(item):
            index, pair, amount = item
            source, destination = accounts[pair]
            status, receipt, duration = request(base, "POST", "/api/transfers", token,
                {"sourceId": source, "destinationId": destination, "amountMinor": amount, "currency": "USD"}, identity(f"transfer-{index}"))
            if status != 201: raise AssertionError(f"{language}: transfer {index} HTTP {status}")
            return index, receipt, duration
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            results = list(pool.map(transfer, operations))
        duration = time.perf_counter() - start
        receipts = {}
        for index, receipt, _ in results:
            if index in receipts and receipts[index] != receipt: raise AssertionError("Idempotent retry changed its receipt")
            receipts[index] = receipt
        if len({value["id"] for value in receipts.values()}) != args.iterations: raise AssertionError("Unexpected distinct receipt count")
        expected = [0] * args.pairs
        unique = {index: (pair, amount) for index, pair, amount in operations}
        for pair, amount in unique.values(): expected[pair] += amount
        for pair, (source, destination) in enumerate(accounts):
            for account, expected_balance in ((source, opening-expected[pair]), (destination, expected[pair])):
                status, value, _ = request(base, "GET", "/api/accounts/" + account, token)
                if status != 200 or value["balanceMinor"] != expected_balance: raise AssertionError("Load changed the expected ledger balance")
        latencies = [value[2]*1000 for value in results]
        report = {"language": language, "requests": len(operations), "uniqueTransfers": args.iterations,
            "durationSeconds": round(duration, 3), "requestsPerSecond": round(len(results)/duration, 3),
            "p50Ms": round(percentile(latencies, .5), 3), "p95Ms": round(percentile(latencies, .95), 3),
            "p99Ms": round(percentile(latencies, .99), 3), "balancesVerified": True, "idempotencyVerified": True}
        reports.append(report); print(json.dumps(report))
        if args.max_p95_ms and report["p95Ms"] > args.max_p95_ms: raise AssertionError(f"{language}: exceeded explicit p95 budget")
    directory = ROOT / "artifacts" / "load" / str(run_id)
    directory.mkdir(parents=True)
    summary = {"runId": str(run_id), "seed": args.seed, "iterations": args.iterations, "pairs": args.pairs,
        "concurrency": args.concurrency, "workloadSha256": fingerprint, "results": reports}
    (directory / "report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--pairs", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--max-p95-ms", type=float, default=0, help="Optional explicit budget; omitted on shared machines")
    args = parser.parse_args()
    if not (1 <= args.iterations <= 100000 and 1 <= args.pairs <= 100 and 1 <= args.concurrency <= 128): parser.error("Invalid workload bounds")
    run(args)
