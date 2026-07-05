# H004 — Evaluar señales de entrada solo bajo regímenes causales favorables

| Campo | Valor |
|---|---|
| **ID** | H004 |
| **Fecha de registro** | 2026-07-05 |
| **Estado** | PROPOSED |
| **Tipo** | MARKET_REGIME |
| **Prioridad (calculada)** | BAJA — impacto MEDIO, claridad MEDIA, riesgo CF ALTO |
| **Origen** | Diagnóstico de régimen de H001 + Market Regime Engine (Fase 3). |

## Hipótesis

Las señales de entrada solo deberían evaluarse cuando el Regime Engine etiqueta la barra con regímenes causales favorables (p.ej. vol_regime != baja y trend_regime != lateral); fuera de eso, la expectativa es negativa.

## Mecanismo causal esperado

Extensión natural del filtro ATR validado en H001 (vol baja = cinta muerta) al vocabulario completo del Regime Engine. El mecanismo es el mismo: sin volatilidad ni direccionalidad no hay continuación que cobrar.

## Datasets

| Rol | Dataset | Período |
|---|---|---|
| Diseño (in-sample) | data/processed/MNQ_2024_full + MNQ_2025_01_2026_06 (ya vistos: solo sirven para DISEÑO) | 2024-01 → 2026-06 |
| Out-of-sample (RESERVADO) | PENDIENTE: jul-2026 en adelante (a recolectar) o histórico 2023 (a adquirir) — **PENDIENTE: datos aún no disponibles/adquiridos (garantía de OOS virgen)** | futuro |

Muestra mínima para veredicto: **30 trades**.

## Criterios de ACEPTACIÓN *(borrador: se congelan al pasar a DESIGNED)*

1. expR mejora vs base en OOS Y los trades filtrados por régimen son netos negativos también en el OOS (replicación del mecanismo, regla near_vwap)
2. >= 30 trades de la variante en el OOS

## Criterios de DESCARTE *(borrador: se congelan al pasar a DESIGNED)*

1. los trades filtrados cambian de signo entre períodos (régimen-dependencia)
2. mejora solo por recorte de muestra

## Riesgos de curve fitting

**Nivel: ALTO.** PRIORIDAD BAJA DELIBERADA: el cierre de H001 demostró que los filtros de entrada tienen techo (reducen daño, no crean edge), los proxies causales de régimen PRE-entrada fueron inconsistentes entre períodos, y elegir qué combinación de etiquetas usar sobre datos ya minados es terreno fértil para curve fitting. Se registra para no perder la idea, no para ejecutarla pronto.

## Notas

Solo tiene sentido si primero existe una base con edge (H002/H003 u otra lógica): filtrar entradas de una base perdedora ya se hizo en H001 y tiene techo conocido.

## Resultado final

*(pendiente)*

## Decisión

*(pendiente — se registra como DXXX en research/decisions/)*
