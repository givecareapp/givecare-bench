"""Incremental request sizing must decide exactly as whole-request `check_context`."""

from __future__ import annotations

import json

import pytest

from invisiblebench.api import typesafe
from invisiblebench.evaluation.check_registry import load_checks
from invisiblebench.examples import load_examples, requests_for


def reference_chunks(state, questions):
    """The original quadratic algorithm: re-check the whole candidate every time."""
    result, chunk = [], {}
    for key, question in sorted(questions.items()):
        typesafe.check_context(state, {key: question})
        candidate = {**chunk, key: question}
        try:
            typesafe.check_context(state, candidate)
        except ValueError:
            result.append(chunk)
            chunk = {key: question}
        else:
            chunk = candidate
    if chunk:
        result.append(chunk)
    return result


def incremental_chunks(state, questions):
    result, chunk, fit = [], {}, typesafe.ContextFit(state)
    for key, question in sorted(questions.items()):
        size = fit.size(key, question)
        fit.check_alone(size)
        if not fit.accepts(size):
            result.append(chunk)
            chunk = {}
            fit.reset()
        chunk[key] = question
        fit.add(size)
    if chunk:
        result.append(chunk)
    return result


def outcome(fn, state, questions):
    try:
        return fn(state, questions)
    except ValueError as exc:
        return str(exc)


def literal_check(state, questions):
    """The pre-incremental definition, byte for byte."""
    tokens = lambda v: len(json.dumps(v, ensure_ascii=False, default=str).encode()) / 3  # noqa: E731
    longest = max((tokens(q) for q in questions.values()), default=0.0)
    if tokens(state) + longest > typesafe.MAX_STATE_AND_QUESTION_TOKENS:
        return "state"
    if tokens({"state": state, "questions": questions}) > typesafe.MAX_REQUEST_TOKENS:
        return "request"
    return None


def verdict(state, questions):
    try:
        typesafe.check_context(state, questions)
    except ValueError as exc:
        return "state" if "longest" in str(exc) else "request"
    return None


def real_requests(root):
    checks = load_checks(root)
    found = []
    for rows in load_examples(root, checks).values():
        for row in rows:
            found.extend(requests_for(checks[row["check_id"]], row).values())
    return found


def test_real_requests_chunk_identically_at_real_and_tight_limits(monkeypatch, published_checks):
    found = real_requests(published_checks)
    assert found
    for max_request, max_state in [(64_000, 32_000), (1500, 1200), (700, 600), (400, 300)]:
        monkeypatch.setattr(typesafe, "MAX_REQUEST_TOKENS", max_request)
        monkeypatch.setattr(typesafe, "MAX_STATE_AND_QUESTION_TOKENS", max_state)
        for request in found:
            state, questions = request["state"], request["questions"]
            assert outcome(incremental_chunks, state, questions) == outcome(
                reference_chunks, state, questions
            )
            assert verdict(state, questions) == literal_check(state, questions)


@pytest.mark.parametrize(
    "state", ["", "s" * 100, "漢" * 40, {"a": "🫂\u0000é", "b": ["x", 1, None]}]
)
def test_straddling_sizes_chunk_identically(monkeypatch, state):
    monkeypatch.setattr(typesafe, "MAX_REQUEST_TOKENS", 300)
    monkeypatch.setattr(typesafe, "MAX_STATE_AND_QUESTION_TOKENS", 200)
    # Sweep question sizes across both limits, one byte at a time.
    for width in range(1, 260):
        for filler in ("y", "é", "🫂"):
            questions = {
                f"k{i:02d}": {"type": "noul", "instructions": filler * (width + i % 3)}
                for i in range(7)
            }
            assert outcome(incremental_chunks, state, questions) == outcome(
                reference_chunks, state, questions
            )
            assert verdict(state, questions) == literal_check(state, questions)


def test_empty_and_exact_boundary_requests(monkeypatch):
    assert verdict("s", {}) == literal_check("s", {}) is None
    state = "s"
    base = len(json.dumps({"state": state, "questions": {"q": ""}}).encode())
    for limit in (base // 3 - 1, base // 3, base // 3 + 1):
        monkeypatch.setattr(typesafe, "MAX_REQUEST_TOKENS", limit)
        assert verdict(state, {"q": ""}) == literal_check(state, {"q": ""})
