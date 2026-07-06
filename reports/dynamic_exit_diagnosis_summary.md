# Diagnóstico H002 — salidas dinámicas in-trade

- **Trades analizados:** 287 (reporte: `reports/20260704_134905_MNQ_daytrading_vwap_liquidity_rr2_no_midday`)
- **Datos:** `data/processed/MNQ_2025_01_2026_06_1m_ninjatrader_combined_clean.csv`
- **Período:** 2025-01-06 10:13:00 → 2026-06-15 10:53:00
- **Advertencia:** trades de la familia H001 sobre datos YA VISTOS:
  este diagnóstico sirve para DISEÑAR H002, no para validarla.

## Recorrido por tipo de salida

| salida          |   n |   dur_mediana_min |   mfe_r_mediana |   mae_r_mediana |   pct_alcanza_0.25R |   pct_alcanza_0.5R |   pct_alcanza_1.0R |   min_a_0.5R_mediana |
|:----------------|----:|------------------:|----------------:|----------------:|--------------------:|-------------------:|-------------------:|---------------------:|
| session_flatten |  27 |              78   |          1.039  |          0.569  |               100   |               92.6 |               51.9 |                   21 |
| stop            | 164 |              18   |          0.458  |          1.1125 |                66.5 |               46.3 |               20.7 |                    4 |
| target          |  96 |              39.5 |          2.0815 |          0.306  |               100   |              100   |              100   |                    3 |

## Regla hipotética: ¿alcanzó +0.5R dentro de la ventana T?

(solo trades aún abiertos en T; es lo que vería una regla de salida en T)

|   ventana_min | grupo            |   n |   winrate_final_pct |   r_final_promedio |   pct_termina_en_stop |
|--------------:|:-----------------|----:|--------------------:|-------------------:|----------------------:|
|            10 | alcanzó +0.5R    | 125 |                58.4 |              0.66  |                  40.8 |
|            10 | NO alcanzó +0.5R |  99 |                33.3 |             -0.167 |                  59.6 |
|            15 | alcanzó +0.5R    | 124 |                58.9 |              0.656 |                  39.5 |
|            15 | NO alcanzó +0.5R |  70 |                32.9 |             -0.205 |                  58.6 |
|            20 | alcanzó +0.5R    | 113 |                60.2 |              0.675 |                  38.1 |
|            20 | NO alcanzó +0.5R |  58 |                34.5 |             -0.16  |                  55.2 |
|            30 | alcanzó +0.5R    | 110 |                65.5 |              0.815 |                  29.1 |
|            30 | NO alcanzó +0.5R |  35 |                22.9 |             -0.564 |                  71.4 |
|            45 | alcanzó +0.5R    |  78 |                62.8 |              0.682 |                  29.5 |
|            45 | NO alcanzó +0.5R |  15 |                26.7 |             -0.466 |                  60   |
|            60 | alcanzó +0.5R    |  62 |                61.3 |              0.637 |                  32.3 |
|            60 | NO alcanzó +0.5R |   7 |                28.6 |             -0.332 |                  57.1 |

## Lo mismo con umbral +0.25R

|   ventana_min | grupo             |   n |   winrate_final_pct |   r_final_promedio |   pct_termina_en_stop |
|--------------:|:------------------|----:|--------------------:|-------------------:|----------------------:|
|            10 | alcanzó +0.25R    | 170 |                51.8 |              0.449 |                  45.9 |
|            10 | NO alcanzó +0.25R |  54 |                33.3 |             -0.193 |                  59.3 |
|            15 | alcanzó +0.25R    | 159 |                54.1 |              0.505 |                  42.1 |
|            15 | NO alcanzó +0.25R |  35 |                28.6 |             -0.381 |                  65.7 |
|            20 | alcanzó +0.25R    | 147 |                56.5 |              0.545 |                  39.5 |
|            20 | NO alcanzó +0.25R |  24 |                20.8 |             -0.542 |                  70.8 |
|            30 | alcanzó +0.25R    | 132 |                59.8 |              0.617 |                  34.8 |
|            30 | NO alcanzó +0.25R |  13 |                 7.7 |             -0.886 |                  84.6 |
|            45 | alcanzó +0.25R    |  91 |                58.2 |              0.53  |                  33   |
|            45 | NO alcanzó +0.25R |   2 |                 0   |             -1.024 |                 100   |
|            60 | alcanzó +0.25R    |  68 |                58.8 |              0.561 |                  33.8 |
|            60 | NO alcanzó +0.25R |   1 |                 0   |             -1.019 |                 100   |

## Otras preguntas de la ficha

- **¿Los flatten son trades que no expandieron?** MFE mediana de los session_flatten: 1.04R | expansión mediana del rango del día durante el trade: 0.0 pts (vs 38.5 pts en targets).
- **¿Volver al VWAP después de entrar anticipa el fallo?** Winrate con retorno al VWAP: 17.0% (n=135) vs sin retorno: 60.5% (n=152).
- **¿La falta de expansión explica pérdidas?** Expansión mediana del rango durante el trade — targets: 38.5 pts | stops: 0.0 pts | flatten: 0.0 pts.

## Nota metodológica

- El recorrido usa high/low de cada barra 1m incluida la de salida.
- La curva de ventanas se reporta COMPLETA a propósito: este documento no
  elige el parámetro. La elección (valores redondos, lejos del óptimo) es
  trabajo de la ficha H002 al pasar a DESIGNED, y su validación exige el
  OOS virgen declarado (jul-2026+ o 2023).
