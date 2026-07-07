# H002 — Resultado de la variante dynamic_exit (base: atr_filter)

Regla congelada: early_exit si la posición lleva >= 30 min y MFE < +0.5R.
Prueba de INVESTIGACIÓN sobre datasets de diseño: no valida promoción;
el OOS pre-registrado (jul-2026+ o 2023) sigue pendiente.

============================================================================
## Dataset 2024 — `data/processed/MNQ_2024_full_1m_ninjatrader_combined_clean.csv`
2024-01-02 09:30:00 → 2024-12-31 15:59:00 (284 sesiones)

|                     |   daytrading_vwap_liquidity_rr2_no_midday_atr_filter |   daytrading_vwap_liquidity_rr2_no_midday_atr_filter_dynamic_exit_h002 |    delta |
|:--------------------|-----------------------------------------------------:|-----------------------------------------------------------------------:|---------:|
| trades              |                                              258     |                                                                264     |    6     |
| pnl_net             |                                            -2948.06  |                                                              -3128.44  | -180.38  |
| profit_factor       |                                                0.818 |                                                                  0.798 |   -0.02  |
| winrate_pct         |                                               31.78  |                                                                 31.44  |   -0.34  |
| expectancy_r        |                                               -0.12  |                                                                 -0.115 |    0.005 |
| max_drawdown_usd    |                                             3553.2   |                                                               3844.24  |  291.04  |
| max_drawdown_pct    |                                               13.99  |                                                                 15.07  |    1.08  |
| racha_perdedora_max |                                               12     |                                                                 10     |   -2     |
| targets             |                                               71     |                                                                 66     |   -5     |
| stops               |                                              166     |                                                                151     |  -15     |
| session_flatten     |                                               21     |                                                                 17     |   -4     |
| early_exits         |                                                0     |                                                                 30     |   30     |
| early_exit_pnl      |                                                0     |                                                               -603.56  | -603.56  |
| early_exit_r_prom   |                                              nan     |                                                                 -0.226 |  nan     |

**Early exits:** 30 | PnL -603.56 | R promedio -0.226 | MFE prom 0.275R | MAE prom 0.671R

**Contrafactual (destino en la base de los 29 trades cortados):** {'stop': 20, 'target': 5, 'session_flatten': 4} → 17.2% habría llegado a target (límite de la ficha: 20%)

**Beneficio directo de la regla en trades compartidos** (PnL de los early_exits − PnL de esos mismos trades en la base): +185.00 (positivo = la regla ahorró)

**Trades nuevos por re-secuenciación:** 9 (PnL -754.54) | **trades de la base perdidos:** 3 (PnL que tenían: -312.32)

### Por mes

|         |   pnl_base |   pnl_h002 |   expr_base |   expr_h002 |
|:--------|-----------:|-----------:|------------:|------------:|
| 2024-01 |    -504.56 |    -373.56 |      -0.18  |      -0.112 |
| 2024-02 |      55.7  |     339.12 |      -0.015 |       0.121 |
| 2024-03 |    -730.72 |    -517.72 |      -0.354 |      -0.243 |
| 2024-04 |    -331.82 |    -763.82 |      -0.165 |      -0.335 |
| 2024-05 |     488.34 |     714.76 |       0.292 |       0.392 |
| 2024-06 |    -408.88 |    -286.62 |      -0.22  |      -0.165 |
| 2024-07 |     512.34 |     193.76 |       0.277 |       0.135 |
| 2024-08 |    -365.02 |    -641.18 |      -0.144 |      -0.241 |
| 2024-09 |    -756.4  |    -973.98 |      -0.436 |      -0.507 |
| 2024-10 |    -280.98 |    -381.14 |      -0.023 |      -0.084 |
| 2024-11 |    -421.24 |    -232.24 |      -0.212 |      -0.115 |
| 2024-12 |    -204.82 |    -205.82 |      -0.124 |      -0.12  |

### Por hora

|   entry_time |   pnl_base |   pnl_h002 |
|-------------:|-----------:|-----------:|
|           10 |   -2272.64 |   -2354.54 |
|           11 |     -70.58 |     -35.58 |
|           13 |     -84.28 |    -155.86 |
|           14 |     363.04 |     227.14 |
|           15 |    -883.6  |    -809.6  |

### Por régimen causal (volatilidad)

| vol_regime      |   n_h002 |   expR_h002 |   pnl_h002 |   n_base |   expR_base |   pnl_base |
|:----------------|---------:|------------:|-----------:|---------:|------------:|-----------:|
| alta            |      163 |      -0.081 |   -1429.32 |      162 |      -0.091 |   -1486    |
| baja            |       38 |      -0.096 |    -604.12 |       35 |      -0.027 |    -255.8  |
| media           |       53 |      -0.214 |    -867.72 |       51 |      -0.256 |    -978.98 |
| no_clasificable |       10 |      -0.224 |    -227.28 |       10 |      -0.224 |    -227.28 |

### Por régimen causal (tendencia)

| trend_regime      |   n_h002 |   expR_h002 |   pnl_h002 |   n_base |   expR_base |   pnl_base |
|:------------------|---------:|------------:|-----------:|---------:|------------:|-----------:|
| lateral           |       50 |       0.137 |     581.62 |       49 |       0.027 |      96.78 |
| tendencia_alcista |      120 |      -0.161 |   -2116.7  |      116 |      -0.13  |   -1667.22 |
| tendencia_bajista |       94 |      -0.191 |   -1593.36 |       93 |      -0.186 |   -1377.62 |

### Decision Engine: **REJECTED**

- Sin edge: expectancia R no positiva y/o profit factor < 1.0 con muestra suficiente.
- Criterios fallidos: profit_factor, expectancia_r_positiva, drawdown, no_depende_de_pocos_trades, validacion_oos_positiva, sin_contaminacion_de_diseño.

============================================================================
## Dataset 2025_ene_nov — `data/processed/MNQ_2025_01_2025_11_oos_clean.csv`
2025-01-01 10:14:00 → 2025-11-28 13:15:00 (271 sesiones)

|                     |   daytrading_vwap_liquidity_rr2_no_midday_atr_filter |   daytrading_vwap_liquidity_rr2_no_midday_atr_filter_dynamic_exit_h002 |    delta |
|:--------------------|-----------------------------------------------------:|-----------------------------------------------------------------------:|---------:|
| trades              |                                              166     |                                                                169     |    3     |
| pnl_net             |                                              572.86  |                                                                566.96  |   -5.9   |
| profit_factor       |                                                1.059 |                                                                  1.061 |    0.002 |
| winrate_pct         |                                               37.95  |                                                                 37.28  |   -0.67  |
| expectancy_r        |                                                0.061 |                                                                  0.066 |    0.005 |
| max_drawdown_usd    |                                             1323.04  |                                                               1151.84  | -171.2   |
| max_drawdown_pct    |                                                5.26  |                                                                  4.57  |   -0.69  |
| racha_perdedora_max |                                                9     |                                                                 10     |    1     |
| targets             |                                               57     |                                                                 54     |   -3     |
| stops               |                                              101     |                                                                 88     |  -13     |
| session_flatten     |                                                8     |                                                                  7     |   -1     |
| early_exits         |                                                0     |                                                                 20     |   20     |
| early_exit_pnl      |                                                0     |                                                               -546.6   | -546.6   |
| early_exit_r_prom   |                                              nan     |                                                                 -0.341 |  nan     |

**Early exits:** 20 | PnL -546.60 | R promedio -0.341 | MFE prom 0.295R | MAE prom 0.686R

**Contrafactual (destino en la base de los 19 trades cortados):** {'stop': 15, 'target': 3, 'session_flatten': 1} → 15.8% habría llegado a target (límite de la ficha: 20%)

**Beneficio directo de la regla en trades compartidos** (PnL de los early_exits − PnL de esos mismos trades en la base): +290.00 (positivo = la regla ahorró)

**Trades nuevos por re-secuenciación:** 4 (PnL -417.64) | **trades de la base perdidos:** 1 (PnL que tenían: -121.74)

### Por mes

|         |   pnl_base |   pnl_h002 |   expr_base |   expr_h002 |
|:--------|-----------:|-----------:|------------:|------------:|
| 2025-01 |    -296.96 |    -258.96 |      -0.277 |      -0.235 |
| 2025-02 |    -428.76 |    -382.34 |      -0.325 |      -0.259 |
| 2025-03 |     376.2  |     376.2  |       0.653 |       0.653 |
| 2025-04 |     252.36 |     252.36 |       0.473 |       0.473 |
| 2025-05 |    -287.14 |    -194.14 |      -0.118 |      -0.056 |
| 2025-06 |    -190.98 |    -213.98 |      -0.098 |      -0.093 |
| 2025-07 |     -58.72 |    -141.72 |      -0.012 |      -0.096 |
| 2025-08 |     125.56 |     121.24 |       0.192 |       0.218 |
| 2025-09 |     148.02 |      75.02 |       0.059 |       0.028 |
| 2025-10 |     670.98 |     670.98 |       0.572 |       0.572 |
| 2025-11 |     262.3  |     262.3  |       0.349 |       0.349 |

### Por hora

|   entry_time |   pnl_base |   pnl_h002 |
|-------------:|-----------:|-----------:|
|           10 |    -159.94 |    -377.42 |
|           11 |      83.26 |     -31.9  |
|           13 |     844.32 |     925.32 |
|           14 |     -71.3  |     135.44 |
|           15 |    -123.48 |     -84.48 |

### Por régimen causal (volatilidad)

| vol_regime      |   n_h002 |   expR_h002 |   pnl_h002 |   n_base |   expR_base |   pnl_base |
|:----------------|---------:|------------:|-----------:|---------:|------------:|-----------:|
| alta            |       93 |       0.102 |     584.66 |       93 |       0.097 |     552.66 |
| baja            |       28 |       0.047 |     114.48 |       29 |      -0.126 |    -334.26 |
| media           |       45 |       0.077 |     126.56 |       41 |       0.189 |     613.2  |
| no_clasificable |        3 |      -1.031 |    -258.74 |        3 |      -1.031 |    -258.74 |

### Por régimen causal (tendencia)

| trend_regime      |   n_h002 |   expR_h002 |   pnl_h002 |   n_base |   expR_base |   pnl_base |
|:------------------|---------:|------------:|-----------:|---------:|------------:|-----------:|
| lateral           |       34 |      -0.043 |     -34.2  |       34 |      -0.087 |    -156.2  |
| tendencia_alcista |       81 |       0.106 |     466.98 |       79 |       0.098 |     446.72 |
| tendencia_bajista |       54 |       0.076 |     134.18 |       53 |       0.099 |     282.34 |

### Decision Engine: **APPROVED_FOR_RESEARCH**

- Señales positivas (expR > 0, PF >= 1.0) por debajo del nivel paper.
- Criterios fallidos: profit_factor, no_depende_de_pocos_trades, validacion_oos_positiva, sin_contaminacion_de_diseño.

============================================================================
## Dataset 2025_2026_completo — `data/processed/MNQ_2025_01_2026_06_1m_ninjatrader_combined_clean.csv`
2025-01-01 10:14:00 → 2026-06-18 09:30:00 (401 sesiones)

|                     |   daytrading_vwap_liquidity_rr2_no_midday_atr_filter |   daytrading_vwap_liquidity_rr2_no_midday_atr_filter_dynamic_exit_h002 |    delta |
|:--------------------|-----------------------------------------------------:|-----------------------------------------------------------------------:|---------:|
| trades              |                                              233     |                                                                240     |    7     |
| pnl_net             |                                             3446.46  |                                                               3424.92  |  -21.54  |
| profit_factor       |                                                1.271 |                                                                  1.279 |    0.008 |
| winrate_pct         |                                               42.06  |                                                                 41.25  |   -0.81  |
| expectancy_r        |                                                0.166 |                                                                  0.165 |   -0.001 |
| max_drawdown_usd    |                                             1323.04  |                                                               1151.84  | -171.2   |
| max_drawdown_pct    |                                                5.26  |                                                                  4.57  |   -0.69  |
| racha_perdedora_max |                                                9     |                                                                 10     |    1     |
| targets             |                                               85     |                                                                 82     |   -3     |
| stops               |                                              131     |                                                                115     |  -16     |
| session_flatten     |                                               17     |                                                                 14     |   -3     |
| early_exits         |                                                0     |                                                                 29     |   29     |
| early_exit_pnl      |                                                0     |                                                               -727.82  | -727.82  |
| early_exit_r_prom   |                                              nan     |                                                                 -0.303 |  nan     |

**Early exits:** 29 | PnL -727.82 | R promedio -0.303 | MFE prom 0.298R | MAE prom 0.68R

**Contrafactual (destino en la base de los 27 trades cortados):** {'stop': 20, 'session_flatten': 4, 'target': 3} → 11.1% habría llegado a target (límite de la ficha: 20%)

**Beneficio directo de la regla en trades compartidos** (PnL de los early_exits − PnL de esos mismos trades en la base): +493.00 (positivo = la regla ahorró)

**Trades nuevos por re-secuenciación:** 8 (PnL -636.28) | **trades de la base perdidos:** 1 (PnL que tenían: -121.74)

### Por mes

|         |   pnl_base |   pnl_h002 |   expr_base |   expr_h002 |
|:--------|-----------:|-----------:|------------:|------------:|
| 2025-01 |    -296.96 |    -258.96 |      -0.277 |      -0.235 |
| 2025-02 |    -428.76 |    -382.34 |      -0.325 |      -0.259 |
| 2025-03 |     376.2  |     376.2  |       0.653 |       0.653 |
| 2025-04 |     252.36 |     252.36 |       0.473 |       0.473 |
| 2025-05 |    -287.14 |    -194.14 |      -0.118 |      -0.056 |
| 2025-06 |    -190.98 |    -213.98 |      -0.098 |      -0.093 |
| 2025-07 |     -58.72 |    -141.72 |      -0.012 |      -0.096 |
| 2025-08 |     125.56 |     121.24 |       0.192 |       0.218 |
| 2025-09 |     148.02 |      75.02 |       0.059 |       0.028 |
| 2025-10 |     670.98 |     670.98 |       0.572 |       0.572 |
| 2025-11 |     262.3  |     262.3  |       0.349 |       0.349 |
| 2025-12 |     554.24 |     538.6  |       0.33  |       0.275 |
| 2026-01 |    -102.12 |     -82.12 |      -0.179 |      -0.156 |
| 2026-02 |    -124.06 |     -42.06 |      -0.305 |      -0.186 |
| 2026-03 |     224.84 |     224.84 |       1.972 |       1.972 |
| 2026-04 |    1208.56 |    1106.56 |       0.86  |       0.784 |
| 2026-05 |     898.62 |     898.62 |       0.925 |       0.925 |
| 2026-06 |     213.52 |     213.52 |       0.306 |       0.306 |

### Por hora

|   entry_time |   pnl_base |   pnl_h002 |
|-------------:|-----------:|-----------:|
|           10 |    1905.22 |    1723.84 |
|           11 |      83.26 |     -31.9  |
|           13 |     685.2  |     766.2  |
|           14 |     473.74 |     681.74 |
|           15 |     299.04 |     285.04 |

### Por régimen causal (volatilidad)

| vol_regime      |   n_h002 |   expR_h002 |   pnl_h002 |   n_base |   expR_base |   pnl_base |
|:----------------|---------:|------------:|-----------:|---------:|------------:|-----------:|
| alta            |      121 |       0.205 |    2138.42 |      121 |       0.186 |    1946.42 |
| baja            |       51 |       0.185 |     993.18 |       48 |       0.165 |     854.08 |
| media           |       65 |       0.129 |     552.06 |       61 |       0.185 |     904.7  |
| no_clasificable |        3 |      -1.031 |    -258.74 |        3 |      -1.031 |    -258.74 |

### Por régimen causal (tendencia)

| trend_regime      |   n_h002 |   expR_h002 |   pnl_h002 |   n_base |   expR_base |   pnl_base |
|:------------------|---------:|------------:|-----------:|---------:|------------:|-----------:|
| lateral           |       49 |       0.098 |     574.52 |       48 |       0.065 |     413.1  |
| tendencia_alcista |      114 |       0.243 |    2439.62 |      111 |       0.237 |    2314.52 |
| tendencia_bajista |       77 |       0.091 |     410.78 |       74 |       0.125 |     718.84 |

### Decision Engine: **BLOCKED_FOR_PAPER**

- Performance de nivel paper, pero la validación no está limpia o completa (OOS/contaminación/dependencia sin verificar o fallidos).
- Criterios fallidos: validacion_oos_positiva, sin_contaminacion_de_diseño.