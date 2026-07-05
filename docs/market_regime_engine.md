# Market Regime Engine (Quant Brain, Fase 3)

**Módulo:** `src/nqbot/regime/` (`models.py`, `features.py`, `classifier.py`)
**Exploración:** `scripts/analyze_market_regimes.py --data <csv>`
**Tests:** `tests/test_regime_engine.py`

## Qué calcula

Para cada barra intradía, dos capas:

**Features causales** (todas conocidas al cierre de la barra):

| Feature | Descripción |
|---|---|
| `atr_prev` | ATR (true range medio) de las últimas 20 barras cerradas |
| `range_so_far` | Rango acumulado del día hasta la barra actual |
| `or_high/or_low/or_size` | Rango inicial de 30 min (NaN hasta completarse) |
| `expansion_ratio` | Rango acumulado / rango inicial |
| `vwap`, `vwap_slope` | VWAP de sesión y su pendiente (10 barras) |
| `ema200`, `ema200_slope` | EMA200 y su pendiente (30 barras) |
| `dist_vwap`, `dist_ema200` | Distancia del cierre a cada referencia |
| `above_vwap`, `above_ema200` | Posición del precio |
| `rel_volume` | Volumen relativo (20 barras) |
| `making_hh`, `making_ll` | Máximos/mínimos crecientes o decrecientes (ventanas de 15) |

**Etiquetas de régimen** (enums en `models.py`):

| Etiqueta | Valores | Regla |
|---|---|---|
| `vol_regime` | baja / media / alta | ATR previo vs cuantiles 33/67 del ATR mediano de las últimas 20 sesiones **completadas** |
| `trend_regime` | lateral / tendencia_alcista / tendencia_bajista | posición vs EMA200 y VWAP + signo de la pendiente de EMA200 |
| `expansion_regime` | compresion / neutral / expansion | ratio ≤ 1.2 / intermedio / ≥ 2.0 |
| `directional_bias` | alcista / bajista / neutral | cierre vs VWAP y vs apertura del día |

Para trades: `label_trades(trades, labeled)` une cada trade con el régimen
de su barra de señal y agrega `trade_vs_bias` (a_favor / en_contra / neutral).

## Por qué NO usa información futura

1. **Solo operaciones hacia atrás**: rolling, cummax/cummin por sesión y
   diffs. Nada centrado, nada del día completo, nada del dataset completo.
2. **Volatilidad relativa al pasado, no al dataset**: la lección clave de
   los diagnósticos del ciclo RR2. Terciles del dataset completo usan la
   distribución futura (lookahead sutil). Acá el umbral de cada sesión sale
   de las 20 sesiones ANTERIORES (con `shift(1)`: la sesión en curso jamás
   participa de su propio umbral).
3. **Prefiere no etiquetar antes que inventar**: warmup de indicadores, OR
   incompleto o historia insuficiente ⇒ etiqueta `None` ("no clasificable").
4. **Verificado por test de estabilidad de prefijo**: clasificar un dataset
   truncado a mitad de sesión produce exactamente los mismos features y
   etiquetas que clasificar el dataset completo, en el tramo común. Si
   cualquier cálculo mirara el futuro, ese test falla.

Advertencia honesta (del diagnóstico de régimen del ciclo RR2): las
etiquetas causales son más débiles que las etiquetas de cierre de día — el
"día tendencial" muchas veces se confirma después. Este motor expone lo que
se puede saber EN el momento; no promete adivinar el día.

## Cómo se integra con futuros backtests

- **Evaluation Engine (roadmap)**: los validadores y comparadores podrán
  llamar a `classify_regimes` sobre el mismo dataset del backtest y a
  `label_trades` sobre los trades, para que TODO reporte incluya métricas
  por régimen (expR en tendencia vs lateral, en vol alta vs baja, a favor
  vs contra el sesgo) sin código ad-hoc.
- **Hypothesis Engine (Fase 4)**: las fichas de hipótesis pueden referirse a
  regímenes con vocabulario estándar ("solo en vol_regime != baja") en vez
  de redefinir features en cada experimento.
- **Estrategias futuras (Fase 5+)**: una estrategia puede consumir las
  etiquetas como contexto causal (p.ej. gestión de salida distinta en
  compresión), siempre vía hipótesis registrada — el motor no decide nada.

## Cómo ayuda al Quant Brain a diagnosticar

El ciclo RR2 necesitó scripts ad-hoc para descubrir que su edge vivía en
tendencia/expansión y moría en lateral/vol baja. Con este módulo, esa
pregunta — *¿dónde gana y dónde pierde esta estrategia?* — se responde de
serie para cualquier estrategia futura, con vocabulario uniforme y
comparable entre experimentos. Además separa formalmente lo *conocible en
el momento* (features causales) de lo *solo visible a posteriori*
(etiquetas de día completo de los diagnósticos), que es exactamente la
frontera donde el ciclo anterior encontró el límite de los filtros de
entrada.

## Configuración

`RegimeConfig` (defaults redondos, no optimizados): ventanas de ATR/pendientes/
estructura/volumen, lookback de volatilidad (20 sesiones, mínimo 10) y los
ratios de compresión (1.2) y expansión (2.0). Cambiar umbrales para favorecer
un resultado = curve fitting; cualquier cambio pasa por el decision log.
