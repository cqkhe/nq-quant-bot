# H005 — Bloquear la re-entrada después de una salida temprana por no progreso

| Campo | Valor |
|---|---|
| **ID** | H005 |
| **Fecha de registro** | 2026-07-05 |
| **Estado** | PROPOSED |
| **Tipo** | RISK_MANAGEMENT |
| **Prioridad (calculada)** | ALTA — impacto ALTO, claridad ALTA, riesgo CF BAJO |
| **Origen** | D002 (resultado de H002): el mecanismo de la salida temprana replicó en los tres datasets pero el neto quedó ~0 por los trades de re-secuenciación. Ver reports/h002_dynamic_exit_summary.md y D002. |

## Hipótesis

Después de un early_exit por falta de progreso (regla H002), bloquear nuevas entradas por el resto de la sesión (opción preferida, sin parámetros) o por un período fijo preservaría el beneficio directo de H002 (+$185/+$290/+$493 por período) eliminando los trades nuevos por re-secuenciación que hoy lo cancelan (-$755/-$418/-$636).

## Mecanismo causal esperado

La salida temprana funciona como control de daño: detecta que el contexto del trade es de baja calidad (sin participación, sin seguimiento). Si el sistema vuelve a entrar inmediatamente en ese MISMO contexto, reintroduce el riesgo que acababa de evitar — el early_exit es información sobre la sesión, no solo sobre el trade. Evidencia acumulada del patrón 'trades por re-secuenciación son tóxicos': 6 mediciones del mismo signo en 4 experimentos distintos (no_midday OOS: -$630; near_vwap: -$590 y -$551; H002: -$755, -$418, -$636), contra una sola positiva chica in-sample (+$330, n=4).

## Datasets

| Rol | Dataset | Período |
|---|---|---|
| Diseño (in-sample) | data/processed/MNQ_2024_full + MNQ_2025_01_2026_06 (CONTAMINADOS: generaron H002/D002 y toda la familia H001 — solo sirven para diseño) | 2024-01 → 2026-06 |
| Out-of-sample (RESERVADO) | PENDIENTE: jul-2026 en adelante (a recolectar) o histórico 2023 (a adquirir) — **PENDIENTE: datos aún no disponibles/adquiridos (garantía de OOS virgen)** | futuro |

Muestra mínima para veredicto: **30 trades**.

## Criterios de ACEPTACIÓN *(borrador: se congelan al pasar a DESIGNED)*

1. (borrador) En el OOS: expR de la variante H005 > base atr_filter Y > variante H002 sola (el bloqueo debe agregar valor sobre la salida temprana).
2. (borrador) El mecanismo replica: los trades que el bloqueo evita (medibles re-simulando H002 sin bloqueo) deben ser netos NEGATIVOS también en el OOS.
3. (borrador) El beneficio directo de la regla H002 se preserva (early exits siguen ahorrando vs contrafactual).
4. (borrador) >= 30 trades de la variante en el OOS.

## Criterios de DESCARTE *(borrador: se congelan al pasar a DESIGNED)*

1. (borrador) Los trades bloqueados resultan netos positivos en el OOS (flip del patrón de re-secuenciación = era régimen, no estructura).
2. (borrador) La mejora desaparece comparada contra H002 sola.
3. (borrador) La mejora viene solo de reducir la muestra.

## Riesgos de curve fitting

**Nivel: BAJO.** La versión preferida ('bloquear hasta fin de sesión') tiene CERO parámetros ajustables: riesgo de ajuste mínimo. Al pasar a DESIGNED se congela UNA sola versión de la regla (resto de sesión O N minutos redondos, no ambas — probar las dos sería grid search). Riesgo residual: la hipótesis nace de los mismos datasets del ciclo (sesgo de origen); nada vale sin el OOS virgen. Nota de implementación: NO requiere extensión del motor — la variante puede recordar el bloqueo en estado interno entre should_exit_early y signal_for_bar (reseteado por sesión).

## Notas

Depende conceptualmente de H002 (OBSERVATION): si el mecanismo de H002 no replica en el OOS virgen, H005 pierde su base y se archiva. Orden sugerido: diseñar la variante combinada (H002 + bloqueo) cuando se decida abrir la implementación, y validar ambas capas contra el mismo OOS virgen.

## Resultado final

*(pendiente)*

## Decisión

*(pendiente — se registra como DXXX en research/decisions/)*
