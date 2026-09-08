"""Plan and record one full-conversation LLM decision for every criterion."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from invisiblebench.api.client import _MODEL_PRICING, maximum_reasonable_cost_ceiling
from invisiblebench.evaluation.check_registry import check_definition_hashes, check_prompt_hashes
from invisiblebench.evaluation.mode_engine import ModeEngine, ModeEngineOutput
from invisiblebench.evaluation.verifiers.llm_verifier import (
    CONTEXT_POLICY,
    JUDGE_MAX_TOKENS,
    JUDGE_TEMPERATURE,
    _format_transcript_for_prompt,
    prompt_for_check,
)
from invisiblebench.utils.benchmark_inventory import get_benchmark_version
from invisiblebench.utils.io import load_jsonl
from invisiblebench.utils.manifest import scenario_corpus_hash
from invisiblebench.version import SCANNED_ROW_CONTRACT_VERSION

logger = logging.getLogger("safety_care_scan")
REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_PLAN_SCHEMA = "invisiblebench-scan-plan/v3"
MODEL_PRICING = _MODEL_PRICING

def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _valid_sha256_map(value: object) -> bool:
    return bool(
        isinstance(value, dict)
        and value
        and all(_is_sha256(item) for item in value.values())
    )


def attach_scan_provenance(
    scan_plan: dict[str, Any],
    *,
    run_dirs: list[Path],
    transcript_pairs: list[dict[str, Any]],
    selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach exact, private-text-free comparability metadata to a scan plan."""
    source_runs: list[dict[str, Any]] = []
    behavior_contracts: list[dict[str, Any]] = []
    source_artifacts: dict[
        Path,
        tuple[dict[str, Any] | None, dict[str, Any] | None],
    ] = {}
    provenance_complete = True
    corpus_hash = scenario_corpus_hash(REPO_ROOT)
    scoring_config_hash = _sha256_file(
        REPO_ROOT / "benchmark" / "configs" / "scoring.yaml"
    )

    resolved_run_dirs = sorted({path.resolve() for path in run_dirs}, key=str)
    for run_dir in resolved_run_dirs:
        manifest_path = run_dir / "run_manifest.json"
        summary_path = run_dir / "transcript_run.json"
        manifest = _read_json_object(manifest_path)
        summary = _read_json_object(summary_path)
        source_artifacts[run_dir] = (manifest, summary)
        summary_transcripts = summary.get("transcripts") if summary else None
        summary_scenario_ids = {
            str(item.get("scenario_id") or "")
            for item in summary_transcripts or []
            if isinstance(item, dict) and item.get("scenario_id")
        }
        source_complete = bool(
            manifest
            and manifest.get("schema") == "invisiblebench-run-manifest/v2"
            and manifest.get("git_dirty") is False
            and manifest.get("git_sha")
            and manifest.get("benchmark_version") == get_benchmark_version(REPO_ROOT)
            and manifest.get("scenario_hash") == corpus_hash
            and manifest.get("scenario_ids")
            and manifest.get("scoring_config_hash") == scoring_config_hash
            and _valid_sha256_map(manifest.get("check_definition_hashes"))
            and manifest.get("transcript_policy")
            and manifest.get("model_ids")
            and manifest.get("harness")
            and manifest.get("mode")
            and summary
            and summary.get("artifact_type") == "transcript_run/v1"
            and summary.get("run_id") == manifest.get("run_id")
            and summary.get("status") == "complete"
            and summary.get("error_count") == 0
            and summary.get("missing_count") == 0
            and summary.get("transcript_count") == summary.get("expected_transcripts")
            and isinstance(summary.get("resolved_model_ids"), list)
            and isinstance(summary.get("resolved_providers"), list)
            and isinstance(summary_transcripts, list)
            and len(summary_transcripts) == summary.get("transcript_count")
            and summary_scenario_ids == set(manifest.get("scenario_ids") or [])
            and sorted(summary.get("model_ids") or [])
            == sorted(manifest.get("model_ids") or [])
        )
        provenance_complete = provenance_complete and source_complete
        source = {
            "artifact_id": run_dir.name,
            "run_manifest_sha256": _sha256_file(manifest_path)
            if manifest_path.is_file()
            else None,
            "transcript_run_sha256": _sha256_file(summary_path)
            if summary_path.is_file()
            else None,
            "schema": manifest.get("schema") if manifest else None,
            "run_id": manifest.get("run_id") if manifest else None,
            "git_sha": manifest.get("git_sha") if manifest else None,
            "git_dirty": manifest.get("git_dirty") if manifest else None,
            "complete": source_complete,
        }
        source_runs.append(source)
        if manifest:
            behavior_contracts.append(
                {
                    "benchmark_version": manifest.get("benchmark_version"),
                    "git_sha": manifest.get("git_sha"),
                    "scenario_hash": manifest.get("scenario_hash"),
                    "scoring_config_hash": manifest.get("scoring_config_hash"),
                    "check_definition_hashes": manifest.get("check_definition_hashes"),
                    "harness": manifest.get("harness"),
                    "mode": manifest.get("mode"),
                    "transcript_policy": manifest.get("transcript_policy"),
                }
            )

    transcript_hashes: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for pair in transcript_pairs:
        model_id = str(pair.get("model_id") or "")
        scenario_id = str(pair.get("scenario_id") or "")
        path = Path(str(pair.get("transcript_path") or ""))
        key = (model_id, scenario_id)
        resolved_path = path.resolve()
        source_run = next(
            (
                run_dir
                for run_dir in resolved_run_dirs
                if resolved_path.is_relative_to(run_dir / "transcripts")
            ),
            None,
        )
        if (
            not model_id
            or not scenario_id
            or key in seen_pairs
            or not path.is_file()
            or source_run is None
        ):
            provenance_complete = False
            continue
        manifest, summary = source_artifacts[source_run]
        summary_paths: dict[tuple[str, str], set[Path]] = {}
        for item in (summary or {}).get("transcripts") or []:
            if not isinstance(item, dict):
                continue
            item_path = Path(str(item.get("transcript_path") or ""))
            if not item_path.is_absolute():
                item_path = source_run / item_path
            item_key = (
                str(item.get("model_id") or ""),
                str(item.get("scenario_id") or ""),
            )
            summary_paths.setdefault(item_key, set()).add(item_path.resolve())
        if (
            not manifest
            or model_id not in set(manifest.get("model_ids") or [])
            or scenario_id not in set(manifest.get("scenario_ids") or [])
            or resolved_path not in summary_paths.get(key, set())
        ):
            provenance_complete = False
            continue
        seen_pairs.add(key)
        transcript_hashes.append(
            {
                "model_id": model_id,
                "scenario_id": scenario_id,
                "sha256": _sha256_file(path),
            }
        )

    unique_behavior_contracts = {
        json.dumps(contract, sort_keys=True, separators=(",", ":"))
        for contract in behavior_contracts
    }
    if len(unique_behavior_contracts) != 1:
        provenance_complete = False

    model_ids = sorted({model_id for model_id, _scenario_id in seen_pairs})
    scenario_ids = sorted({scenario_id for _model_id, scenario_id in seen_pairs})
    definition_hashes = check_definition_hashes()
    fingerprint_payload = {
        "benchmark_version": get_benchmark_version(REPO_ROOT),
        "result_contract_version": SCANNED_ROW_CONTRACT_VERSION,
        "judge_contract": scan_plan.get("judge_contract"),
        "check_prompt_hashes": check_prompt_hashes(),
        "judge_model": scan_plan.get("judge_model"),
        "scenario_ids": scenario_ids,
        "scenario_corpus_sha256": corpus_hash,
        "scoring_config_sha256": scoring_config_hash,
        "check_definition_hashes": definition_hashes,
        "source_behavior_contracts": sorted(unique_behavior_contracts),
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return {
        **scan_plan,
        "schema": SCAN_PLAN_SCHEMA,
        "benchmark_version": get_benchmark_version(REPO_ROOT),
        "result_contract_version": SCANNED_ROW_CONTRACT_VERSION,
        "model_ids": model_ids,
        "scenario_ids": scenario_ids,
        "scenario_corpus_sha256": corpus_hash,
        "scoring_config_sha256": scoring_config_hash,
        "check_definition_hashes": definition_hashes,
        "check_prompt_hashes": check_prompt_hashes(),
        "source_runs": source_runs,
        "transcript_hashes": sorted(
            transcript_hashes,
            key=lambda item: (item["model_id"], item["scenario_id"]),
        ),
        "selection": selection or {},
        "provenance_complete": provenance_complete,
        "comparability_fingerprint": fingerprint,
    }


def build_scan_plan(
    transcript_pairs: list[dict[str, Any]],
    modes: dict[str, dict[str, Any]],
    *, judge_model: str,
) -> dict[str, Any]:
    """Use actual prompt bytes as a conservative token envelope.

    One UTF-8 byte per input token bounds byte-tokenized text without a
    model-specific tokenizer. Output uses the judge's configured allowance.
    Provider prices remain estimates; the runtime records reported costs.
    """
    input_tokens = 0
    for pair in transcript_pairs:
        transcript = load_transcript(Path(pair["transcript_path"]))
        if not transcript or not any(t.get("role") == "assistant" for t in transcript):
            raise ValueError(f"Incomplete transcript: {pair['transcript_path']}")
        text = _format_transcript_for_prompt(transcript)
        for check in modes.values():
            messages = [{"role": "system", "content": prompt_for_check(check)},
                        {"role": "user", "content": text}]
            input_tokens += len(json.dumps(messages, ensure_ascii=False).encode())
    calls = len(transcript_pairs) * len(modes)
    output_tokens = calls * JUDGE_MAX_TOKENS
    pricing = MODEL_PRICING.get(judge_model)
    estimate = None if pricing is None else (
        input_tokens * pricing[0] + output_tokens * pricing[1]
    ) / 1_000_000
    return {
        "judge_model": judge_model,
        "judge_contract": {"temperature": JUDGE_TEMPERATURE,
                           "max_tokens": JUDGE_MAX_TOKENS, "context_policy": CONTEXT_POLICY},
        "transcript_count": len(transcript_pairs),
        "check_count": len(modes), "planned_llm_calls": calls,
        "estimated_cost_usd": estimate,
        "maximum_reasonable_cost_ceiling_usd": (
            maximum_reasonable_cost_ceiling(estimate) if estimate is not None else None
        ),
        "pricing_known": pricing is not None,
        "cost_assumptions": {"input_token_envelope": input_tokens,
                             "output_token_allowance": output_tokens,
                             "basis": "actual serialized prompt UTF-8 bytes; configured output allowance",
                             "price_per_million_input_output_usd": pricing},
    }


def load_transcript(path: Path) -> list[dict[str, Any]]:
    return load_jsonl(path)


def transcripts_for_run(run_dir: Path) -> list[dict[str, Any]]:
    """Read explicit transcript identities. Missing or corrupt sources are errors."""
    artifact_path = run_dir / "transcript_run.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    if artifact.get("artifact_type") != "transcript_run/v1":
        raise ValueError(f"Unsupported transcript artifact: {artifact_path}")
    pairs = []
    seen = set()
    for row in artifact["transcripts"]:
        key = (row["model_id"], row["scenario_id"])
        if not all(key) or key in seen:
            raise ValueError(f"Missing or duplicate transcript identity: {key}")
        seen.add(key)
        path = Path(row["transcript_path"])
        if not path.is_absolute():
            path = run_dir / path
        if not path.is_file():
            raise ValueError(f"Missing transcript: {path}")
        pairs.append({"transcript_path": path.resolve(), "model": row["model"],
                      "model_id": key[0], "scenario_id": key[1], "category": row["category"]})
    return pairs


def scan_run(
    run_dir: Path, engine: ModeEngine, limit: int | None = None,
    filename_filter: str | None = None,
    skip_keys: set[tuple[str, str]] | None = None,
    progress_callback: Callable[[dict[str, Any], ModeEngineOutput], None] | None = None,
):
    pairs = transcripts_for_run(run_dir)
    if filename_filter:
        pairs = [p for p in pairs if filename_filter.lower() in p["transcript_path"].name.lower()]
    if limit is not None:
        pairs = pairs[:limit]
    records, outputs = [], []
    for pair in pairs:
        if skip_keys and (pair["model_id"], pair["scenario_id"]) in skip_keys:
            continue
        out = engine.evaluate(load_transcript(pair["transcript_path"]), {})
        record = {**pair, "transcript_path": str(pair["transcript_path"]),
                  "contract_version": SCANNED_ROW_CONTRACT_VERSION, **out.to_dict()}
        records.append(record)
        outputs.append(out)
        if progress_callback:
            progress_callback(record, out)
    return records, outputs


def write_outputs(
    output_dir: Path, outputs: list[dict[str, Any]],
    engine_outputs: list[ModeEngineOutput], run_dirs: list[Path],
    scan_plan: dict[str, Any] | None = None, *, cost_snapshot: dict[str, Any] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "per_run.jsonl").open("w", encoding="utf-8") as handle:
        for row in outputs:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    if scan_plan is not None:
        (output_dir / "scan_plan.json").write_text(json.dumps(scan_plan, indent=2) + "\n")
    (output_dir / "cost_report.json").write_text(json.dumps({
        "estimated_cost_usd": (scan_plan or {}).get("estimated_cost_usd"),
        "actual": cost_snapshot,
    }, indent=2) + "\n")
    counts: dict[str, int] = {}
    for row in outputs:
        for decision in row["mode_results"]:
            verdict = decision["verdict"]
            counts[verdict] = counts.get(verdict, 0) + 1
    lines = ["# Scan summary", "", f"Transcripts: {len(outputs)}.",
             f"Judge: {(scan_plan or {}).get('judge_model', 'unspecified')}.", "",
             "| Verdict | Decisions |", "|---|---:|"]
    lines += [f"| {verdict} | {counts.get(verdict, 0)} |"
              for verdict in ("PASS", "FAIL", "UNCLEAR", "NOT_APPLICABLE")]
    lines += ["", "These are model judgments under the recorded criteria.",
              "Each decision retains its evidence and rationale in per_run.jsonl."]
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n")
