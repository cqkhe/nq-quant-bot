# Registro de decisiones de estrategia (decision log)

Documento de gobierno del proyecto: qué estrategia es referencia, qué está en
evaluación, con qué evidencia y bajo qué criterio se decide. Cada entrada es
inmutable: las decisiones nuevas se agregan, no se reescriben.

---

## 2026-07-04 — Candidata `no_midday` | Estado: **PENDIENTE DE VALIDACIÓN OUT-OF-SAMPLE**

### Roles vigentes

| Estrategia | Rol |
|---|---|
| `daytrading_vwap_liquidity_rr2` | **Benchmark** — estrategia original de referencia. No se modifica. |
| `daytrading_vwap_liquidity_rr2_no_midday` | **Candidata** — única variante en evaluación formal. |

Las demás variantes (`longs_only`, `morning_only`, `no_midday_longs_only`)
quedan como experimentos archivados: no están en evaluación.

### Motivo del filtro

La candidata evita abrir operaciones entre **11:00 y 12:59 ET**, franja donde
el análisis del backtest real mostró pérdidas sistemáticas (33 trades,
-$573, winrate 21-32%). El mecanismo es microestructural y conocido: mediodía
sin participación institucional = chop sin seguimiento. Es un filtro binario
de una sola decisión (baja capacidad de sobreajuste) aplicado SOBRE las
señales de la original, sin tocar la lógica de entrada.

### Resultado in-sample (dic-2025 → jun-2026, 113 sesiones, MNQ 1m real)

| Métrica | Original | no_midday |
|---|---|---|
| Trades | 89 | 59 |
| PnL neto | +$1,452 | +$2,271 |
| Profit factor | 1.31 | 1.83 |
| Expectancia | +0.15 R | +0.38 R |
| Drawdown máximo | $1,184 | $589 |
| Racha perdedora máxima | 10 | 4 |

### Evidencia (detalle en `reports/no_midday_validation_summary.txt`)

**A favor:**
- La expectancia R mejora en **6 de 6 bloques temporales**, incluidos los
  meses perdedores (dic+ene pasa de -$563 a +$25). El único bloque donde el
  PnL empeora es abril, el mejor mes del original — cede upside en el régimen
  fácil, arregla el difícil. Forma opuesta a la del curve fitting típico.
- Descomposición exacta del +$819: 70% por evitar las pérdidas sistemáticas
  del mediodía; no por concentración en pocos ganadores (PnL sin el top-5
  sube de $264 a $1,069; mediana de R pasa de -1.02 a +0.31).

**En contra:**
- El filtro se derivó de este mismo dataset (sesgo de selección).
- Test de signos semanal no significativo (10W/7L, p = 0.315).
- Los 4 trades nuevos por slot libre (+$330, 75% winrate) pueden ser suerte.

### Advertencia

**Falta la validación out-of-sample.** Todo lo anterior se midió sobre los
mismos datos que originaron la hipótesis. Nada de este documento constituye
evidencia suficiente para operar la candidata.

### Criterio de promoción — PRE-REGISTRADO (no renegociable a posteriori)

Sobre datos que el filtro nunca vio (julio-2026 en adelante, o históricos
2024-2025 no usados), corridos sin cambiar ningún parámetro:

1. `expR(no_midday) > expR(original)` en el período completo nuevo.
2. Drawdown máximo de la candidata no peor que el de la original.
3. Muestra mínima orientativa: ≥ 30 trades de la candidata (si hay menos,
   el veredicto queda provisional y se junta más historia).

Si no cumple → la candidata se descarta y se registra acá. Si cumple → se
promueve a estrategia por defecto y se registra acá.

### Regla vigente

**No se optimizan más parámetros ni se crean variantes nuevas** hasta
completar esta validación con datos no usados.

### Cómo ejecutar la validación

```bash
# 1. importar los datos nuevos (mismo pipeline de siempre)
python scripts/import_data.py --input data/raw/ARCHIVO_NUEVO.txt

# 2. correr la validación head-to-head
python scripts/validate_no_midday.py --data data/processed/ARCHIVO_NUEVO_clean.csv

# genera: reports/out_of_sample_validation.csv
#         reports/out_of_sample_validation_summary.txt
```

El script avisa si el rango de fechas del archivo se solapa con el período
in-sample (dic-2025 → jun-2026): en ese caso NO cuenta como validación.

---

## 2026-07-04 — Resultado de la validación out-of-sample | Estado: **FILTRO VALIDADO / ESTRATEGIA BASE SIN EDGE OOS**

**Datos**: ene-2025 → nov-2025 (271 sesiones RTH, sin solapamiento con el
período de diseño). Reportes: `reports/true_oos_2025_01_11_validation.*`.

| Métrica | Original | no_midday |
|---|---|---|
| Trades | 311 | 212 |
| PnL neto | **-$1,316** | **-$876** |
| Profit factor | 0.93 | 0.93 |
| Expectancia | -0.051 R | -0.024 R |
| Drawdown máx | $3,186 (12.6%) | $2,225 (8.9%) |
| Racha perdedora | 14 | 13 |

**Contra el criterio pre-registrado**: CUMPLE (expR mayor, drawdown menor,
muestra 212 trades). La candidata mejora el PnL en 7 de 11 meses. La tesis
central del filtro **replicó fuera de muestra**: los 125 trades de mediodía
que el original tomó en 2025 perdieron -$1,299 netos. Los "trades nuevos por
slot libre" (+$330 in-sample) resultaron ser suerte: -$630 OOS.

**Decisión**: `no_midday` se promueve sobre la original (la domina en ambos
períodos y su mecanismo replicó). **PERO la observación crítica manda**:
ambas versiones PIERDEN en 2025 (PF 0.93). La estrategia base no demostró
edge fuera del régimen dic-2025→jun-2026. La mejora de expectancia del filtro
(+0.027 R) no es estadísticamente significativa (t≈0.2); su beneficio sólido
es la reducción de exposición y drawdown (-30%).

**Implicación**: ninguna versión está en condiciones de avanzar a paper
trading. El problema ya no es el filtro sino el edge de la estrategia base,
que es investigación nueva (régimen/tendencia, selección de días, u otra
lógica de entrada) — fase separada, con su propio in-sample/out-of-sample.
La regla de no optimizar parámetros de la lógica actual sigue vigente.

---

## 2026-07-04 — Nueva candidata `near_vwap` | Estado: **EN EVALUACIÓN, EVIDENCIA MIXTA**

**Variante**: `daytrading_vwap_liquidity_rr2_no_midday_near_vwap` — hereda de
no_midday; cambio único: distancia máxima al VWAP de 60 → 30 pts
(`max_vwap_distance_points_near`, umbral redondo deliberadamente distinto
del borde óptimo del diagnóstico para minimizar curve fitting).

**Origen**: diagnóstico de edge sobre OOS 2025 — entradas a >40 pts del VWAP
dieron expR -0.27; a <24 pts, +0.21 (monotónico). Refuerza la tesis propia
de la estrategia (pullback A valor).

**Resultado** (`reports/near_vwap_variant_comparison.csv`, ambos datasets
contaminados: el A generó la hipótesis, el B contiene el diseño de no_midday):

| | A: 2025 (origen) | B: completo 18m |
|---|---|---|
| PnL | -$876 → **+$178** | +$2.198 → **+$1.439** (peor) |
| PF / expR | 0.93→1.03 / -0.02→+0.03 | 1.14→1.19 / 0.09→0.15 |
| DD / racha | -43% / 13→7 | -43% / 13→7 |
| Muestra | -52% | -54% |
| Meses mejores | 6 de 11 | 7 de 18 |

**Señal de alerta**: los trades eliminados por la regla fueron muy negativos
en 2025 (-$1.792) pero **positivos en dic-25→jun-26** (≈ +$1.850): el efecto
"lejos del VWAP = malo" parece DEPENDIENTE DEL RÉGIMEN (en tendencia fuerte
el precio se aleja del VWAP y la continuación igual paga). A diferencia de
no_midday, cuyo mecanismo replicó con el mismo signo en ambos períodos.
Patrón recurrente: los trades "nuevos por re-secuenciación" volvieron a ser
negativos (-$590 y -$551).

**Decisión**: ni se adopta ni se descarta. Criterio pre-registrado para datos
NO usados (2024 o jul-2026+), corriendo `scripts/validate_near_vwap.py`
adaptado al archivo nuevo: (1) expR(near_vwap) > expR(no_midday), (2) el PnL
de los trades eliminados debe ser negativo en el período nuevo (el mecanismo
debe replicar, no solo las métricas), (3) ≥ 30 trades de la candidata.
Prior honesto: más bajo que el que tenía no_midday, por el flip de signo
entre regímenes. Sigue vigente: no más variantes ni optimización.

---

## 2026-07-04 — Nueva candidata `atr_filter` | Estado: **CANDIDATA FUERTE, PENDIENTE OOS REAL**

**Variante**: `daytrading_vwap_liquidity_rr2_no_midday_atr_filter` — hereda de
no_midday; cambio único: no operar si el ATR-20 previo a la señal (rolling
causal, solo pasado) es menor a `min_atr20_points: 8.0` (redondo, por debajo
del borde del tercil malo del diagnóstico ~10; sin grid search: un solo valor).

**Origen**: diagnóstico de régimen — el ATR-20 previo fue el ÚNICO proxy
causal de volatilidad cuyo ordenamiento replicó en ambos datasets (cinta
muerta = tercil peor en 2025 Y en 18 meses, sin flip de signo).

**Resultado** (`reports/atr_filter_variant_comparison.csv`; ambos datasets
participaron del diagnóstico → no es OOS):

| | A: 2025 | B: completo 18m |
|---|---|---|
| PnL | -$876 → **+$573** | +$2.198 → **+$3.446** |
| PF / expR | 0.93→1.06 / -0.02→+0.06 | 1.14→1.27 / 0.09→0.17 |
| DD | -41% ($2.225→$1.323) | -41% |
| Racha | 13→9 | 13→9 |
| Muestra | -22% (212→166) | -19% (287→233) |
| Eliminados por ATR | 50, PnL **-$1.065** (expR -0.17) | 59, PnL **-$595** (expR -0.05) |

**Contra los criterios de no-adopción pre-acordados**: (1) no mejora "solo
por recortar" — el PnL absoluto SUBE en ambos con recorte modesto ~20%;
(2) no sacrifica PnL por drawdown — mejora ambos; (3) no es de un solo
período — mejora las cuatro métricas en los dos datasets y, clave, los
trades eliminados fueron netos NEGATIVOS en ambos períodos (el mecanismo
replica signo — la propiedad que a near_vwap le faltó).

**Decisión**: candidata principal por delante de near_vwap. NO adoptada
todavía: la hipótesis salió de estos mismos datasets. Criterio pre-registrado
para datos no usados (2024 o jul-2026+), con `scripts/validate_atr_filter.py`:
(1) expR(atr_filter) > expR(no_midday); (2) los trades eliminados por ATR
deben ser netos negativos en el período nuevo; (3) ≥ 30 trades de la
candidata. Sigue vigente: no más variantes ni optimización de parámetros.

---

## 2026-07-05 — Validación OOS 2024 de `atr_filter` | Estado: **FILTRO PROMOVIDO / LÍNEA DE ESTRATEGIA SIN EDGE ENTRE REGÍMENES**

**Datos**: año 2024 completo (284 sesiones RTH), totalmente fuera del período
de diseño. Reportes: `reports/atr_filter_validation_MNQ_2024_full_*`.

| Métrica (2024) | no_midday | atr_filter |
|---|---|---|
| Trades | 332 | 258 (-22%) |
| PnL neto | **-$4,716** | **-$2,948** (+$1,768) |
| Profit factor | 0.77 | 0.82 |
| Expectancia | -0.149 R | -0.120 R |
| Drawdown máx | $5,360 | $3,553 (-34%) |
| Racha perdedora | 10 | 12 (empeora) |
| Eliminados por ATR | — | 102 trades, PnL **-$1,673** (expR -0.19) |

**Contra el criterio pre-registrado: CUMPLE los tres puntos.** El mecanismo
replicó en datos vírgenes: los trades de cinta muerta fueron netos negativos
también en 2024 (tercer período consecutivo con el mismo signo: -$1,065 en
2025, -$595 en 18m, -$1,673 en 2024). `atr_filter` queda **promovida** como
mejor variante de la línea (domina a no_midday en los tres períodos).

**La conclusión que manda**: la estrategia base NO tiene edge entre
regímenes. Con ~30 meses de datos reales: 2024 pierde fuerte (PF 0.77),
2025 pierde (PF 0.93), solo dic-25→jun-26 ganó. Hallazgo adicional de 2024:
la franja 10:00-10:59 — el "horario bueno" de períodos posteriores — perdió
-$2,132 en 2024: tampoco esa pauta es estable. Los filtros de reducción de
daño (mediodía, ATR) son reales y replicables, pero reducen las pérdidas de
un núcleo perdedor: su techo está alcanzado.

**Decisión**: (1) `atr_filter` = variante de referencia de la línea RR2.
(2) NINGUNA versión avanza a paper/live. (3) Se cierra el ciclo de filtros
de entrada sobre esta lógica: próxima fase = rediseño del núcleo (otra
lógica de entrada, conciencia de régimen más allá de filtros estáticos, o
gestión dentro del trade), como investigación nueva con su propio protocolo
in/out-of-sample. (4) Sigue vigente: no optimizar parámetros de lo actual.

---

## 2026-07-05 — CIERRE FORMAL DEL CICLO VWAP + LIQUIDITY RR2 | Estado: **CERRADO**

Veredicto final del ciclo de investigación (documento completo:
`reports/final_vwap_rr2_research_closure.md`):

| Estrategia | Estado final |
|---|---|
| `daytrading_vwap_liquidity_rr2` (original) | **DESCARTADA** como estrategia final |
| `daytrading_vwap_liquidity_rr2_no_midday` | Documentada como **mejora parcial** (filtro replicado) |
| `daytrading_vwap_liquidity_rr2_no_midday_atr_filter` | **Promovida** como mejor variante de la familia |
| `longs_only`, `morning_only`, `no_midday_longs_only`, `near_vwap` | Descartadas (no replicaron / régimen-dependientes) |

**`atr_filter` NO queda aprobada para paper trading, live trading ni cuentas
de fondeo.** Motivo: aunque reduce daño de forma replicable (OOS 2024:
+$1,768 de mejora, DD -34%, mecanismo replicado por tercer período), el
núcleo de entrada sigue sin edge estable — pierde en 2024 (PF 0.82) y 2025,
y solo ganó en el régimen dic-25→jun-26.

**REGLA DE CIERRE: no continuar optimizando filtros de entrada sobre esta
lógica.** El techo de los filtros de reducción de daño está alcanzado.

**Próxima fase** (investigación NUEVA, con período de diseño y out-of-sample
propios e intocados, criterios pre-registrados en este log):
gestión dinámica dentro del trade / salida temprana si el trade no expande /
no sostener trades en días que no desarrollan rango / o rediseño completo de
la lógica de entrada.
