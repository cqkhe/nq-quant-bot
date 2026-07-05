# H001 — Familia VWAP + Liquidity RR2 (carga retroactiva)

| Campo | Valor |
|---|---|
| **ID** | H001 |
| **Fecha de registro** | 2026-07-05 (retroactiva; el ciclo corrió 2026-07-03 → 2026-07-05) |
| **Estado** | **testeada → cerrada** (ver D001) |
| **Origen** | Diseño inicial del proyecto: estrategia intradía MNQ/NQ de pullback a valor |
| **Estrategia/módulo afectado** | `daytrading_vwap_liquidity_rr2` y sus 6 variantes |

> Ficha retroactiva: agrupa la hipótesis madre y sus sub-hipótesis de
> filtros. Los ciclos futuros usan una ficha POR hipótesis; esta consolida
> el caso histórico completo para la memoria.

## Hipótesis (madre)

Una estrategia intradía de continuación en MNQ RTH — pullback a valor
(VWAP/EMA25) con tendencia (EMA13>25>55, sobre EMA200 con pendiente),
rechazo de price action, confirmación de volumen, stop técnico intradía y
TP fijo 2R — tiene expectancia positiva estable.

## Mecanismo causal esperado

En días con participación institucional direccional, los retrocesos al valor
(VWAP) son absorbidos y la tendencia continúa; el RR 2:1 fijo con winrate
~40% daría expectancia positiva.

## Datasets

| Rol | Período | Nota |
|---|---|---|
| Diseño original | dic-2025 → jun-2026 (113 sesiones) | in-sample de la madre y de no_midday |
| OOS #1 | ene-2025 → nov-2025 (271 sesiones) | luego contaminado: originó las hipótesis near_vwap y atr_filter |
| Contraste | ene-2025 → jun-2026 (18 meses) | contiene ambos anteriores |
| **OOS final (virgen)** | **año 2024 completo (284 sesiones)** | ninguna hipótesis lo vio |

## Sub-hipótesis probadas (variantes)

| Variante | Hipótesis del filtro | Resultado |
|---|---|---|
| `no_midday` | El mediodía 11-13h pierde sistemáticamente | **Mecanismo REPLICÓ** (2 períodos); mejora parcial |
| `longs_only` | Los shorts no aportan | DESCARTADA: el sesgo se invirtió en 2025 (régimen) |
| `morning_only` | Solo 10-11h tiene edge | DESCARTADA: la franja perdió -$2,132 en 2024 |
| `no_midday_longs_only` | Combinación | DESCARTADA (hereda longs_only) |
| `near_vwap` (≤30 pts) | Entradas lejos del valor son tóxicas | EN OBSERVACIÓN→DESCARTADA de facto: régimen-dependiente (eliminados -$1,792 en 2025 pero +$1,850 en dic25-jun26) |
| `atr_filter` (ATR-20 ≥ 8) | ATR previo bajo = cinta muerta = no operar | **Mecanismo REPLICÓ en 3 períodos** incl. 2024 virgen → mejor variante de la familia |

## Resultados clave

**In-sample (dic-25→jun-26)**: original +$1,452 (89 trades, PF 1.31,
expR +0.15); no_midday +$2,271 (59, PF 1.83, expR +0.38).

**OOS 2025 (ene-nov)**: original **-$1,316** (311, PF 0.93); no_midday
**-$876** (212, PF 0.93). El filtro replicó; la base no.

**OOS FINAL 2024 (virgen)**:

| | no_midday | atr_filter |
|---|---|---|
| Trades | 332 | 258 |
| PnL | **-$4,716.30** | **-$2,948.06** |
| PF | 0.765 | 0.818 |
| expR | -0.149 | -0.120 |
| DD | $5,360 | $3,553 (-34%) |
| Eliminados por ATR | — | 102 trades con PnL **-$1,673** (expR -0.19) |

`atr_filter` cumplió sus 3 criterios pre-registrados (expR mayor, mecanismo
replicado, muestra suficiente) — y aun así la familia pierde en 2024 y 2025.

## Diagnósticos derivados (conocimiento estructural)

- El edge vive en días tendenciales/expansión (+0.45R, PF 1.89 en B) y
  muere en laterales (-0.2R) y baja volatilidad (monotónico).
- Operar contra la dirección final del día destruye (-0.47/-0.52R, WR <20%).
- El día tendencial NO es anticipable a la entrada: los proxies causales de
  expansión fueron inconsistentes o invertidos entre datasets.
- Por eso los filtros de entrada tienen techo: reducen daño, no crean edge.

## Riesgos de curve fitting identificados (y cómo se gestionaron)

- Filtros derivados de los mismos datos que los midieron → validación
  obligatoria en datos vírgenes (2024), que descartó a 4 de 6 variantes.
- Umbrales elegidos redondos y lejos del óptimo (30 vs 40; 8 vs 10).
- Regla decisiva aprendida: **el mecanismo debe replicar con el mismo signo,
  no solo las métricas** (descartó a near_vwap, validó a atr_filter).

## Resultado final

La familia NO tiene edge estable entre regímenes: pierde en 2024 (PF 0.77
base) y 2025 (PF 0.93), solo ganó en dic-25→jun-26. Dos mecanismos de
reducción de daño quedaron validados como building blocks (mediodía, ATR).

Reportes: `reports/final_vwap_rr2_research_closure.md` (cierre completo),
`reports/atr_filter_validation_MNQ_2024_full_*` (validación final),
`docs/strategy_decision_log.md` (todas las decisiones intermedias).

## Decisión

**D001** — ciclo cerrado; familia no operable; atr_filter promovida como
referencia de la familia pero bloqueada para paper/live/fondeo.
