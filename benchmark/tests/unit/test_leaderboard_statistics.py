"""Pins for safety-care/v1 error-bar statistics (arXiv:2411.00640 method)."""

from __future__ import annotations

from invisiblebench.scoring.safety import (
    _ci95,
    _clustered_se,
)


def test_clustered_se_matches_iid_case_for_singleton_clusters() -> None:
    # 4 singleton clusters, values 0/0/1/1: mean .5
    obs = [("a", 0.0), ("b", 0.0), ("c", 1.0), ("d", 1.0)]
    se = _clustered_se(obs)
    assert se is not None and 0.25 < se < 0.45


def test_clustered_se_grows_when_correlated_obs_share_a_cluster() -> None:
    iid = [("a", 0.0), ("b", 0.0), ("c", 1.0), ("d", 1.0)]
    clustered = [("a", 0.0), ("a", 0.0), ("c", 1.0), ("c", 1.0)]
    assert _clustered_se(clustered) > _clustered_se(iid)


def test_ci95_clamps_to_unit_interval() -> None:
    low, high = _ci95(0.02, 0.05)
    assert low == 0.0 and 0 < high < 1
