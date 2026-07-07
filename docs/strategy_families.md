# Strategy Families

Este documento registra las familias investigables del Strategy Lab. Una
familia no es una promesa de rentabilidad ni una autorizacion para paper/live.
Es una hipotesis de mercado con parametros limitados, filtros y robustez.

Las familias marcadas como scaffolding estan registradas para investigacion
futura, pero no tienen estrategia real implementada. El Strategy Lab las lista
y las descarta como `SCAFFOLD_ONLY` hasta que exista una implementacion con
tests.

## Limitaciones de volumen

El dataset actual usa OHLCV de 1 minuto. Las familias de volumen solo pueden
usar volumen de vela, volumen relativo, compresion/expansion, spikes y
estadisticas rolling calculadas sin lookahead.

No hay bid/ask, delta real, footprint, DOM, volumen por precio exacto ni order
flow real. Por eso ninguna familia debe interpretar `volume` como absorcion
real, agresion compradora/vendedora o delta institucional. Es una proxy
estadistica y debe validarse con Robustness Engine, Decision Engine y OOS.

El volumen gaussiano significa normalizar `volume` con media movil, desviacion
estandar movil y z-score:

```text
volume_zscore = (volume_actual - rolling_mean_volume) / rolling_std_volume
```

`rolling_mean_volume` y `rolling_std_volume` deben calcularse con datos
pasados, usando `shift(1)` o una tecnica equivalente.

## Familias conectadas a estrategias existentes

### rr2_atr_filter

- Hipotesis: pullback a valor con volatilidad minima mejora la familia RR2.
- Deberia funcionar: sesiones RTH con volatilidad suficiente y tendencia limpia.
- Deberia fallar: cinta muerta, chop de mediodia y breaks sin continuidad.
- Riesgo de overfitting: medio; la Fase 8 ya mostro fragilidad.
- Parametros: `min_atr20_points`, `rel_volume_threshold`,
  `max_vwap_distance_points`, `min_slope_points`.

### base_vwap_ema

- Hipotesis: pullback a valor alineado con EMAs y volumen relativo.
- Deberia funcionar: tendencias intradia ordenadas con pullbacks poco profundos.
- Deberia fallar: rangos estrechos o cambios violentos de regimen.
- Riesgo de overfitting: medio si se expande demasiado la grilla.
- Parametros: `rel_volume_threshold`, `pullback_lookback`, `rr`.

### vwap_mean_reversion

- Hipotesis: operar cerca de VWAP reduce perseguir precio extendido.
- Deberia funcionar: mercado rota alrededor de valor con rechazo claro.
- Deberia fallar: dias de tendencia persistente donde VWAP no actua como iman.
- Riesgo de overfitting: medio; requiere validation/OOS.
- Parametros: `max_vwap_distance_points_near`, `rel_volume_threshold`,
  `rejection_close_pct`.

### trend_pullback_ema

- Hipotesis: la continuidad mejora si las EMAs estan ordenadas.
- Deberia funcionar: tendencias limpias con retrocesos a medias.
- Deberia fallar: rangos laterales y reversiones bruscas.
- Riesgo de overfitting: medio.
- Parametros: `pullback_lookback`, `rr`.

### pullback_to_vwap_trend

- Hipotesis: pullback a VWAP con pendiente puede continuar.
- Deberia funcionar: tendencias con pullbacks ordenados a VWAP.
- Deberia fallar: VWAP plana, rangos y falsa continuacion.
- Riesgo de overfitting: medio.
- Parametros: `max_vwap_distance_points`, `min_slope_points`,
  `rel_volume_threshold`.

### ema_trend_continuation

- Hipotesis: alineacion de EMAs filtra operaciones contra tendencia.
- Deberia funcionar: sesiones direccionales con volumen estable.
- Deberia fallar: mean reversion fuerte o EMAs cruzandose constantemente.
- Riesgo de overfitting: medio.
- Parametros: `ema_mid`, `rel_volume_threshold`.

## Familias en scaffolding

### opening_range_breakout

- Hipotesis: ruptura del rango inicial captura expansion temprana.
- Deberia funcionar: compresion inicial y expansion direccional.
- Deberia fallar: falsos breaks y rotacion dentro del rango inicial.
- Riesgo de overfitting: alto hasta tener estrategia y tests.
- Parametros previstos: `opening_range_minutes`, `breakout_buffer_ticks`,
  `min_volume_ratio`.

### opening_range_reversal

- Hipotesis: un breakout fallido del rango inicial vuelve a valor.
- Deberia funcionar: open emocional que falla y revierte al VWAP.
- Deberia fallar: dias de trend desde apertura.
- Riesgo de overfitting: alto.
- Parametros previstos: `opening_range_minutes`, `failure_minutes`,
  `reclaim_buffer_ticks`.

### volatility_expansion_breakout

- Hipotesis: expansion de rango con volumen confirma desplazamiento.
- Deberia funcionar: volatilidad comprimida seguida de vela expansiva.
- Deberia fallar: spikes aislados sin follow-through.
- Riesgo de overfitting: alto.
- Parametros previstos: `atr_window`, `atr_expansion_ratio`, `volume_ratio`.

### regime_aware_rr2

- Hipotesis: RR2 solo deberia operar en regimenes favorables.
- Deberia funcionar: regimen de tendencia/volatilidad confirmado.
- Deberia fallar: regimen lateral o transicion no clasificada.
- Riesgo de overfitting: alto si se eligen regimenes post-hoc.
- Parametros previstos: `allowed_regimes`, `min_regime_confidence`.

### vwap_reclaim

- Hipotesis: recuperar VWAP con volumen marca cambio de control.
- Deberia funcionar: falso breakdown/breakout alrededor de VWAP.
- Deberia fallar: VWAP deja de actuar como referencia.
- Riesgo de overfitting: alto.
- Parametros previstos: `reclaim_window`, `volume_ratio`,
  `max_distance_after_reclaim`.

### previous_day_high_low_breakout

- Hipotesis: high/low del dia previo concentra liquidez y continuacion.
- Deberia funcionar: ruptura limpia con aceptacion fuera del nivel.
- Deberia fallar: barridas de liquidez que revierten rapido.
- Riesgo de overfitting: alto.
- Parametros previstos: `level_buffer_ticks`, `confirmation_bars`,
  `volume_ratio`.

### previous_day_high_low_reversal

- Hipotesis: barridas del dia previo pueden revertir al rango.
- Deberia funcionar: stop run y rechazo fuerte del nivel.
- Deberia fallar: breakout con aceptacion real fuera del nivel.
- Riesgo de overfitting: alto.
- Parametros previstos: `rejection_window`, `level_buffer_ticks`,
  `target_to_vwap`.

### range_expansion_continuation

- Hipotesis: expansion amplia con cierre fuerte tiende a continuar.
- Deberia funcionar: velas de expansion con participacion creciente.
- Deberia fallar: climax bars y agotamiento.
- Riesgo de overfitting: alto.
- Parametros previstos: `range_window`, `expansion_ratio`, `close_strength`.

### failed_breakout_reversal

- Hipotesis: falta de follow-through despues de romper un nivel crea reversal.
- Deberia funcionar: ruptura, rechazo y retorno dentro del rango.
- Deberia fallar: breakouts reales con aceptacion.
- Riesgo de overfitting: alto.
- Parametros previstos: `failure_bars`, `level_buffer_ticks`,
  `reversal_confirmation`.

### high_volume_reversal

- Hipotesis: volumen climatico cerca de extremos puede indicar absorcion.
- Deberia funcionar: spikes de volumen con rechazo de precio.
- Deberia fallar: volumen alto de continuacion institucional.
- Riesgo de overfitting: alto.
- Parametros previstos: `volume_zscore`, `wick_ratio`, `location_filter`.

### low_volatility_breakout

- Hipotesis: compresion de volatilidad precede expansion direccional.
- Deberia funcionar: ATR bajo y rango estrecho antes del impulso.
- Deberia fallar: baja volatilidad persistente sin expansion.
- Riesgo de overfitting: alto.
- Parametros previstos: `compression_window`, `atr_percentile`,
  `breakout_buffer_ticks`.

### session_momentum_breakout

- Hipotesis: momentum temprano puede extenderse si hay volumen.
- Deberia funcionar: sesiones direccionales con impulso inicial.
- Deberia fallar: aperturas con reversals rapidos.
- Riesgo de overfitting: alto.
- Parametros previstos: `momentum_window`, `min_session_return`,
  `volume_ratio`.

## Familias de volumen OHLCV

En Fase 10, `relative_volume_breakout`, `volume_climax_reversal`,
`volume_dry_up_breakout`, `opening_range_volume_breakout` y
`vwap_volume_reclaim` pasan a ejecutables con estrategias reales OHLCV-only y
tests. Las demas familias de esta seccion siguen como scaffolding hasta tener
implementacion propia.

### relative_volume_breakout

- Hipotesis: una ruptura con volumen relativo alto tiene mas probabilidad de
  aceptacion.
- Deberia funcionar: rango definido, compresion inicial y expansion con
  volumen creciente.
- Deberia fallar: rupturas sin follow-through, news whipsaw y spikes aislados.
- Estado: ejecutable desde Fase 10.
- Riesgo de overfitting: alto; requiere validation/OOS.
- Parametros: `rel_volume_threshold`, `volume_window`, `breakout_lookback`,
  `rr`.

### volume_climax_reversal

- Hipotesis: un pico de volumen con rechazo de precio puede indicar
  agotamiento de corto plazo.
- Deberia funcionar: extremos de rango/VWAP extendidos con rechazo claro.
- Deberia fallar: volumen alto de continuacion y breakouts aceptados.
- Estado: ejecutable desde Fase 10.
- Riesgo de overfitting: alto por sensibilidad a umbrales de spike/rechazo.
- Parametros: `spike_threshold`, `volume_window`, `rejection_close_pct`, `rr`.

### volume_dry_up_breakout

- Hipotesis: volumen seco previo puede preceder una expansion direccional.
- Deberia funcionar: compresion de rango, baja participacion y ruptura con
  volumen creciente.
- Deberia fallar: baja liquidez persistente o expansion sin continuidad.
- Estado: ejecutable desde Fase 10.
- Riesgo de overfitting: alto por elegir ventanas de compresion post-hoc.
- Parametros: `dry_up_threshold`, `rel_volume_threshold`, `volume_window`,
  `breakout_lookback`.

### volume_expansion_continuation

- Hipotesis: rango amplio con volumen creciente puede confirmar continuidad.
- Deberia funcionar: desplazamientos con cierre fuerte y participacion
  creciente.
- Deberia fallar: barras climax de agotamiento o extension lejos de valor.
- Estado: scaffolding.
- Riesgo de overfitting: alto si se ajusta el ATR/volumen al periodo probado.
- Parametros previstos: `rel_volume_threshold`, `min_atr20_points`, `rr`.

### high_volume_failed_breakout

- Hipotesis: una ruptura con alto volumen que no sostiene aceptacion puede
  revertir al rango.
- Deberia funcionar: barrida de nivel, retorno rapido al rango y rechazo.
- Deberia fallar: ruptura real con aceptacion y continuacion.
- Estado: scaffolding.
- Riesgo de overfitting: alto por definicion de fallo y ventana de confirmacion.
- Parametros previstos: `rel_volume_threshold`, `failure_bars`,
  `rejection_close_pct`.

### low_volume_pullback_continuation

- Hipotesis: retrocesos de bajo volumen pueden ser pausas dentro de tendencia.
- Deberia funcionar: tendencia clara, pullback ordenado y reanudacion con
  volumen normal/alto.
- Deberia fallar: tendencias agotadas o pullbacks que pasan a reversal.
- Estado: scaffolding.
- Riesgo de overfitting: alto por dependencia de clasificacion de tendencia.
- Parametros previstos: `dry_up_threshold`, `pullback_lookback`, `rr`.

### vwap_volume_reclaim

- Hipotesis: recuperar VWAP con volumen relativo alto puede marcar cambio de
  control.
- Deberia funcionar: falso quiebre alrededor de VWAP y aceptacion posterior.
- Deberia fallar: VWAP plana, rangos estrechos o reclaim sin participacion.
- Estado: ejecutable desde Fase 10.
- Riesgo de overfitting: alto por distancia a VWAP y umbral de volumen.
- Parametros: `rel_volume_threshold`, `max_vwap_distance_points`,
  `volume_window`, `rr`.

### opening_range_volume_breakout

- Hipotesis: la ruptura del opening range necesita volumen superior al promedio.
- Deberia funcionar: open con rango claro y expansion direccional.
- Deberia fallar: aperturas erraticas y stop runs sin aceptacion.
- Estado: ejecutable desde Fase 10.
- Riesgo de overfitting: alto si se ajusta el rango inicial al dataset.
- Parametros: `opening_range_minutes`, `rel_volume_threshold`, `volume_window`,
  `rr`.

### volume_spike_mean_reversion

- Hipotesis: un spike de volumen lejos de VWAP puede indicar agotamiento.
- Deberia funcionar: extension de precio, spike de volumen y rechazo claro.
- Deberia fallar: spikes que inician tendencia o news con continuidad.
- Estado: scaffolding.
- Riesgo de overfitting: alto por umbrales de extension y rechazo.
- Parametros previstos: `spike_threshold`, `max_vwap_distance_points`,
  `rejection_close_pct`.

### volume_trend_confirmation

- Hipotesis: operar a favor de tendencia solo si el volumen confirma
  participacion.
- Deberia funcionar: tendencias con EMAs/VWAP alineadas y volumen normal-alto.
- Deberia fallar: avances con participacion decreciente o climax final.
- Estado: scaffolding.
- Riesgo de overfitting: alto si se usa volumen para filtrar demasiado.
- Parametros previstos: `rel_volume_threshold`, `volume_window`, `rr`.

## Familias gaussian_volume

En Fase 10, `gaussian_volume_breakout`, `gaussian_volume_reversal` y
`gaussian_volume_dry_up_breakout` pasan a ejecutables. El z-score de volumen
sigue siendo una proxy estadistica OHLCV y no reemplaza order flow real.

### gaussian_volume_breakout

- Hipotesis: una ruptura con `volume_zscore` alto tiene mas probabilidad de
  aceptacion.
- Deberia funcionar: rango definido y volumen estadisticamente alto no
  climatico.
- Deberia fallar: spikes aislados o barras de agotamiento.
- Estado: ejecutable desde Fase 10.
- Riesgo de overfitting: alto por umbrales de z-score y ventanas.
- Parametros: `volume_window`, `volume_zscore_threshold`,
  `breakout_lookback`, `rr`.

### gaussian_volume_reversal

- Hipotesis: volumen estadisticamente extremo con rechazo puede revertir.
- Deberia funcionar: z-score alto, rechazo y cierre contrario al impulso.
- Deberia fallar: continuacion fuerte con volumen persistentemente alto.
- Estado: ejecutable desde Fase 10.
- Riesgo de overfitting: alto por definicion de rechazo y nivel extremo.
- Parametros: `volume_window`, `volume_zscore_threshold`,
  `rejection_close_pct`, `rr`.

### gaussian_volume_climax

- Hipotesis: z-score de volumen muy alto puede detectar posible climax.
- Deberia funcionar: extremos de precio con `volume_zscore` > 2.0/2.5.
- Deberia fallar: sesiones de tendencia donde el volumen extremo confirma
  aceptacion.
- Estado: scaffolding.
- Riesgo de overfitting: alto por seleccionar el umbral despues del resultado.
- Parametros previstos: `volume_window`, `volume_zscore_threshold`,
  `rejection_close_pct`.

### gaussian_volume_dry_up_breakout

- Hipotesis: z-score bajo previo puede preceder una expansion con volumen.
- Deberia funcionar: compresion estadistica y ruptura con z-score positivo.
- Deberia fallar: compresion que no expande o baja liquidez persistente.
- Estado: ejecutable desde Fase 10.
- Riesgo de overfitting: alto por combinar dos umbrales de z-score.
- Parametros: `volume_window`, `dry_up_zscore_threshold`,
  `volume_zscore_threshold`, `breakout_lookback`.

### gaussian_volume_trend_confirmation

- Hipotesis: la tendencia mejora cuando el volumen supera su media reciente.
- Deberia funcionar: tendencia alineada y volumen positivo en impulsos.
- Deberia fallar: tendencia agotada o volumen extremo de climax.
- Estado: scaffolding.
- Riesgo de overfitting: alto por filtrar trades hasta dejar pocos casos.
- Parametros previstos: `volume_window`, `volume_zscore_threshold`, `rr`.

### gaussian_volume_failed_breakout

- Hipotesis: un breakout con z-score extremo que falla puede volver al rango.
- Deberia funcionar: ruptura, fallo rapido y retorno con rechazo.
- Deberia fallar: breakout aceptado fuera del nivel.
- Estado: scaffolding.
- Riesgo de overfitting: alto por ventana de fallo y umbral extremo.
- Parametros previstos: `volume_window`, `volume_zscore_threshold`,
  `failure_bars`.

### gaussian_volume_mean_reversion

- Hipotesis: z-score extremo lejos de VWAP puede senalar exhaustacion.
- Deberia funcionar: extension a distancia de VWAP con rechazo.
- Deberia fallar: tendencia que acepta nuevos niveles y no vuelve a valor.
- Estado: scaffolding.
- Riesgo de overfitting: alto por distancia a VWAP y z-score.
- Parametros previstos: `volume_window`, `volume_zscore_threshold`,
  `max_vwap_distance_points`.

### gaussian_volume_expansion_continuation

- Hipotesis: expansion de rango con volumen estadisticamente alto puede
  continuar.
- Deberia funcionar: vela expansiva, cierre fuerte y z-score alto no climatico.
- Deberia fallar: barra final de climax o movimiento extendido.
- Estado: scaffolding.
- Riesgo de overfitting: alto por elegir ventana/umbral sobre el historico.
- Parametros previstos: `volume_window`, `volume_zscore_threshold`, `rr`.

## Regla final

Una familia puede tener PnL positivo y aun asi quedar descartada si falla
drawdown, Monte Carlo, Bootstrap, stress de costos, dependencia de pocos
ganadores o Decision Engine. Si no hay robustez, no hay paper.
