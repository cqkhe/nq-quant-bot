# Evaluación — daytrading_vwap_liquidity_rr2_no_midday_atr_filter

- **Fuente:** `reports\atr_filter_validation_MNQ_2024_full_1m_ninjatrader_combined_clean.csv`
- **Estado:** **REJECTED**

## Criterios

| Criterio | Resultado | Detalle |
|---|---|---|
| muestra_minima_paper | CUMPLE | 258 trades (mínimo 100) |
| profit_factor | FALLA | 0.818 (mínimo 1.15) |
| expectancia_r_positiva | FALLA | -0.12 (debe ser > 0.0) |
| drawdown | FALLA | 13.99% (máximo 10.0%) |
| no_depende_de_pocos_trades | no evaluable | PnL sin los 5 mejores trades: sin datos de trades (usar carpeta de reporte) |
| validacion_oos_positiva | FALLA | OOS con PnL -2,948.06 (debe ser positivo) |
| sin_contaminacion_de_diseño | CUMPLE | los datos NO se solapan con el período de diseño |
| racha_perdedora (informativo) | no evaluable | 12 trades |

## Motivo

- Sin edge: expectancia R no positiva y/o profit factor < 1.0 con muestra suficiente.
- Criterios fallidos: profit_factor, expectancia_r_positiva, drawdown, validacion_oos_positiva.
- Criterios no evaluables con esta fuente: no_depende_de_pocos_trades.

## Recomendación

Registrar el descarte en research/decisions/ y en el índice. No re-testear sin evidencia nueva.
