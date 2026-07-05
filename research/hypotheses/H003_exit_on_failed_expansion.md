# H003 — Salida por expansión fallida después de la entrada

| Campo | Valor |
|---|---|
| **ID** | H003 |
| **Fecha de registro** | 2026-07-05 |
| **Estado** | PROPOSED |
| **Tipo** | EXIT_LOGIC |
| **Prioridad (calculada)** | ALTA — impacto ALTO, claridad ALTA, riesgo CF MEDIO |
| **Origen** | Diagnóstico de régimen de H001: el edge vive en expansión pero los proxies causales PRE-entrada fueron inconsistentes; la expansión POST-entrada no tiene ese problema. Cierre de H001 §9. |

## Hipótesis

Si tras la entrada el rango del día no se expande en la dirección del trade (el mercado sigue comprimido o expande en contra), mantener la posición hasta stop/target genera pérdida innecesaria frente a abandonar temprano.

## Mecanismo causal esperado

La estrategia de continuación solo cobra en días que desarrollan rango (diagnóstico de régimen: +0.45R en tendenciales vs -0.2R en laterales). La expansión post-entrada ES observable causalmente DENTRO del trade (range_so_far y expansion_ratio del Regime Engine se actualizan barra a barra): si no aparece, el trade quedó sin combustible y su valor esperado converge al stop.

## Datasets

| Rol | Dataset | Período |
|---|---|---|
| Diseño (in-sample) | data/processed/MNQ_2024_full + MNQ_2025_01_2026_06 (ya vistos: solo sirven para DISEÑO) | 2024-01 → 2026-06 |
| Out-of-sample (RESERVADO) | PENDIENTE: jul-2026 en adelante (a recolectar) o histórico 2023 (a adquirir) — **PENDIENTE: datos aún no disponibles/adquiridos (garantía de OOS virgen)** | futuro |

Muestra mínima para veredicto: **30 trades**.

## Criterios de ACEPTACIÓN *(borrador: se congelan al pasar a DESIGNED)*

1. expR mejora vs base en OOS y el PnL de los tramos abandonados es negativo (el mecanismo replica)
2. el drawdown no empeora
3. >= 30 trades de la variante en el OOS

## Criterios de DESCARTE *(borrador: se congelan al pasar a DESIGNED)*

1. los trades abandonados terminaban mayoritariamente en target (mata ganadores)
2. funciona en un período y falla en el otro (flip)

## Riesgos de curve fitting

**Nivel: MEDIO.** Definir 'expansión fallida' con las features estándar del Regime Engine (expansion_ratio) y umbrales redondos únicos; no probar variantes de la definición contra los mismos datos.

## Notas

Solapa conceptualmente con H002 (ambas cortan trades sin progreso): si las dos avanzan a diseño, definir primero cuál se testea, o diferenciarlas con precisión (H002 = progreso en R; H003 = expansión del día). PRERREQUISITO: misma extensión de salidas dinámicas del motor (Fase 5).

## Resultado final

*(pendiente)*

## Decisión

*(pendiente — se registra como DXXX en research/decisions/)*
