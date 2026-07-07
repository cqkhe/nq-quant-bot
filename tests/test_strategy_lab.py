import pandas as pd

from nqbot.strategy_lab import (
    ExperimentResult,
    ParameterGrid,
    StrategyFamily,
    StrategyFilterConfig,
    StrategySearchConfig,
    apply_filters,
    generate_variants,
    rank_results,
    run_strategy_search,
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
    csv_path, summary_path = write_strategy_search_outputs(ranking, cfg.reports_dir)

    assert ranking.evaluated_variants == 3
    assert csv_path.exists()
    assert summary_path.exists()
    rows = pd.read_csv(csv_path)
    assert len(rows) == 3
    assert "rank_score" in rows.columns
    assert "Strategy Search Summary" in summary_path.read_text(encoding="utf-8")
    assert all(status != "PAPER_CANDIDATE" for status in rows["decision_status"])
