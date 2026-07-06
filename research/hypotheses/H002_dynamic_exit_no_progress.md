# H002 — Salida dinámica si el trade no alcanza +0.5R en 30 minutos

| Campo | Valor |
|---|---|
| **ID** | H002 |
| **Fecha de registro** | 2026-07-05 |
| **Estado** | DESIGNED |
| **Tipo** | EXIT_LOGIC |
| **Prioridad (calculada)** | ALTA — impacto ALTO, claridad ALTA, riesgo CF MEDIO |
| **Origen** | Cierre de H001 + diagnóstico dedicado reports/dynamic_exit_diagnosis_summary.md (2026-07-05, 287 trades de no_midday sobre 18 meses). |

## Hipótesis

Los trades de continuación que no alcanzan +0.5R dentro de los primeros 30 minutos tienen expectativa claramente negativa; cerrarlos a mercado en ese punto reduce la pérdida media sin destruir una fracción relevante de los ganadores.

## Mecanismo causal esperado

En setups de continuación, la participación que valida la entrada aparece rápido o no aparece. Diagnóstico (287 trades, dic-24→jun-26, in-sample): los targets alcanzan +0.5R con MEDIANA DE 3 MINUTOS y el 100% lo alcanza; de los stops, solo 46% lo alcanza alguna vez. Un trade estancado bajo +0.5R a los 30 min tiene winrate final 23%, R promedio -0.56 y termina en stop el 71% de las veces. La espera posterior solo financia el camino al stop.

## Datasets

| Rol | Dataset | Período |
|---|---|---|
| Diseño (in-sample) | data/processed/MNQ_2025_01_2026_06 (+2024 para re-chequeo de diseño) — ya vistos: solo diseño | 2024-01 → 2026-06 |
| Out-of-sample (RESERVADO) | PENDIENTE: jul-2026 en adelante (a recolectar) o histórico 2023 (a adquirir) — **PENDIENTE: datos aún no disponibles/adquiridos (garantía de OOS virgen)** | futuro |

Muestra mínima para veredicto: **30 trades**.

## Criterios de ACEPTACIÓN

1. REGLA CONGELADA: si el trade no alcanzó +0.5R (por excursión favorable) a los 30 minutos de la entrada, salida a mercado. Sin variantes de la regla.
2. En el OOS: expR de la variante > expR de la base (misma lógica sin la regla).
3. El mecanismo replica: los trades cortados por la regla deben mostrar PnL evitado negativo también en el OOS (re-simulación con y sin regla).
4. No mata ganadores: <= 20% de los trades cortados habrían llegado a target.
5. >= 30 trades de la variante en el OOS.

## Criterios de DESCARTE

1. El PnL evitado por la regla cambia de signo en el OOS (flip = régimen).
2. Más del 20% de los cortados habrían sido targets.
3. La mejora de métricas viene solo de reducir la muestra.

## Riesgos de curve fitting

**Nivel: MEDIO.** El umbral +0.5R estaba PRE-declarado en la hipótesis original (antes del diagnóstico). La ventana de 30 min se eligió redonda y del MEDIO de la curva reportada (10-60 min), no en la celda más extrema (+0.25R/45min era 'mejor' in-sample y se descartó por eso). Riesgo residual: el diagnóstico usa datos ya vistos por H001; nada de esto vale sin el OOS virgen.

## Notas

RESULTADO DEL DIAGNÓSTICO (2026-07-05, in-sample): ganadores rápidos (mediana 3 min a +0.5R), estancados a 30 min = 23% winrate / -0.56R / 71% stops (n=35, 12% de los trades). Los session_flatten NO son objetivo de la regla (92.6% alcanza +0.5R; MFE mediana 1.04R). Hallazgo colateral fuerte para H003: retorno al VWAP post-entrada -> winrate 17% vs 60.5% sin retorno; expansión del rango durante el trade: targets 38.5 pts vs stops/flatten 0 pts.

PRERREQUISITO TÉCNICO — ACTUALIZACIÓN 2026-07-05: la extensión del motor para salidas dinámicas está **implementada y testeada** (hook `Strategy.should_exit_early` + `TradeState` causal + `exit_reason="early_exit"`; 7 tests dedicados, incluida la equivalencia exacta sin hook y la ausencia de lookahead — ver `docs/dynamic_exit_engine_extension.md`). El `TradeState` entrega `current_r` y `mfe_r` al cierre de cada barra, lo que resuelve el faltante del mark-to-market en T identificado por el diagnóstico.

ESTADO: la hipótesis **sigue en DESIGNED**. La variante (`..._dynamic_exit` o similar) **NO fue creada** ni backtesteada. Para pasar a READY_FOR_TEST falta únicamente implementar la variante con la regla congelada (decisión aparte); para TESTED, correr el protocolo contra el OOS virgen declarado (jul-2026+ o 2023).

## Resultado final

*(pendiente)*

## Decisión

*(pendiente — se registra como DXXX en research/decisions/)*
