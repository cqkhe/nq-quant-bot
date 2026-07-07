# Research Memory — Índice maestro

Tabla principal de la memoria de investigación. **Toda hipótesis aparece
acá**, desde que se propone hasta su decisión final. Los detalles viven en
las fichas (`hypotheses/`, `decisions/`); esta tabla es el mapa.

Estados: `propuesta → en diseño → testeada → { promovida | en observación | descartada }`

## Hipótesis

| ID | Hipótesis | Estrategia / módulo | Estado | Prioridad | Período diseño | Período OOS | Decisión | Reporte |
|---|---|---|---|---|---|---|---|---|
| H001 | Pullback a valor (VWAP+EMAs) con RR 2:1 tiene edge estable en MNQ RTH — familia completa con 6 variantes de filtro | `daytrading_vwap_liquidity_rr2` + variantes | **cerrada** | — | dic-2025→jun-2026 (+ 2025 para los filtros) | **2024 completo (virgen)** | **D001: NO OPERABLE** — atr_filter promovida como referencia de la familia, bloqueada para paper/live/fondeo | [cierre](../reports/final_vwap_rr2_research_closure.md) · [OOS 2024](../reports/atr_filter_validation_MNQ_2024_full_1m_ninjatrader_combined_clean_summary.txt) |
| [H002](hypotheses/H002_dynamic_exit_no_progress.md) | Salida dinámica si el trade no alcanza +0.5R en 30 min (regla congelada) | EXIT_LOGIC — variante `..._dynamic_exit_h002` | **TESTED → OBSERVATION** | **ALTA** | 2024 + 2025-26 (ya vistos) | PENDIENTE: jul-2026+ o 2023 | **D002**: mecanismo replicó (regla +$185/+$290/+$493 directo, mata solo 11-17% targets) pero neto ~0 por re-secuenciación tóxica (4ª observación del patrón) → hipótesis derivada candidata: bloquear re-entrada tras early_exit | [resultado](../reports/h002_dynamic_exit_summary.md) · [D002](decisions/D002_h002_dynamic_exit_result.md) |
| [H003](hypotheses/H003_exit_on_failed_expansion.md) | Salida por expansión fallida después de la entrada | EXIT_LOGIC (Fase 5; usa Regime Engine in-trade) | **PROPOSED** | **ALTA** | 2024 + 2025-26 (ya vistos) | PENDIENTE: jul-2026+ o 2023 | — | — |
| [H004](hypotheses/H004_regime_aware_entry.md) | Evaluar entradas solo bajo regímenes causales favorables | MARKET_REGIME | **PROPOSED** | **BAJA** (deliberada: techo conocido de filtros de entrada) | 2024 + 2025-26 (ya vistos) | PENDIENTE: jul-2026+ o 2023 | — | — |
| [H005](hypotheses/H005_block_reentry_after_early_exit.md) | Bloquear re-entrada tras un early_exit por no progreso (versión preferida: resto de sesión, cero parámetros) | RISK_MANAGEMENT — derivada de H002/D002 | **PROPOSED** | **ALTA** | 2024 + 2025-26 (contaminados) | PENDIENTE: jul-2026+ o 2023 | — (depende de que H002 replique en OOS) | [D002](decisions/D002_h002_dynamic_exit_result.md) |

## Backlog de hipótesis (ideas sin ficha)

| Candidata | Origen | Nota |
|---|---|---|
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
