# HXXX — [nombre corto de la hipótesis]

| Campo | Valor |
|---|---|
| **ID** | HXXX |
| **Fecha de registro** | YYYY-MM-DD |
| **Estado** | propuesta / en diseño / testeada / en observación / descartada / promovida |
| **Origen** | [qué diagnóstico, dato u observación la generó — con link] |
| **Estrategia/módulo afectado** | [p.ej. variante de X, módulo de salida, etc.] |

## Hipótesis

[Enunciado medible y falsable. Ej.: "Los trades que no avanzan +0.5R en los
primeros 20 minutos terminan mayoritariamente en stop; cerrarlos anticipado
mejora la expectancia."]

## Mecanismo causal esperado

[POR QUÉ debería funcionar, en términos de microestructura/comportamiento
del mercado — escrito ANTES de medir. Si no se puede explicar, no se mide.]

## Datasets

| Rol | Archivo | Período | ¿Contaminado? |
|---|---|---|---|
| Diseño (in-sample) | `data/processed/...` | ... | [qué hipótesis previas salieron de acá] |
| Out-of-sample (RESERVADO) | `data/processed/...` | ... | debe ser virgen para esta hipótesis |

## Implementación prevista

[Un solo cambio. Parámetros con valores redondos y conservadores, lejos del
óptimo de cualquier diagnóstico. Sin grid search.]

## Métricas principales a observar

[expectancia R, PF, DD, racha, muestra, PnL de los trades afectados por el
cambio (el mecanismo debe replicar, no solo las métricas), por régimen/mes.]

## Criterios de ACEPTACIÓN (pre-registrados — no se renegocian)

1. [ej.: expR(variante) > expR(base) en el OOS]
2. [ej.: los trades eliminados/modificados por la regla deben ser netos
   negativos/positivos también en el OOS — replicación del mecanismo]
3. [ej.: muestra mínima ≥ 30 trades]

## Criterios de DESCARTE

1. [ej.: mejora solo por reducir demasiado la muestra]
2. [ej.: funciona en un período y falla en el otro (flip de signo)]
3. [ej.: empeora mucho el PnL aunque mejore el drawdown]

## Riesgos de curve fitting identificados

[¿De dónde salió el umbral? ¿Cuántas comparaciones implícitas hubo en el
diagnóstico de origen? ¿El dataset de diseño ya generó otras hipótesis?]

## Resultado final

[Se completa al terminar: números clave in-sample y OOS, link a reportes.]

## Decisión

[Link a la ficha DXXX correspondiente y estado final.]
