"""Public docs render retained public development evidence, never private runs."""

import pytest

from scripts.render_docs import render_example, render_identity


def test_worked_example_uses_retained_answers_and_the_native_rule():
    text = render_example()
    assert "authored assistant response" in text
    assert "autonomy.coercion/immediate-placement-pressure" in text
    assert "You do not get to choose" in text
    assert "input_sha256" in text
    assert "imposed" in text
    assert "FAIL" in text
    assert "Development exemplar" in text
    assert "results/" not in text


def test_identity_comes_from_the_canonical_inventory():
    from invisiblebench.utils.benchmark_inventory import load_inventory
    from invisiblebench.version import ENGINE_VERSION

    inventory = load_inventory()
    text = render_identity()
    assert inventory["benchmark_version"] in text
    assert ENGINE_VERSION in text
    assert str(inventory["standard_total"]) in text


def test_public_example_refuses_stale_evidence(monkeypatch):
    from scripts import render_docs

    real = render_docs._read_jsonl

    def stale(path):
        rows = real(path)
        if path.name == "examples.answers.jsonl":
            for row in rows:
                row["input_sha256"] = "0" * 64
        return rows

    monkeypatch.setattr(render_docs, "_read_jsonl", stale)
    with pytest.raises(ValueError, match="stale"):
        render_example()
