"""Check the configured OpenRouter free models, and optionally compare them on Agent A.

    uv run python scripts/llm_model_check.py              # are the models still listed and free?
    uv run python scripts/llm_model_check.py --evaluate   # Agent A dev queries per candidate

The check reads `GET /api/v1/models` (public, no key is sent) and warns for every model in
config/llm.yaml or .env (LLM_MODEL, LLM_FALLBACK_MODELS, LLM_MODEL_*) that is no longer listed,
no longer free, or lacks structured-output / tool support. Exit code 1 with --strict when a
model configured in .env has a problem.

--evaluate needs OPENROUTER_API_KEY. It runs the Agent A dev queries through each candidate
(responses cached under data/llm_cache/, so reruns are free and reproducible) and prints
validity, attribute F1, hard-constraint accuracy and p50/p95 latency next to the deterministic
parser; results go to artifacts/evaluation/llm_models/<date>.json. Only query text is sent.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import UTC, datetime

import httpx
import yaml

from music_discovery.agents.agent_a_query import QueryAgent
from music_discovery.agents.lexicon_loader import load_lexicon
from music_discovery.agents.llm_query_interpreter import LLMQueryInterpreter
from music_discovery.evaluation import agent_eval
from music_discovery.evaluation.datasets import load_dataset
from music_discovery.infrastructure.llm import OpenRouterLLM, model_statuses
from music_discovery.infrastructure.settings import Settings, get_settings


def configured(settings: Settings) -> list[str]:
    ids = [settings.llm_model, *settings.llm_fallback_models]
    ids += [settings.llm_model_query, settings.llm_model_feedback, settings.llm_model_descriptions]
    return [i for i in ids if i]


def check(settings: Settings, config: dict, strict: bool) -> int:
    response = httpx.get(f"{settings.openrouter_base_url}/models", timeout=30)
    response.raise_for_status()
    catalog = response.json().get("data", [])
    in_env = configured(settings)
    shortlist = [c["id"] for c in config.get("candidates", [])]
    shortlist += [m for models in config.get("tasks", {}).values() for m in models]
    failing_env = 0
    print(f"{len(catalog)} models listed; checking {len(set(in_env + shortlist))}")
    for status in model_statuses(catalog, [*in_env, *shortlist]):
        where = ".env" if status.model_id in in_env else "llm.yaml"
        if status.ok:
            detail = f"{status.strategy}, {status.context_length} ctx"
            print(f"  ok    {status.model_id} ({detail}) [{where}]")
            continue
        print(f"  WARN  {status.model_id}: {status.problem} [{where}]")
        failing_env += where == ".env"
    if not in_env:
        print("no model configured in .env: LLM paths are disabled (deterministic fallbacks)")
    return 1 if strict and failing_env else 0


def evaluate(settings: Settings, config: dict) -> int:
    if settings.openrouter_api_key is None:
        print("OPENROUTER_API_KEY is not set: skipping the model comparison", file=sys.stderr)
        return 2
    dataset = load_dataset(settings.evaluation_dir)
    assert dataset.split is not None
    queries = [dataset.query(q) for q in dataset.split.dev]
    lexicon = load_lexicon()
    results: dict[str, dict] = {}
    baseline = agent_eval.agent_a_metrics(
        agent_eval.evaluate_agent_a(queries, QueryAgent(lexicon)), llm_enabled=False
    )
    results["deterministic"] = {"metrics": baseline}
    for candidate in config.get("candidates", []):
        model = candidate["id"]
        llm = OpenRouterLLM(
            api_key=settings.openrouter_api_key,
            models=[model],
            base_url=settings.openrouter_base_url,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            app_title=settings.openrouter_app_title,
            cache_dir=settings.llm_cache_dir,
        )
        agent = QueryAgent(lexicon, LLMQueryInterpreter(llm, lexicon))
        latencies: list[float] = []
        rows = []
        for q in queries:
            started = time.perf_counter()
            rows += agent_eval.evaluate_agent_a([q], agent)
            latencies.append((time.perf_counter() - started) * 1000)
        llm.close()
        metrics = agent_eval.agent_a_metrics(rows, llm_enabled=True)
        ordered = sorted(latencies)
        results[model] = {
            "metrics": metrics,
            "latency_ms": {
                "p50": statistics.median(ordered),
                "p95": ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))],
            },
            "fallback_reasons": [r.llm_fallback_reason for r in rows if r.llm_fallback_reason],
        }
    print(f"{'model':<45} {'accepted':>8} {'F1':>6} {'hard':>6} {'p50 ms':>8} {'p95 ms':>8}")
    for name, r in results.items():
        m, lat = r["metrics"], r.get("latency_ms", {})
        accepted = m["llm_acceptance_rate"]
        print(
            f"{name:<45} {'' if accepted is None else f'{accepted:.2f}':>8} "
            f"{m['micro']['f1'] or 0:>6.3f} {m['hard_constraint_accuracy'] or 0:>6.3f} "
            f"{lat.get('p50', 0):>8.0f} {lat.get('p95', 0):>8.0f}"
        )
    out = settings.evaluation_artifacts_dir / "llm_models"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    payload = {"date": stamp, "prompt_version": "query-v1", "split": "dev", "results": results}
    (out / f"{stamp}.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"written: {out / f'{stamp}.json'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    config = yaml.safe_load((settings.project_root / "config" / "llm.yaml").read_text())
    status = check(settings, config, args.strict)
    if args.evaluate:
        status = max(status, evaluate(settings, config))
    return status


if __name__ == "__main__":
    sys.exit(main())
