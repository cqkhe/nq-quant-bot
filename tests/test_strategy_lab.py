import pandas as pd
import importlib.util
import pytest
from pathlib import Path

from nqbot.strategy_lab import (
    ExperimentResult,
    ParameterGrid,
    StrategyFamily,
    StrategyFilterConfig,
    StrategySearchConfig,
    StrategyRanking,
    StrategySearchSuite,
    apply_filters,
    available_families,
    generate_variants,
    get_family,
    rank_results,
    registered_families,
    run_strategy_search,
    run_strategy_search_suite,
    write_strategy_search_outputs,
)


def _family() -> StrategyFamily:
    return StrategyFamily(
        name="test_family",
        base_strategy="test_strategy",
        parameter_grid=ParameterGrid({
            "min_atr20_points": [6.0, 8.0],
            "rel_volume_threshold": [1.05, 1.10],
        }),
    )


def _result(
    variant,
    *,
    pnl_net=1_000.0,
    n_trades=120,
    profit_factor=1.30,
    expectancy_r=0.20,
    max_drawdown_pct=5.0,
    mc_probability_negative=0.05,
    mc_probability_extreme_drawdown=0.05,
    bootstrap_probability_expectancy_le_zero=0.05,
    cost_stress_survives=True,
    depends_on_top_winners=False,
    robustness_passed=True,
    decision_status="PAPER_CANDIDATE",
):
    return ExperimentResult(
        variant=variant,
        n_trades=n_trades,
        pnl_net=pnl_net,
        profit_factor=profit_factor,
        expectancy_r=expectancy_r,
        max_drawdown_pct=max_drawdown_pct,
        mc_probability_negative=mc_probability_negative,
        mc_probability_extreme_drawdown=mc_probability_extreme_drawdown,
        bootstrap_probability_expectancy_le_zero=bootstrap_probability_expectancy_le_zero,
        cost_stress_survives=cost_stress_survives,
        depends_on_top_winners=depends_on_top_winners,
        robustness_passed=robustness_passed,
        decision_status=decision_status,
    )


def test_parameter_grid_generates_limited_reproducible_variants():
    family = _family()

    first = generate_variants(family, max_variants=2, seed=42)
    second = generate_variants(family, max_variants=2, seed=42)

    assert [v.variant_id for v in first] == [v.variant_id for v in second]
    assert len(first) == 2
    assert all(v.strategy_name == "test_strategy" for v in first)
    assert all(v.family == "test_family" for v in first)


def test_ranking_penalizes_fragility_not_just_pnl():
    variants = generate_variants(_family(), max_variants=2, seed=1)
    cfg = StrategyFilterConfig(min_trades=50)
    fragile_big_pnl = apply_filters(_result(
        variants[0],
        pnl_net=20_000.0,
        profit_factor=2.0,
        expectancy_r=0.50,
        max_drawdown_pct=35.0,
        mc_probability_negative=0.80,
        mc_probability_extreme_drawdown=0.70,
        bootstrap_probability_expectancy_le_zero=0.70,
        cost_stress_survives=False,
        depends_on_top_winners=True,
        robustness_passed=False,
        decision_status="BLOCKED_FOR_PAPER",
    ), cfg)
    modest_robust = apply_filters(_result(variants[1], pnl_net=1_000.0), cfg)

    ranked = rank_results([fragile_big_pnl, modest_robust], cfg)

    assert ranked[0] is modest_robust
    assert ranked[0].paper_candidate
    assert not fragile_big_pnl.passed_filters


def test_strategy_search_with_mock_evaluator_writes_reports(tmp_path):
    family = _family()
    cfg = StrategySearchConfig(
        family=family,
        symbol="MNQ",
        data=str(tmp_path / "data.csv"),
        initial_capital=25_000.0,
        max_variants=3,
        iterations=100,
        seed=7,
        filters=StrategyFilterConfig(min_trades=50),
        reports_dir=str(tmp_path / "reports"),
        config_path=str(tmp_path / "config.yaml"),
    )

    def evaluator(variant, search_cfg):
        del search_cfg
        if variant.params["min_atr20_points"] == 6.0:
            return _result(variant, decision_status="BLOCKED_FOR_PAPER")
        return _result(
            variant,
            max_drawdown_pct=20.0,
            mc_probability_negative=0.40,
            robustness_passed=False,
            decision_status="REJECTED",
        )

    ranking = run_strategy_search(cfg, evaluator=evaluator)
    csv_path, summary_path, family_summary_path = write_strategy_search_outputs(
        ranking, cfg.reports_dir
    )

    assert ranking.evaluated_variants == 3
    assert csv_path.exists()
    assert summary_path.exists()
    assert family_summary_path.exists()
    rows = pd.read_csv(csv_path)
    assert len(rows) == 3
    assert "rank_score" in rows.columns
    assert "Strategy Search Summary" in summary_path.read_text(encoding="utf-8")
    assert all(status != "PAPER_CANDIDATE" for status in rows["decision_status"])


def test_family_registry_contains_requested_families():
    requested = {
        "opening_range_breakout",
        "opening_range_reversal",
        "vwap_mean_reversion",
        "trend_pullback_ema",
        "volatility_expansion_breakout",
        "regime_aware_rr2",
        "vwap_reclaim",
        "previous_day_high_low_breakout",
        "previous_day_high_low_reversal",
        "range_expansion_continuation",
        "failed_breakout_reversal",
        "pullback_to_vwap_trend",
        "ema_trend_continuation",
        "high_volume_reversal",
        "low_volatility_breakout",
        "session_momentum_breakout",
    }
    volume_families = {
        "relative_volume_breakout",
        "volume_climax_reversal",
        "volume_dry_up_breakout",
        "volume_expansion_continuation",
        "high_volume_failed_breakout",
        "low_volume_pullback_continuation",
        "vwap_volume_reclaim",
        "opening_range_volume_breakout",
        "volume_spike_mean_reversion",
        "volume_trend_confirmation",
    }
    gaussian_families = {
        "gaussian_volume_breakout",
        "gaussian_volume_reversal",
        "gaussian_volume_climax",
        "gaussian_volume_dry_up_breakout",
        "gaussian_volume_trend_confirmation",
        "gaussian_volume_failed_breakout",
        "gaussian_volume_mean_reversion",
        "gaussian_volume_expansion_continuation",
    }

    available = set(available_families())
    assert requested.issubset(available)
    assert volume_families.issubset(available)
    assert gaussian_families.issubset(available)
    assert get_family("daytrading_vwap_liquidity_rr2_no_midday_atr_filter").name == "rr2_atr_filter"
    assert get_family("opening_range_breakout").implemented is False
    assert get_family("vwap_mean_reversion").implemented is True
    assert all(not get_family(name).implemented for name in volume_families)
    assert all(not get_family(name).implemented for name in gaussian_families)


def test_parameter_validation_rejects_empty_and_invalid_limits():
    family = _family()

    with pytest.raises(ValueError):
        ParameterGrid({"x": []}).combinations()
    with pytest.raises(ValueError):
        generate_variants(family, max_variants=0, seed=1)
    with pytest.raises(ValueError):
        run_strategy_search(StrategySearchConfig(
            family=family,
            symbol="MNQ",
            data="data.csv",
            initial_capital=25_000.0,
            max_variants=0,
            iterations=100,
            seed=1,
        ), evaluator=lambda variant, cfg: _result(variant))


def test_registered_families_generate_limited_variants():
    for family in registered_families():
        variants = generate_variants(family, max_variants=2, seed=3)
        assert 1 <= len(variants) <= 2
        assert all(v.family == family.name for v in variants)
        if not family.implemented:
            assert all(v.strategy_name.startswith("scaffold::") for v in variants)


def test_all_family_suite_respects_limit_and_writes_family_summary(tmp_path):
    implemented = _family()
    scaffold = StrategyFamily(
        name="scaffold_family",
        base_strategy="scaffold::scaffold_family",
        parameter_grid=ParameterGrid({"prototype": ["baseline", "alt"]}),
        implemented=False,
    )
    configs = [
        StrategySearchConfig(
            family=implemented,
            symbol="MNQ",
            data=str(tmp_path / "data.csv"),
            initial_capital=25_000.0,
            max_variants=1,
            iterations=50,
            seed=9,
            filters=StrategyFilterConfig(min_trades=50),
            reports_dir=str(tmp_path / "reports"),
            config_path=str(tmp_path / "config.yaml"),
        ),
        StrategySearchConfig(
            family=scaffold,
            symbol="MNQ",
            data=str(tmp_path / "data.csv"),
            initial_capital=25_000.0,
            max_variants=1,
            iterations=50,
            seed=9,
            filters=StrategyFilterConfig(min_trades=50),
            reports_dir=str(tmp_path / "reports"),
            config_path=str(tmp_path / "config.yaml"),
        ),
    ]

    def evaluator(variant, search_cfg):
        del search_cfg
        return _result(variant, decision_status="BLOCKED_FOR_PAPER")

    suite = run_strategy_search_suite(configs, evaluator=evaluator)
    csv_path, summary_path, family_summary_path = write_strategy_search_outputs(
        suite, tmp_path / "reports"
    )

    assert suite.evaluated_families == 2
    assert suite.evaluated_variants == 2
    assert len(suite.ranked) == 2
    family_rows = pd.read_csv(family_summary_path)
    assert set(family_rows["family"]) == {"test_family", "scaffold_family"}
    assert family_rows["evaluated_variants"].tolist() == [1, 1]
    assert "Top 10 global" in summary_path.read_text(encoding="utf-8")
    assert "scaffold_family" in pd.read_csv(csv_path)["family"].tolist()


def test_family_summary_lists_scaffold_registered_but_not_evaluated(tmp_path):
    implemented = _family()
    scaffold = StrategyFamily(
        name="pending_volume_family",
        base_strategy="scaffold::pending_volume_family",
        parameter_grid=ParameterGrid({"prototype": ["baseline"]}),
        implemented=False,
    )
    cfg = StrategySearchConfig(
        family=implemented,
        symbol="MNQ",
        data=str(tmp_path / "data.csv"),
        initial_capital=25_000.0,
        max_variants=1,
        iterations=50,
        seed=9,
        filters=StrategyFilterConfig(min_trades=50),
        reports_dir=str(tmp_path / "reports"),
        config_path=str(tmp_path / "config.yaml"),
    )

    def evaluator(variant, search_cfg):
        del search_cfg
        return _result(variant, decision_status="BLOCKED_FOR_PAPER")

    suite = run_strategy_search_suite(
        [cfg],
        evaluator=evaluator,
        registered_families=[implemented, scaffold],
    )
    _, summary_path, family_summary_path = write_strategy_search_outputs(
        suite, tmp_path / "reports"
    )

    family_rows = pd.read_csv(family_summary_path)
    scaffold_row = family_rows[family_rows["family"] == "pending_volume_family"].iloc[0]
    assert scaffold_row["evaluated_variants"] == 0
    assert scaffold_row["top_decision"] == "NOT_EXECUTABLE"
    assert "pending_volume_family" in summary_path.read_text(encoding="utf-8")
    assert "Familias no ejecutables/scaffolding" in summary_path.read_text(encoding="utf-8")


def test_run_strategy_search_cli_family_all_uses_per_family_limit(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_strategy_search.py"
    spec = importlib.util.spec_from_file_location("run_strategy_search_cli_test", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    scaffold = StrategyFamily(
        name="scaffold_family",
        base_strategy="scaffold::scaffold_family",
        parameter_grid=ParameterGrid({"prototype": ["baseline", "alt"]}),
        implemented=False,
    )
    families = [_family(), StrategyFamily(
        name="other_family",
        base_strategy="test_strategy",
        parameter_grid=ParameterGrid({"x": [1, 2]}),
    ), scaffold]
    captured: list[StrategySearchConfig] = []

    def fake_suite(configs, registered_families=None):
        assert registered_families == families
        captured.extend(configs)
        rankings = []
        for cfg in configs:
            variant = generate_variants(cfg.family, max_variants=1, seed=cfg.seed)[0]
            result = apply_filters(_result(variant, decision_status="BLOCKED_FOR_PAPER"), cfg.filters)
            rank_results([result], cfg.filters)
            rankings.append(StrategyRanking(cfg.family, [result], 1, 1))
        return StrategySearchSuite(rankings, registered_families=registered_families or [])

    def fake_write(ranking, reports_dir):
        del ranking
        out = Path(reports_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths = (
            out / "strategy_search_results.csv",
            out / "strategy_search_summary.md",
            out / "strategy_search_family_summary.csv",
        )
        for path in paths:
            path.write_text("ok", encoding="utf-8")
        return paths

    monkeypatch.setattr(module, "registered_families", lambda: families)
    monkeypatch.setattr(module, "run_strategy_search_suite", fake_suite)
    monkeypatch.setattr(module, "write_strategy_search_outputs", fake_write)

    code = module.main([
        "--symbol", "MNQ",
        "--data", str(tmp_path / "data.csv"),
        "--family", "all",
        "--initial-capital", "25000",
        "--max-variants-per-family", "2",
        "--iterations", "50",
        "--seed", "11",
        "--reports-dir", str(tmp_path / "reports"),
    ])

    assert code == 0
    assert len(captured) == 2
    assert all(cfg.family.implemented for cfg in captured)
    assert all(cfg.max_variants == 2 for cfg in captured)
    assert all(cfg.seed == 11 for cfg in captured)


def test_no_paper_candidate_without_filters_and_robustness():
    variant = generate_variants(_family(), max_variants=1, seed=1)[0]
    result = apply_filters(_result(
        variant,
        decision_status="PAPER_CANDIDATE",
        robustness_passed=False,
        max_drawdown_pct=30.0,
        mc_probability_negative=0.60,
    ), StrategyFilterConfig(min_trades=50))

    assert result.decision_status == "PAPER_CANDIDATE"
    assert not result.robustness_passed
    assert not result.passed_filters
    assert not result.paper_candidate
