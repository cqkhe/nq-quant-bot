"""Decision Engine — gates ejecutables del Quant Brain (Fase 2).

Evalúa las métricas de un experimento contra los criterios PRE-REGISTRADOS
y asigna un estado: PAPER_CANDIDATE, BLOCKED_FOR_PAPER,
APPROVED_FOR_RESEARCH, OBSERVATION o REJECTED.

Principios:
  * No corre backtests: consume métricas ya producidas (CSV de validadores
    o carpeta de reporte de backtest).
  * Un criterio NO EVALUABLE (dato faltante) no está cumplido: bloquea la
    candidatura a paper. Certificar requiere datos completos.
  * PAPER_CANDIDATE no es aprobación automática: habilita a PROPONER la
    estrategia, y la aprobación final es una decisión humana registrada
    en research/decisions/ (ver decision_engine_rules.md).

Árbol de decisión (resumen; detalle en decision_engine_rules.md):
  1. TODOS los criterios de paper cumplidos           -> PAPER_CANDIDATE
  2. Performance de nivel paper, sin validación limpia -> BLOCKED_FOR_PAPER
  3. Muestra < mínimo para veredicto                   -> OBSERVATION
  4. Sin edge (expR <= 0 o PF < 1.0)                   -> REJECTED
  5. Señales positivas por debajo del nivel paper      -> APPROVED_FOR_RESEARCH
  6. Cualquier otro caso (mixto)                       -> OBSERVATION
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import (
    CriterionResult,
    Decision,
    DecisionStatus,
    ExperimentMetrics,
    PaperCriteria,
)


# ---------------------------------------------------------------- evaluación
def evaluate(metrics: ExperimentMetrics, criteria: PaperCriteria | None = None) -> Decision:
    cfg = criteria or PaperCriteria()
    m = metrics
    checks: list[CriterionResult] = []

    def add(name: str, passed: bool | None, detail: str) -> None:
        checks.append(CriterionResult(name, passed, detail))

    # ---- criterios de performance (nivel paper)
    trades_ok = m.n_trades >= cfg.min_trades
    add("muestra_minima_paper", trades_ok,
        f"{m.n_trades} trades (mínimo {cfg.min_trades})")

    pf_ok = None if m.profit_factor is None else m.profit_factor >= cfg.min_profit_factor
    add("profit_factor", pf_ok,
        f"{m.profit_factor} (mínimo {cfg.min_profit_factor})")

    expr_ok = None if m.expectancy_r is None else m.expectancy_r > cfg.min_expectancy_r
    add("expectancia_r_positiva", expr_ok,
        f"{m.expectancy_r} (debe ser > {cfg.min_expectancy_r})")

    dd_ok = None if m.max_drawdown_pct is None else m.max_drawdown_pct < cfg.max_drawdown_pct
    add("drawdown", dd_ok,
        f"{m.max_drawdown_pct}% (máximo {cfg.max_drawdown_pct}%)")

    dep_ok = None if m.pnl_without_top5 is None else m.pnl_without_top5 > 0
    add("no_depende_de_pocos_trades", dep_ok,
        "PnL sin los 5 mejores trades: "
        + (f"{m.pnl_without_top5:+,.2f} (debe seguir > 0)" if m.pnl_without_top5 is not None
           else "sin datos de trades (usar carpeta de reporte)"))

    # ---- criterios de limpieza de la validación
    oos_ok: bool | None
    if m.is_out_of_sample is None:
        oos_ok = None
        oos_detail = "no declarado (--oos si/no)"
    elif not m.is_out_of_sample:
        oos_ok = False
        oos_detail = "el período NO es out-of-sample"
    else:
        oos_ok = m.pnl_net > 0
        oos_detail = f"OOS con PnL {m.pnl_net:+,.2f} (debe ser positivo)"
    add("validacion_oos_positiva", oos_ok, oos_detail)

    clean_ok = None if m.overlaps_design_period is None else not m.overlaps_design_period
    add("sin_contaminacion_de_diseño", clean_ok,
        "no declarado (--overlaps si/no)" if clean_ok is None
        else ("los datos NO se solapan con el período de diseño" if clean_ok
              else "los datos se solapan con el período de diseño"))

    # ---- métricas informativas (no gatean, pero quedan a la vista)
    if m.pct_positive_months is not None:
        add("meses_positivos (informativo)", None,
            f"{m.pct_positive_months:.0f}% de {m.n_months} meses")
    if m.max_losing_streak is not None:
        add("racha_perdedora (informativo)", None, f"{m.max_losing_streak} trades")

    # ---------------------------------------------------------- árbol de decisión
    paper_gate = [trades_ok, pf_ok, expr_ok, dd_ok, dep_ok, oos_ok, clean_ok]
    perf_grade = (trades_ok and pf_ok is True and expr_ok is True and dd_ok is True)
    has_edge_signal = (m.expectancy_r or 0) > 0 and (m.profit_factor or 0) >= 1.0
    no_edge = (m.expectancy_r is not None and m.expectancy_r <= 0) or (
        m.profit_factor is not None and m.profit_factor < 1.0
    )

    reasons: list[str] = []
    if all(c is True for c in paper_gate):
        status = DecisionStatus.PAPER_CANDIDATE
        reasons.append("Cumple TODOS los criterios mínimos pre-registrados para paper trading.")
        recommendation = (
            "Proponer para paper trading: crear la decisión DXXX en research/decisions/ "
            "con aprobación humana explícita. PAPER_CANDIDATE no es aprobación automática."
        )
    elif perf_grade:
        status = DecisionStatus.BLOCKED_FOR_PAPER
        reasons.append("Performance de nivel paper, pero la validación no está limpia o completa "
                       "(OOS/contaminación/dependencia sin verificar o fallidos).")
        recommendation = (
            "Conseguir validación out-of-sample virgen y completar los criterios faltantes "
            "antes de volver a evaluar. No proponer para paper en este estado."
        )
    elif m.n_trades < cfg.min_sample_for_verdict:
        status = DecisionStatus.OBSERVATION
        reasons.append(f"Muestra insuficiente para veredicto ({m.n_trades} < "
                       f"{cfg.min_sample_for_verdict} trades).")
        recommendation = "Juntar más historia/datos antes de decidir."
    elif no_edge:
        status = DecisionStatus.REJECTED
        reasons.append("Sin edge: expectancia R no positiva y/o profit factor < 1.0 "
                       "con muestra suficiente.")
        recommendation = (
            "Registrar el descarte en research/decisions/ y en el índice. "
            "No re-testear sin evidencia nueva."
        )
    elif has_edge_signal:
        status = DecisionStatus.APPROVED_FOR_RESEARCH
        reasons.append("Señales positivas (expR > 0, PF >= 1.0) por debajo del nivel paper.")
        recommendation = (
            "Continuar el protocolo de investigación: más muestra, validación OOS "
            "y/o walk-forward según la ficha de la hipótesis."
        )
    else:
        status = DecisionStatus.OBSERVATION
        reasons.append("Evidencia mixta: métricas contradictorias o incompletas.")
        recommendation = "Completar datos faltantes o juntar más historia antes de decidir."

    failed = [c.name for c in checks if c.passed is False]
    not_eval = [c.name for c in checks if c.passed is None and "informativo" not in c.name]
    if failed:
        reasons.append(f"Criterios fallidos: {', '.join(failed)}.")
    if not_eval:
        reasons.append(f"Criterios no evaluables con esta fuente: {', '.join(not_eval)}.")

    return Decision(status=status, strategy=m.strategy, source=m.source,
                    criteria=checks, reasons=reasons, recommendation=recommendation)


# ---------------------------------------------------------------- adaptadores
_CSV_COLUMN_MAP = {
    "trades": "n_trades",
    "pnl_net": "pnl_net",
    "profit_factor": "profit_factor",
    "expectancy_r": "expectancy_r",
    "winrate_pct": "winrate_pct",
    "max_drawdown_usd": "max_drawdown_usd",
    "max_drawdown_pct": "max_drawdown_pct",
    "racha_perdedora_max": "max_losing_streak",
}


def metrics_from_comparison_csv(
    path: str | Path,
    strategy: str | None = None,
    is_out_of_sample: bool | None = None,
    overlaps_design_period: bool | None = None,
) -> ExperimentMetrics:
    """Lee la fila de una estrategia desde un CSV de validador/comparador.

    Formato esperado: el que generan scripts/validate_*.py y
    compare_strategies.py (columna 'estrategia' + métricas estándar).
    Meses positivos y dependencia de pocos trades no están en esos CSV:
    quedan como no evaluables (usar carpeta de reporte para el gate completo).
    """
    path = Path(path)
    df = pd.read_csv(path)
    if "estrategia" not in df.columns:
        raise ValueError(f"{path.name}: no tiene columna 'estrategia'")
    rows = df[~df["estrategia"].str.startswith("delta")]
    if strategy is not None:
        rows = rows[rows["estrategia"] == strategy]
        if rows.empty:
            raise ValueError(f"{path.name}: no hay fila para {strategy!r}. "
                             f"Disponibles: {list(df['estrategia'].unique())}")
    elif len(rows) > 1:
        raise ValueError(f"{path.name}: hay varias estrategias "
                         f"({list(rows['estrategia'])}); indicar --strategy")
    row = rows.iloc[0]

    kwargs = {}
    for col, field_name in _CSV_COLUMN_MAP.items():
        if col in row.index and pd.notna(row[col]):
            value = row[col]
            kwargs[field_name] = int(value) if field_name in ("n_trades", "max_losing_streak") else float(value)
    return ExperimentMetrics(
        source=str(path),
        strategy=str(row["estrategia"]),
        n_trades=kwargs.pop("n_trades", 0),
        pnl_net=kwargs.pop("pnl_net", 0.0),
        profit_factor=kwargs.pop("profit_factor", None),
        expectancy_r=kwargs.pop("expectancy_r", None),
        is_out_of_sample=is_out_of_sample,
        overlaps_design_period=overlaps_design_period,
        **kwargs,
    )


def metrics_from_report_folder(
    path: str | Path,
    is_out_of_sample: bool | None = None,
    overlaps_design_period: bool | None = None,
) -> ExperimentMetrics:
    """Computa TODAS las métricas desde una carpeta de reporte de backtest
    (trades.csv + equity_curve.csv): la fuente completa para el gate."""
    folder = Path(path)
    trades = pd.read_csv(folder / "trades.csv", parse_dates=["entry_time", "exit_time"])
    equity = pd.read_csv(folder / "equity_curve.csv", index_col=0, parse_dates=True)["equity"]

    pnl = trades["pnl_net"]
    wins = pnl > 0
    gross_profit = float(pnl[wins].sum())
    gross_loss = float(-pnl[pnl < 0].sum())

    running_max = equity.cummax()
    dd = equity - running_max
    max_dd_usd = float(-dd.min())
    max_dd_pct = float(-(dd / running_max).min() * 100.0)

    ordered = trades.sort_values("exit_time")["pnl_net"]
    losing = (ordered < 0).to_numpy()
    streak = best = 0
    for is_loss in losing:
        streak = streak + 1 if is_loss else 0
        best = max(best, streak)

    monthly = pnl.groupby(trades["entry_time"].dt.to_period("M").astype(str).to_numpy()).sum()
    top5 = float(pnl[wins].nlargest(5).sum())

    return ExperimentMetrics(
        source=str(folder),
        strategy=folder.name,
        n_trades=len(trades),
        pnl_net=round(float(pnl.sum()), 2),
        profit_factor=round(gross_profit / gross_loss, 3) if gross_loss > 0 else None,
        expectancy_r=round(float(trades["r_multiple"].mean()), 3) if len(trades) else None,
        winrate_pct=round(float(wins.mean()) * 100, 2) if len(trades) else None,
        max_drawdown_usd=round(max_dd_usd, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        max_losing_streak=best,
        n_months=len(monthly),
        pct_positive_months=round(float((monthly > 0).mean()) * 100, 1) if len(monthly) else None,
        pnl_without_top5=round(float(pnl.sum()) - top5, 2),
        is_out_of_sample=is_out_of_sample,
        overlaps_design_period=overlaps_design_period,
    )
