#!/usr/bin/env python
"""Exploración de regímenes de mercado sobre un dataset procesado.

Clasifica cada barra RTH con el Market Regime Engine (100% causal) y
resume la composición de regímenes: por barras, por sesión dominante,
cruce tendencia x volatilidad y evolución mensual.

NO corre backtests ni toca estrategias: es lectura del mercado.

Uso:
    python scripts/analyze_market_regimes.py --data data/processed/ARCHIVO_clean.csv

Genera:
    reports/market_regime_summary.csv
    reports/market_regime_summary.md
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nqbot.config.settings import Config                     # noqa: E402
from nqbot.data.loader import load_ohlcv_csv                 # noqa: E402
from nqbot.regime import LABEL_COLUMNS, classify_regimes     # noqa: E402
from nqbot.utils.logger import setup_logger                  # noqa: E402
from nqbot.utils.sessions import filter_to_trade_session     # noqa: E402

DIMENSIONS = {
    "vol_regime": "Volatilidad",
    "trend_regime": "Tendencia",
    "expansion_regime": "Expansión",
    "directional_bias": "Sesgo direccional",
}


def dominant_by_session(labeled: pd.DataFrame, column: str) -> pd.Series:
    """Etiqueta dominante (moda) de cada sesión, ignorando no clasificables."""
    def mode(series: pd.Series):
        counts = series.dropna().value_counts()
        return counts.index[0] if len(counts) else None

    return labeled[column].groupby(labeled.index.normalize()).agg(mode)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, help="CSV procesado (data/processed/...)")
    ap.add_argument("--config", default=str(ROOT / "config" / "config.yaml"))
    args = ap.parse_args()

    logger = setup_logger(log_dir=ROOT / "logs", level=logging.WARNING)
    config = Config.from_yaml(args.config)
    df = filter_to_trade_session(load_ohlcv_csv(args.data, logger), config.session)
    print(f"Clasificando {len(df):,} barras RTH "
          f"({df.index[0]} -> {df.index[-1]}, {df.index.normalize().nunique()} sesiones) ...")
    labeled = classify_regimes(df)

    # ------------------------------------------------------------ resumen tidy
    rows = []
    month_key = labeled.index.to_period("M").astype(str).to_numpy()
    for column, title in DIMENSIONS.items():
        bar_counts = labeled[column].value_counts(dropna=False)
        sessions = dominant_by_session(labeled, column)
        session_counts = sessions.value_counts(dropna=False)
        for label, n_bars in bar_counts.items():
            key = "no_clasificable" if label is None or pd.isna(label) else str(label)
            n_sessions = 0
            for s_label, s_n in session_counts.items():
                s_key = "no_clasificable" if s_label is None or pd.isna(s_label) else str(s_label)
                if s_key == key:
                    n_sessions = int(s_n)
            rows.append({
                "dimension": title,
                "etiqueta": key,
                "barras": int(n_bars),
                "pct_barras": round(n_bars / len(labeled) * 100, 1),
                "sesiones_dominantes": n_sessions,
                "pct_sesiones": round(n_sessions / sessions.size * 100, 1),
            })
    summary = pd.DataFrame(rows)
    out_csv = ROOT / "reports" / "market_regime_summary.csv"
    summary.to_csv(out_csv, index=False)

    # ------------------------------------------------------------ markdown
    L = [
        "# Composición de regímenes de mercado",
        "",
        f"- **Dataset:** `{args.data}`",
        f"- **Período:** {df.index[0]} → {df.index[-1]} "
        f"({df.index.normalize().nunique()} sesiones RTH, {len(df):,} barras)",
        "- **Motor:** `nqbot.regime` (100% causal: sin información futura; la",
        "  volatilidad se mide contra las sesiones previas, no contra el dataset).",
        "",
    ]
    for column, title in DIMENSIONS.items():
        L += [f"## {title}", "", "| Etiqueta | % barras | % sesiones (dominante) |", "|---|---|---|"]
        sub = summary[summary["dimension"] == title].sort_values("pct_barras", ascending=False)
        for _, r in sub.iterrows():
            L.append(f"| {r['etiqueta']} | {r['pct_barras']}% | {r['pct_sesiones']}% |")
        L.append("")

    # cruce tendencia x volatilidad (barras clasificadas en ambas)
    both = labeled.dropna(subset=["trend_regime", "vol_regime"])
    if len(both):
        cross = pd.crosstab(both["trend_regime"], both["vol_regime"],
                            normalize="all").mul(100).round(1)
        L += ["## Cruce tendencia × volatilidad (% de barras clasificadas)", "",
              "| tendencia \\ vol | " + " | ".join(cross.columns) + " |",
              "|---" * (len(cross.columns) + 1) + "|"]
        for trend, row in cross.iterrows():
            L.append(f"| {trend} | " + " | ".join(f"{v}%" for v in row) + " |")
        L.append("")

    # evolución mensual: % de barras en expansión y en tendencia
    monthly = pd.DataFrame({
        "pct_expansion": labeled["expansion_regime"].eq("expansion").groupby(month_key).mean() * 100,
        "pct_tendencia": labeled["trend_regime"].isin(
            ["tendencia_alcista", "tendencia_bajista"]).groupby(month_key).mean() * 100,
        "pct_vol_alta": labeled["vol_regime"].eq("alta").groupby(month_key).mean() * 100,
    }).round(1)
    L += ["## Evolución mensual (% de barras)", "",
          "| mes | expansión | tendencia | vol alta |", "|---|---|---|---|"]
    for mes, r in monthly.iterrows():
        L.append(f"| {mes} | {r['pct_expansion']}% | {r['pct_tendencia']}% | {r['pct_vol_alta']}% |")
    L += ["", "> Nota: 'no_clasificable' = warmup de indicadores, rango inicial",
          "> incompleto o historia de volatilidad insuficiente. El motor prefiere",
          "> no etiquetar antes que etiquetar mirando el futuro.", ""]

    out_md = ROOT / "reports" / "market_regime_summary.md"
    out_md.write_text("\n".join(L), encoding="utf-8")

    print("\n".join(L))
    print(f"\nArchivos: {out_csv} | {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
