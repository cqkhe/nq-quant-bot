# Research Workflow - daytrading_vwap_liquidity_rr2_no_midday_atr_filter

| Campo | Valor |
|---|---|
| Fecha | 2026-07-07 |
| Hipotesis | H002 |
| Estrategia | `daytrading_vwap_liquidity_rr2_no_midday_atr_filter` |
| Simbolo | `MNQ` |
| Dataset | `data\processed\MNQ_2024_01_2026_06_full_1m_ninjatrader_combined_clean.csv` |
| Capital inicial | 25000.00 |
| Iteraciones robustez | 1000 |
| Seed | 42 |
| OOS declarado | True |
| Solapa diseno | False |

## Pipeline

1. Hypothesis metadata
2. Backtest
3. trades.csv
4. Robustness Engine
5. Decision Engine
6. Registro en Research Memory

## Artefactos

- Backtest report: `C:\Users\julie\Documents\nq-quant-bot\reports\20260707_012938_MNQ_daytrading_vwap_liquidity_rr2_no_midday_atr_filter`
- Trades: `C:\Users\julie\Documents\nq-quant-bot\reports\20260707_012938_MNQ_daytrading_vwap_liquidity_rr2_no_midday_atr_filter\trades.csv`
- Robustness CSV: `C:\Users\julie\Documents\nq-quant-bot\reports\20260707_012938_MNQ_daytrading_vwap_liquidity_rr2_no_midday_atr_filter\robustness_report.csv`
- Robustness summary: `C:\Users\julie\Documents\nq-quant-bot\reports\20260707_012938_MNQ_daytrading_vwap_liquidity_rr2_no_midday_atr_filter\robustness_report_summary.md`
- Decision Engine summary: `C:\Users\julie\Documents\nq-quant-bot\reports\20260707_012938_MNQ_daytrading_vwap_liquidity_rr2_no_midday_atr_filter\decision_engine_summary.md`

## Resultado

- Robustness Engine: **FRAGIL**
- Decision Engine: **APPROVED_FOR_RESEARCH**

## Motivos del Decision Engine

- Señales positivas (expR > 0, PF >= 1.0) por debajo del nivel paper.
- Criterios fallidos: profit_factor, drawdown, no_depende_de_pocos_trades, robustez_mc_probabilidad_negativa, robustez_bootstrap_expectancia_no_positiva, robustez_no_depende_de_pocos_ganadores, robustez_sobrevive_costos.

## Bloqueo operativo

Este registro no habilita paper/live/fondeo por si solo. Si el estado fuera PAPER_CANDIDATE, requiere decision humana DXXX.
