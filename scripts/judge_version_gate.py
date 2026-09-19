#!/usr/bin/env python3
"""Gate a judge model upgrade by re-asking a frozen, complete scan.

Every saved request of a frozen scan bundle is reconstructed exactly as the
bundle built it, then sent again to a candidate judge model. The candidate's
answers are derived into judgments with the frozen plan's checks and
thresholds, and compared against the bundle's own stored judgments.

This never modifies the frozen bundle. It writes the candidate's answers,
its derived judgments, and a drift report to a separate directory.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invisiblebench.api.client import (  # noqa: E402
    CostBudgetExceededError,
    cost_tracker,
    maximum_reasonable_cost_ceiling,
)
from invisiblebench.api.typesafe import SystemOneClient, estimated_cost  # noqa: E402
from invisiblebench.evaluation import rules  # noqa: E402
from invisiblebench.judge import (  # noqa: E402
    ANSWERS_FILE,
    PLAN_FILE,
    _ask,
    _conversations,
    _planned_requests,
    _write_judgments,
    derive_all,
    json_bytes,
    load_scan,
    sha256,
)
from invisiblebench.models.scan import Answer, Thresholds  # noqa: E402


def _probability_drift(
    frozen_answers: list[Answer],
    candidate_answers: list[Answer],
    thresholds: Thresholds,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Per-question and total drift between the frozen and candidate probabilities."""
    frozen_by_key = {answer.key: answer for answer in frozen_answers if answer.nouls is not None}
    pairs_by_question: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for candidate in candidate_answers:
        frozen = frozen_by_key.get(candidate.key)
        if frozen is None or frozen.nouls is None or candidate.nouls is None:
            continue
        for question_key, candidate_p in candidate.nouls.items():
            frozen_p = frozen.nouls.get(question_key)
            if frozen_p is None:
                continue
            pairs_by_question[question_key].append((frozen_p, candidate_p))

    def stats(pairs: list[tuple[float, float]]) -> dict[str, Any]:
        deltas = [abs(frozen_p - candidate_p) for frozen_p, candidate_p in pairs]
        flips = sum(
            rules.tri(frozen_p, thresholds) != rules.tri(candidate_p, thresholds)
            for frozen_p, candidate_p in pairs
        )
        return {
            "n": len(pairs),
            "mean_abs_delta": (sum(deltas) / len(deltas)) if deltas else 0.0,
            "max_abs_delta": max(deltas) if deltas else 0.0,
            "band_flips": flips,
        }

    questions = {key: stats(pairs) for key, pairs in sorted(pairs_by_question.items())}
    totals = stats([pair for pairs in pairs_by_question.values() for pair in pairs])
    return questions, totals


def _regate(
    bundle: Path,
    target_model: str,
    *,
    client: Any,
    max_cost_usd: float | None,
    output: Path,
    plan: Any,
    frozen_answers: list[Answer],
    frozen_judgments: list[Any],
    plan_sha: str,
    conversations: Any,
    pending: list[tuple[str, str, str, int, Any]],
) -> dict[str, Any]:
    """Re-ask every pending request against `target_model` and write its report.

    Shared core for both the candidate gate and the `--baseline` re-ask of
    the frozen bundle's own frozen model. Writes `answers.jsonl`,
    `judgments.jsonl`, and `report.json` to `output`.
    """
    estimate = estimated_cost(target_model, plan.input_token_envelope)
    if estimate is None:
        raise ValueError(f"no pricing is known for candidate model: {target_model}")
    if max_cost_usd is None:
        max_cost_usd = estimate
    if not math.isfinite(max_cost_usd) or max_cost_usd <= 0:
        raise ValueError("max_cost_usd must be finite and positive")
    if max_cost_usd < estimate:
        raise ValueError("max_cost_usd is below the candidate's dry-run cost estimate")
    if max_cost_usd > maximum_reasonable_cost_ceiling(estimate):
        raise ValueError("max_cost_usd exceeds the candidate's accepted cost ceiling")

    cost_tracker.reset(max_cost_usd=max_cost_usd)
    target_answers: list[Answer] = []
    for model_id, scenario_id, role, turn, request in pending:
        answer = _ask(
            client,
            target_model,
            request,
            model_id=model_id,
            scenario_id=scenario_id,
            role=role,
            turn=turn,
            plan_sha256=plan_sha,
        )
        target_answers.append(answer)
        if answer.error is not None:
            raise RuntimeError(
                f"{scenario_id} {role} turn {turn}: {answer.error} ({answer.error_detail}); "
                "no version-gate report was written."
            )

    target_judgments = derive_all(plan, conversations, target_answers, plan_sha)
    frozen_by_key = {judgment.key: judgment for judgment in frozen_judgments}
    verdict_flips = sorted(
        (
            {
                "model_id": judgment.model_id,
                "scenario_id": judgment.scenario_id,
                "check_id": judgment.check_id,
                "frozen": frozen_by_key[judgment.key].verdict.value,
                "candidate": judgment.verdict.value,
            }
            for judgment in target_judgments
            if frozen_by_key[judgment.key].verdict != judgment.verdict
        ),
        key=lambda flip: (flip["model_id"], flip["scenario_id"], flip["check_id"]),
    )
    questions, totals = _probability_drift(
        frozen_answers, target_answers, plan.judge.thresholds
    )

    report = {
        "bundle": str(bundle),
        "plan_sha256": plan_sha,
        "frozen_model": plan.judge.model,
        "candidate_model": target_model,
        "requests": len(pending),
        "questions": questions,
        "totals": totals,
        "verdict_flips": verdict_flips,
        "cost_usd": sum(answer.cost_usd for answer in target_answers),
        "input_tokens": sum(answer.input_tokens for answer in target_answers),
    }

    output.mkdir(parents=True, exist_ok=True)
    (output / ANSWERS_FILE).write_bytes(
        b"".join(answer.model_dump_json().encode() + b"\n" for answer in target_answers)
    )
    _write_judgments(output, target_judgments)
    (output / "report.json").write_bytes(json_bytes(report))
    return report


def gate(
    bundle: Path,
    candidate_model: str,
    *,
    client: Any | None = None,
    max_cost_usd: float | None = None,
    output: Path | None = None,
    baseline: bool = False,
) -> dict[str, Any]:
    """Re-ask every saved request of a frozen, complete bundle against a candidate model.

    Never modifies `bundle`. Writes `answers.jsonl` (the candidate's saved
    answers), `judgments.jsonl` (derived from them with the frozen plan's
    checks and thresholds), and `report.json` (the drift report) to
    `output`, which defaults to `<bundle>/version-gate/<candidate-model>/`.

    When `baseline` is set, the frozen bundle's own frozen model is also
    re-asked (same requests, same budget rules) and written under
    `<bundle>/version-gate/baseline-<frozen-model>/`. The candidate report
    then gains `baseline` (that re-ask's own drift against the frozen
    judgments) and `beyond_baseline` (drift the candidate shows beyond what
    the frozen model shows against itself, i.e. the sampling noise floor).
    """
    bundle = Path(bundle)
    plan, frozen_answers, frozen_judgments = load_scan(bundle, complete=True)
    plan_sha = sha256((bundle / PLAN_FILE).read_bytes())
    conversations = _conversations(bundle, plan)
    requests = _planned_requests(plan, conversations)
    pending = sorted(
        (model_id, scenario_id, role, turn, request)
        for (model_id, scenario_id), turns in requests.items()
        for (role, turn), request in turns.items()
    )
    if len(pending) != plan.planned_requests:
        raise ValueError("reconstructed requests differ from the frozen plan's request count")

    client = client if client is not None else SystemOneClient()
    destination = Path(output) if output is not None else bundle / "version-gate" / candidate_model
    report = _regate(
        bundle,
        candidate_model,
        client=client,
        max_cost_usd=max_cost_usd,
        output=destination,
        plan=plan,
        frozen_answers=frozen_answers,
        frozen_judgments=frozen_judgments,
        plan_sha=plan_sha,
        conversations=conversations,
        pending=pending,
    )

    if baseline:
        baseline_destination = bundle / "version-gate" / f"baseline-{plan.judge.model}"
        baseline_report = _regate(
            bundle,
            plan.judge.model,
            client=client,
            max_cost_usd=max_cost_usd,
            output=baseline_destination,
            plan=plan,
            frozen_answers=frozen_answers,
            frozen_judgments=frozen_judgments,
            plan_sha=plan_sha,
            conversations=conversations,
            pending=pending,
        )
        baseline_flip_keys = {
            (flip["model_id"], flip["scenario_id"], flip["check_id"])
            for flip in baseline_report["verdict_flips"]
        }
        beyond_verdict_flips = [
            flip
            for flip in report["verdict_flips"]
            if (flip["model_id"], flip["scenario_id"], flip["check_id"]) not in baseline_flip_keys
        ]
        report["baseline"] = {
            "band_flips": baseline_report["totals"]["band_flips"],
            "verdict_flips": baseline_report["verdict_flips"],
            "max_abs_delta": baseline_report["totals"]["max_abs_delta"],
        }
        report["beyond_baseline"] = {
            "band_flips": max(
                report["totals"]["band_flips"] - baseline_report["totals"]["band_flips"], 0
            ),
            "verdict_flips": beyond_verdict_flips,
        }
        # `_regate` already wrote the candidate's report.json before these
        # keys existed; rewrite it so the persisted report matches what
        # `gate()` returns.
        (destination / "report.json").write_bytes(json_bytes(report))

    return report


class _NoNetworkTestClient:
    """Zero-cost, deterministic stand-in for `--client-only-for-tests`.

    Lets the CLI entry point be exercised end to end (argument parsing, file
    writes, exit code) without network access or an API key. Never used for
    a real version gate.
    """

    def ask(self, *, model: str, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        return {"model": model, "nouls": dict.fromkeys(questions, 0.0), "input_tokens": 0}


def _render(report: dict[str, Any]) -> str:
    totals = report["totals"]
    lines = [
        f"Frozen judge: {report['frozen_model']} -> candidate: {report['candidate_model']}",
        f"Requests: {report['requests']}; answers compared: {totals['n']}",
        f"Max |delta p|: {totals['max_abs_delta']:.4f}; mean |delta p|: {totals['mean_abs_delta']:.4f}",
        f"Band flips: {totals['band_flips']}",
        f"Verdict flips: {len(report['verdict_flips'])}",
        f"Cost: ${report['cost_usd']:.6f} USD ({report['input_tokens']} input tokens)",
    ]
    for flip in report["verdict_flips"]:
        lines.append(
            f"  {flip['model_id']}/{flip['scenario_id']}/{flip['check_id']}: "
            f"{flip['frozen']} -> {flip['candidate']}"
        )
    if "baseline" in report:
        baseline = report["baseline"]
        beyond = report["beyond_baseline"]
        lines.append(
            f"Baseline ({report['frozen_model']} vs itself): "
            f"band flips {baseline['band_flips']}, verdict flips {len(baseline['verdict_flips'])}, "
            f"max |delta p| {baseline['max_abs_delta']:.4f}"
        )
        lines.append(
            f"Beyond baseline: band flips {beyond['band_flips']}, "
            f"verdict flips {len(beyond['verdict_flips'])}"
        )
        for flip in beyond["verdict_flips"]:
            lines.append(
                f"  beyond baseline: {flip['model_id']}/{flip['scenario_id']}/{flip['check_id']}: "
                f"{flip['frozen']} -> {flip['candidate']}"
            )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", required=True, type=Path, help="Frozen, complete scan bundle")
    parser.add_argument(
        "--candidate-model", required=True, help="Judge model to re-ask every saved request against"
    )
    parser.add_argument(
        "--max-cost-usd",
        type=float,
        default=None,
        help="Approved budget; defaults to the candidate's dry-run cost estimate",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Report directory; defaults to <frozen>/version-gate/<candidate-model>/",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help=(
            "Also re-ask the frozen bundle's own frozen model, and gate on "
            "candidate drift beyond that noise floor instead of raw drift"
        ),
    )
    parser.add_argument(
        "--client-only-for-tests",
        action="store_true",
        help="Use a local, zero-cost, no-network client instead of the real judge API",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = _NoNetworkTestClient() if args.client_only_for_tests else None
    try:
        report = gate(
            args.frozen,
            args.candidate_model,
            client=client,
            max_cost_usd=args.max_cost_usd,
            output=args.output,
            baseline=args.baseline,
        )
    except KeyboardInterrupt:
        print("Interrupted; no version-gate report was written.", file=sys.stderr)
        return 130
    except CostBudgetExceededError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(_render(report))
    if args.baseline:
        return 0 if not report["beyond_baseline"]["verdict_flips"] else 1
    return 0 if not report["verdict_flips"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
