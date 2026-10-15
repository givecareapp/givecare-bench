"""Turn finished Inspect logs into the run directory that `bench scan plan` reads."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from inspect_ai.log import EvalLog, EvalSample, read_eval_log

from invisiblebench.api.typesafe import request_cost
from invisiblebench.inspect_task import (
    MAX_REPLY_TOKENS,
    TRANSCRIPT_TEMPERATURE,
    transcript_policy,
)
from invisiblebench.models.config import MODELS_FULL, serving_policy
from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.utils.manifest import generate_manifest, is_git_commit, write_manifest

PROVIDER_PREFIX = "openrouter/"


def _endpoint(log: EvalLog) -> str | None:
    """The OpenRouter provider restriction the log recorded; anything else is refused."""
    provider = log.eval.model_args.get("provider")
    only = (provider or {}).get("only")
    endpoint = only[0] if isinstance(only, list) and len(only) == 1 else None
    if provider != serving_policy({"endpoint": endpoint})["provider"]:
        raise ValueError(
            f"{log.location}: generate with -M 'provider={{\"allow_fallbacks\": true, "
            "\"require_parameters\": true}}' (optionally pinned with \"only\")"
        )
    return endpoint


def _full_commit(commit: str, root: Path) -> str:
    """Inspect logs an abbreviated commit; resolve it to the full id in this checkout."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{commit}^{{commit}}"],
        cwd=root, capture_output=True, text=True,
    )
    full = result.stdout.strip()
    if result.returncode or not is_git_commit(full):
        raise ValueError(f"generation commit {commit} is not in this checkout")
    return full


def _entries(sample: EvalSample) -> list[dict[str, Any]]:
    """The transcript of record is the sample's messages; each reply's call is its model event."""
    events = {
        e.output.message.id: e for e in sample.events if e.event == "model" and e.output.choices
    }
    entries = []
    for message in sample.messages:
        if message.role == "system":
            continue
        meta = dict(message.metadata or {})
        entry = {"turn": meta.pop("turn"), "role": message.role, "content": message.text}
        attempts = meta.pop("empty_response_attempts", None)
        entry.update(meta)
        event = events.get(message.id) if message.role == "assistant" else None
        if event is not None:
            if event.output.stop_reason == "max_tokens":
                entry["truncated"] = True
            if event.output.model:
                entry["resolved_model_id"] = event.output.model
            provider = (event.call.response or {}).get("provider") if event.call else None
            if provider:
                entry["resolved_provider"] = provider
        if attempts:
            entry["empty_response_attempts"] = attempts
        entries.append(entry)
    return entries


def _judge_cost(entries: list[dict[str, Any]]) -> float | None:
    """Cost of Jev branch choices; None when a branch judge's price is unknown."""
    total = 0.0
    for entry in entries:
        for decision in entry.get("branch_decisions", [])[:1]:
            if response := decision.get("judge_response"):
                try:
                    total += request_cost(response["model"], response["usage"]["input_tokens"])
                except (KeyError, TypeError, ValueError):
                    return None
    return total


def _seconds(logs: list[EvalLog]) -> float | None:
    try:
        start = min(datetime.fromisoformat(log.stats.started_at) for log in logs)
        end = max(datetime.fromisoformat(log.stats.completed_at) for log in logs)
    except ValueError:
        return None
    return round((end - start).total_seconds(), 3)


def export_run(log_paths: list[Path], output_dir: Path) -> Path:
    """Write run_manifest.json, transcript_run.json, and transcripts/ from Inspect logs."""
    logs = [read_eval_log(str(path)) for path in log_paths]
    first = logs[0]
    revision = first.eval.revision
    if revision is None:
        raise ValueError("log records no git revision; generate inside the checkout")
    root = get_project_root()
    git_sha = _full_commit(revision.commit, root)
    confidential = bool(first.eval.metadata and first.eval.metadata.get("include_confidential"))
    manifest = generate_manifest(
        root,
        [],
        transcript_policy=None,
        run_id=first.eval.run_id,
        harness="llm",
        mode="raw",
        include_confidential=confidential,
    )
    expected_ids = sorted(map(str, first.eval.dataset.sample_ids or []))
    models, rows, errors, transcripts = [], [], [], {}
    cost_by_model: dict[str, float] = {}
    unknown_cost_samples = 0
    for log in logs:
        meta = log.eval.metadata or {}
        if log.eval.task.rsplit("/", 1)[-1] != "safety_care":
            raise ValueError(f"{log.location}: not a safety_care log")
        if (log.eval.revision and log.eval.revision.commit, log.eval.revision and log.eval.revision.dirty) != (
            revision.commit,
            revision.dirty,
        ):
            raise ValueError("logs were generated at different git revisions")
        if meta.get("scenario_hash") != manifest["scenario_hash"]:
            raise ValueError(f"{log.location}: scenarios changed since generation")
        if sorted(map(str, log.eval.dataset.sample_ids or [])) != expected_ids:
            raise ValueError("logs cover different scenarios")
        config = log.plan.config
        if (config.temperature, config.max_tokens) != (TRANSCRIPT_TEMPERATURE, MAX_REPLY_TOKENS):
            raise ValueError(f"{log.location}: generation settings differ from the policy")
        model_id = log.eval.model.removeprefix(PROVIDER_PREFIX)
        models.append({"id": model_id, "endpoint": _endpoint(log)})
        name = next((m.name for m in MODELS_FULL if m.id == model_id), model_id)
        present = {str(s.id): s for s in log.samples or []}
        for scenario_id in expected_ids:
            sample = present.get(scenario_id)
            row = {
                "model": name,
                "model_id": model_id,
                "scenario": sample.metadata.get("name") if sample else None,
                "scenario_id": scenario_id,
                "category": sample.metadata.get("category") if sample else None,
            }
            if sample is None:
                continue
            judge_cost = None
            try:
                if sample.error or sample.limit:
                    raise ValueError(
                        sample.error.message if sample.error else f"limit: {sample.limit.type}"
                    )
                entries = _entries(sample)
                judge_cost = _judge_cost(entries)
            except (KeyError, ValueError) as exc:
                errors.append({**row, "reason": str(exc)})
                entries = None
            costs = [u.total_cost for u in sample.model_usage.values()]
            if not costs or None in costs or judge_cost is None and entries is not None:
                unknown_cost_samples += 1
            cost_by_model[model_id] = (
                cost_by_model.get(model_id, 0.0) + sum(c for c in costs if c) + (judge_cost or 0.0)
            )
            if entries is not None:
                filename = f"{quote(model_id, safe='')}_{quote(scenario_id, safe='')}.jsonl"
                transcripts[filename] = entries
                rows.append(
                    {
                        **row,
                        "transcript_path": f"transcripts/{filename}",
                        "resolved_model_ids": sorted(
                            {e["resolved_model_id"] for e in entries if "resolved_model_id" in e}
                        ),
                        "resolved_providers": sorted(
                            {e["resolved_provider"] for e in entries if "resolved_provider" in e}
                        ),
                    }
                )
    expected = len(expected_ids) * len(logs)
    missing = expected - len(rows) - len(errors)
    complete = (
        expected > 0
        and len(rows) == expected
        and all(log.status == "success" for log in logs)
    )
    manifest.update(
        git_sha=git_sha,
        git_dirty=revision.dirty,
        run_date=min(log.eval.created for log in logs),
        model_ids=[m["id"] for m in models],
        scenario_ids=expected_ids,
        transcript_policy=transcript_policy(models),
        model_pricing={
            m.id: {"input_per_million": m.cost_per_m_input, "output_per_million": m.cost_per_m_output}
            for m in MODELS_FULL
            if m.id in {model["id"] for model in models}
        },
    )
    known_cost = sum(cost_by_model.values())
    summary = {
        "artifact_type": "transcript_run/v1",
        "run_id": manifest["run_id"],
        "benchmark_version": manifest["benchmark_version"],
        "stage": "transcripts",
        "status": "complete" if complete else "partial",
        "model_ids": manifest["model_ids"],
        "scenario_count": len(expected_ids),
        "expected_transcripts": expected,
        "transcript_count": len(rows),
        "error_count": len(errors),
        "missing_count": missing,
        "abort_reason": None
        if complete
        else next((log.error.message for log in logs if log.error), "incomplete_inspect_log"),
        # Cost is Inspect's priced usage plus Jev branch choices. Unknown cost is
        # never folded in as zero: the total is None until every sample is priced.
        "actual_cost_usd": known_cost if not unknown_cost_samples else None,
        "actual_known_cost_usd": known_cost,
        "actual_cost_by_model_usd": cost_by_model,
        "unknown_calls_with_uncosted_usd": unknown_cost_samples,
        "resolved_model_ids": sorted({i for r in rows for i in r["resolved_model_ids"]}),
        "resolved_providers": sorted({p for r in rows for p in r["resolved_providers"]}),
        "transcripts": rows,
        "errors": errors,
    }
    if (seconds := _seconds(logs)) is not None:
        summary["elapsed_seconds"] = seconds

    write_manifest(manifest, output_dir)
    (output_dir / "transcripts").mkdir(exist_ok=True)
    for filename, entries in transcripts.items():
        with (output_dir / "transcripts" / filename).open("w") as stream:
            for entry in entries:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    (output_dir / "transcript_run.json").write_text(json.dumps(summary, indent=2) + "\n")
    return output_dir
