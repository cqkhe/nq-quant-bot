# H002 — Salida dinámica si el trade no alcanza +0.5R en X minutos

| Campo | Valor |
|---|---|
| **ID** | H002 |
| **Fecha de registro** | 2026-07-05 |
| **Estado** | PROPOSED |
| **Tipo** | EXIT_LOGIC |
| **Prioridad (calculada)** | ALTA — impacto ALTO, claridad ALTA, riesgo CF MEDIO |
| **Origen** | Cierre de H001 (reports/final_vwap_rr2_research_closure.md §9) + diagnóstico de régimen: mediana R de la familia = -1.02 (el trade típico muere en el stop) y los targets tardan ~35 barras. |

## Hipótesis

Los trades de continuación que no alcanzan +0.5R dentro de X minutos desde la entrada tienen expectativa claramente peor que los que sí; cerrarlos anticipadamente reduce la pérdida media sin destruir una fracción relevante de los ganadores.

## Mecanismo causal esperado

En setups de continuación, la participación institucional que valida la entrada aparece rápido o no aparece: un trade estancado bajo +0.5R indica absorción/falta de follow-through, y su destino dominante es el stop (-1R) o el flatten. Cortarlo temprano convierte pérdidas completas en pérdidas parciales. Ataca el hallazgo central del cierre de H001: el régimen del día se revela DESPUÉS de entrar, donde los filtros de entrada no llegan.

## Datasets

| Rol | Dataset | Período |
|---|---|---|
| Diseño (in-sample) | data/processed/MNQ_2024_full + MNQ_2025_01_2026_06 (ya vistos: solo sirven para DISEÑO) | 2024-01 → 2026-06 |
| Out-of-sample (RESERVADO) | PENDIENTE: jul-2026 en adelante (a recolectar) o histórico 2023 (a adquirir) — **PENDIENTE: datos aún no disponibles/adquiridos (garantía de OOS virgen)** | futuro |

Muestra mínima para veredicto: **30 trades**.

## Criterios de ACEPTACIÓN *(borrador: se congelan al pasar a DESIGNED)*

1. expR de la variante > expR de la base (atr_filter) en el OOS
2. los trades cerrados anticipadamente habrían terminado mayoritariamente en stop (el mecanismo replica: PnL evitado negativo, medible re-simulando sin la regla)
3. no se pierde más del ~20% de los targets de la base
4. >= 30 trades de la variante en el OOS

## Criterios de DESCARTE *(borrador: se congelan al pasar a DESIGNED)*

1. la mejora desaparece re-simulando en el OOS (flip del PnL evitado)
2. mata ganadores: los targets caen mucho más que las pérdidas evitadas
3. mejora métricas solo por reducir la muestra

## Riesgos de curve fitting

**Nivel: MEDIO.** Dos parámetros nuevos (umbral R y X minutos): elegir valores redondos únicos (p.ej. 0.5R / 20 min) SIN grid search. El diseño saldrá de datos ya vistos por H001: la validación exige OOS virgen.

## Notas

PRERREQUISITO TÉCNICO: el motor de backtesting hoy solo soporta stop/target/flatten fijos; esta hipótesis requiere la extensión controlada de salidas dinámicas (Fase 5 del roadmap), con tests propios, ANTES de implementarla.

## Resultado final

*(pendiente)*

## Decisión

*(pendiente — se registra como DXXX en research/decisions/)*
