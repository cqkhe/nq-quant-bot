from pathlib import Path

import pandas as pd
import pytest

from nqbot.research.factory import ResearchWorkflowConfig, run_research_workflow
from nqbot.research.models import DecisionStatus


def _write_report(folder: Path, pnls: list[float], rs: list[float]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    entries = pd.date_range("2026-01-05 10:00", periods=len(pnls), freq="1D")
    pd.DataFrame({
        "entry_time": entries,
        "exit_time": entries + pd.Timedelta(minutes=30),
        "pnl_net": pnls,
        "r_multiple": rs,
    }).to_csv(folder / "trades.csv", index=False)

    equity_values = [25_000.0]
    for pnl in pnls:
        equity_values.append(equity_values[-1] + pnl)
    equity = pd.Series(
        equity_values,
        index=pd.date_range("2026-01-05", periods=len(equity_values), freq="1D"),
        name="equity",
    )
    equity.index.name = "datetime"
    equity.to_csv(folder / "equity_curve.csv")


def test_research_workflow_runs_full_pipeline_with_fake_backtest(tmp_path):
    reports_dir = tmp_path / "reports"
    research_dir = tmp_path / "research" / "experiments"
    data = tmp_path / "data.csv"
    data.write_text("datetime,open,high,low,close,volume\n", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("config: fake\n", encoding="utf-8")
    created_folder = reports_dir / "20260707_010101_MNQ_test_strategy"
    seen_argv: list[str] = []

    def fake_runner(argv: list[str]) -> int:
        seen_argv.extend(argv)
        _write_report(
            created_folder,
            pnls=[100.0, -50.0] * 60,
            rs=[1.0, -0.5] * 60,
        )
        return 0

    cfg = ResearchWorkflowConfig(
        strategy="test_strategy",
        symbol="MNQ",
        data=data,
        initial_capital=25_000.0,
        iterations=300,
        seed=42,
        hypothesis_id="H999",
        reports_dir=reports_dir,
        research_dir=research_dir,
        config_path=config_path,
        is_out_of_sample=True,
        overlaps_design_period=False,
    )

    result = run_research_workflow(cfg, backtest_runner=fake_runner)

    assert result.report_folder == created_folder.resolve()
    assert result.trades_csv.exists()
    assert result.robustness_csv.exists()
    assert result.robustness_summary.exists()
    assert result.decision_summary.exists()
    assert result.research_record.exists()
    assert result.decision.status == DecisionStatus.PAPER_CANDIDATE
    assert "--mode" in seen_argv
    assert "--capital" in seen_argv
    assert "25000.0" in seen_argv
    record = result.research_record.read_text(encoding="utf-8")
    assert "H999" in record
    assert "PAPER_CANDIDATE" in record


def test_research_workflow_raises_when_backtest_fails(tmp_path):
    cfg = ResearchWorkflowConfig(
        strategy="test_strategy",
        symbol="MNQ",
        data=tmp_path / "data.csv",
        initial_capital=25_000.0,
        iterations=10,
        seed=1,
        reports_dir=tmp_path / "reports",
        research_dir=tmp_path / "research",
        config_path=tmp_path / "config.yaml",
    )

    with pytest.raises(RuntimeError, match="exit code 4"):
        run_research_workflow(cfg, backtest_runner=lambda argv: 4)


def test_research_workflow_requires_generated_trades_csv(tmp_path):
    reports_dir = tmp_path / "reports"
    empty_report = reports_dir / "20260707_010101_MNQ_test_strategy"

    def fake_runner(argv: list[str]) -> int:
        empty_report.mkdir(parents=True)
        return 0

    cfg = ResearchWorkflowConfig(
        strategy="test_strategy",
        symbol="MNQ",
        data=tmp_path / "data.csv",
        initial_capital=25_000.0,
        iterations=10,
        seed=1,
        reports_dir=reports_dir,
        research_dir=tmp_path / "research",
        config_path=tmp_path / "config.yaml",
    )

    with pytest.raises(FileNotFoundError, match="trades.csv"):
        run_research_workflow(cfg, backtest_runner=fake_runner)
