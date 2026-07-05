# Research Memory — Índice maestro

Tabla principal de la memoria de investigación. **Toda hipótesis aparece
acá**, desde que se propone hasta su decisión final. Los detalles viven en
las fichas (`hypotheses/`, `decisions/`); esta tabla es el mapa.

Estados: `propuesta → en diseño → testeada → { promovida | en observación | descartada }`

## Hipótesis

| ID | Hipótesis | Estrategia / módulo | Estado | Período diseño | Período OOS | Decisión | Reporte |
|---|---|---|---|---|---|---|---|
| H001 | Pullback a valor (VWAP+EMAs) con RR 2:1 tiene edge estable en MNQ RTH — familia completa con 6 variantes de filtro | `daytrading_vwap_liquidity_rr2` + variantes | **cerrada** | dic-2025→jun-2026 (+ 2025 para los filtros) | **2024 completo (virgen)** | **D001: NO OPERABLE** — atr_filter promovida como referencia de la familia, bloqueada para paper/live/fondeo | [cierre](../reports/final_vwap_rr2_research_closure.md) · [OOS 2024](../reports/atr_filter_validation_MNQ_2024_full_1m_ninjatrader_combined_clean_summary.txt) |

## Backlog de hipótesis (propuestas, sin ficha completa todavía)

| Candidata | Origen | Nota |
|---|---|---|
| Time-stop: trades que no avanzan +0.5R en N minutos tienden a fallar → salida anticipada | Cierre H001 / diagnóstico de régimen | Fase 5 del roadmap; requiere extensión del motor (salidas dinámicas) |
| No sostener trades en días que no desarrollan rango después de la entrada | Diagnóstico de régimen (el día tendencial se revela post-entrada) | Fase 5 |
| Rupturas falsas cerca del VWAP tienen peor expectativa | Propuesta conceptual | Sin diseñar |

## Mecanismos validados (building blocks disponibles)

| Mecanismo | Evidencia | Fuente |
|---|---|---|
| Mediodía 11:00–12:59 = pérdida sistemática en MNQ RTH | Replicó en 2 períodos | H001 / no_midday |
| ATR-20 previo bajo (< ~8 pts) = cinta muerta = no operar | Replicó en 3 períodos, incl. 2024 virgen | H001 / atr_filter |

## Descartes con evidencia (no re-testear sin justificación nueva)

| Idea descartada | Por qué | Fuente |
|---|---|---|
| Filtrar por lado (solo longs / solo shorts) | El sesgo es régimen: se invirtió entre períodos | H001 / longs_only |
| Operar solo la franja 10:00–10:59 | Inestable: la franja perdió -$2,132 en 2024 | H001 / morning_only |
| Distancia al VWAP como filtro estático | Régimen-dependiente: eliminados con flip de signo entre períodos | H001 / near_vwap |
| Seguir optimizando filtros de entrada sobre la lógica RR2 | Techo alcanzado: reducen daño, no crean edge | D001 (regla de cierre) |

## Decisiones

| ID | Fecha | Título | Veredicto |
|---|---|---|---|
| D001 | 2026-07-05 | Cierre del ciclo VWAP + Liquidity RR2 | Familia no operable; atr_filter referencia; bloqueo paper/live/fondeo |
