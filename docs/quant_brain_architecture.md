# Quant Brain — Arquitectura maestra de nqbot

**Fecha:** 2026-07-05
**Estado:** Fase 1 (este documento)
**Documentos hermanos:** `strategy_decision_log.md` (decisiones),
`../reports/final_vwap_rr2_research_closure.md` (cierre del ciclo anterior)

---

## 1. Visión general

nqbot deja de ser "un bot que ejecuta una estrategia" y pasa a ser una
**plataforma de investigación cuantitativa**: un sistema que piensa como una
mesa quant — formula hipótesis con mecanismo económico, las mide con
protocolo estricto, las valida fuera de muestra, decide con criterios
pre-registrados, documenta todo y **descarta sin dolor**.

El producto principal del sistema no es una estrategia: es un **proceso que
produce y filtra estrategias**. Las estrategias son output descartable; el
proceso y el conocimiento acumulado son el activo.

## 2. Por qué el cambio de paradigma

El ciclo VWAP+Liquidity RR2 (cerrado 2026-07-05) lo demostró empíricamente:

- Una estrategia con backtest ganador en 6 meses (+$1,452, PF 1.31) resultó
  **perdedora en 24 de los ~30 meses** de datos reales. Un "bot con una
  estrategia fija" habría quemado la cuenta con confianza.
- El mismo ciclo produjo **conocimiento replicable** (dos mecanismos que
  funcionan en todos los períodos, cuatro anti-hallazgos que evitan errores
  futuros) porque el proceso era el correcto: hipótesis única, criterio
  pre-registrado, out-of-sample intocado, decision log inmutable.
- Conclusión: lo que escala no es la estrategia — es el pipeline
  datos → hipótesis → prueba → decisión. Eso es el Quant Brain.

## 3. Módulos del Quant Brain

Estado: ✅ existe | 🟡 parcial | ⬜ falta construir

### 3.1 Data Engine ✅
Importar datos reales, validar calidad, mantener datasets limpios.
**Ya existe** y está probado en batalla:
- `src/nqbot/data/loader.py` — multi-formato (CSV genérico, NinjaTrader sin
  header UTC→ET, epoch, date+time), parseo separado de saneo.
- `src/nqbot/data/quality.py` — auditoría bloqueante (APTO/NO APTO):
  duplicados, velas faltantes, nulos, OHLC imposible, volumen cero, gaps,
  timezone, fin de semana, calendario CME de feriados/sesiones parciales.
- `scripts/import_data.py` (raw → processed), `scripts/filter_data_by_date.py`
  (recortes para OOS), `data/raw/` intocable, `data/processed/` auditado.

### 3.2 Market Regime Engine 🟡
Detectar régimen SIN mirar el futuro: tendencia/lateralidad, volatilidad,
expansión/compresión, dirección del día.
**Parcial**: las features causales ya existen pero viven en un script de
diagnóstico (`scripts/diagnose_regime.py`): ATR-20 previo, rango acumulado,
ratio de expansión vs OR, pendientes de VWAP/EMA200, estructura HH/LL.
**Falta**: promoverlas a módulo `src/nqbot/regime/` que etiquete cada barra/
sesión de forma reutilizable, con tests anti-lookahead, para que TODO
backtest reporte métricas por régimen automáticamente.
**Lección incorporada**: los proxies causales de expansión son débiles — el
día tendencial se confirma tarde. El módulo debe exponer esa incertidumbre
(etiquetas causales ≠ etiquetas de cierre de día), nunca ocultarla.

### 3.3 Hypothesis Engine 🟡
Formular hipótesis cuantitativas con formato estándar.
**Parcial**: hoy el proceso es manual (diagnósticos → hipótesis rankeadas →
decision log). **Falta**: formalizar la ficha de hipótesis:
```
id, fecha, origen (qué diagnóstico la generó), mecanismo económico,
predicción medible, dataset de diseño, dataset OOS reservado,
criterio de aceptación pre-registrado, estado, resultado, veredicto
```
Ejemplos del formato (del ciclo anterior y candidatas futuras):
- "Los trades con ATR-20 previo bajo pierden" → VALIDADA (3 períodos).
- "Los trades que no avanzan +0.5R en N minutos suelen terminar en stop"
  → candidata para la fase de gestión dinámica.
- "Las rupturas falsas cerca del VWAP tienen peor expectativa" → sin testear.

### 3.4 Backtest Engine ✅
**Ya existe** y validado: `src/nqbot/backtesting/engine.py` — event-driven,
señal al cierre / fill al open siguiente, stop-first conservador, costos
completos (comisión + slippage + medio spread), sesiones Globex con trade
date real, risk manager integrado (pérdida diaria, max trades, rachas,
bloqueos), verificación de RR planificado, 74 tests.
**Extensión conocida para Fase 5** (única obra pendiente en el motor):
salidas dinámicas gestionadas por la estrategia (time-stop, salida por
no-expansión). Hoy el ciclo de vida es fijo (stop/target/flatten); la
extensión debe ser un cambio controlado y testeado, no un refactor.

### 3.5 Evaluation Engine 🟡
**Parcial**: métricas completas (`metrics.py`: PF, expR, DD mark-to-market,
rachas, Sharpe, long/short, RR ejecutado) + herramientas de análisis
(`analyze_backtest.py`, `compare_strategies.py`, validadores OOS con
detección de solapamiento y veredicto automático).
**Falta**: walk-forward (ventanas rodantes diseño/prueba), análisis de
sensibilidad de parámetros (±20-25% en parámetros clave sin colapso — se usa
para medir fragilidad, NO para elegir el óptimo), y métricas por régimen
integradas (depende de 3.2).

### 3.6 Decision Engine 🟡
Aprobar / observar / descartar, con gates codificados.
**Parcial**: el decision log existe y funciona (6 decisiones registradas,
criterios pre-registrados que ya voltearon a near_vwap y aprobaron el
mecanismo de atr_filter). La guarda de ejecución real existe (doble llave).
**Falta**: codificar los gates como checklist ejecutable (un comando que
tome un experimento y verifique los criterios mínimos contra sus reportes),
y estados formales de hipótesis: `propuesta → en prueba → observación →
aprobada | descartada`.

### 3.7 Research Memory 🟡
Qué se probó, qué funcionó, qué falló — para no repetir experimentos.
**Parcial**: el decision log + reports + el documento de cierre cumplen hoy
ese rol en formato narrativo. **Falta**: registro estructurado y consultable
(`research/` con una ficha por hipótesis, índice de mecanismos validados y
descartados). Contenido inicial ya ganado:
- **Validados**: mediodía 11-13h tóxico; ATR-20 previo bajo = cinta muerta.
- **Descartados**: sesgo por lado (régimen), horario fino (inestable),
  distancia a VWAP como filtro estático (régimen-dependiente).
- **Hechos estructurales**: el edge de la lógica de continuación vive en
  días tendenciales; el día tendencial no es anticipable a la entrada con
  features simples; los trades "re-secuenciados" por filtros de remoción
  tendieron a ser malos (3 de 4 casos).

### 3.8 Strategy Lab ✅ (como práctica) / 🟡 (como módulo)
Crear estrategias de forma controlada. **La práctica ya existe y está
probada**: variantes como subclases finas (un cambio por variante), registry
por nombre, parámetros en config, tests conductuales por filtro, umbrales
redondos lejos del óptimo. **Falta** solo documentar la plantilla como
proceso estándar dentro de la ficha de hipótesis (3.3).

### 3.9 Reporting Engine 🟡
**Parcial**: cada backtest genera summary + trades + equity + PNG; cada
experimento genera CSV + TXT con veredicto; la calidad de datos genera su
reporte. **Falta**: resumen ejecutivo Markdown unificado por experimento
(una página: hipótesis, mecanismo, números clave por régimen/mes/horario,
veredicto y por qué), generado automáticamente al cerrar cada experimento.

### 3.10 Future Execution Layer ✅ (bloqueado por diseño)
`src/nqbot/execution/broker.py`: interfaz definida, doble llave
(`LIVE_TRADING` en .env + `live_trading` en YAML), y aun con ambas llaves
lanza `NotImplementedError`. **Se mantiene bloqueado** hasta que una
estrategia pase los criterios de la sección 6. Paper trading es Fase 6.

## 4. Flujo completo de investigación

```
DATOS            Data Engine: importar → auditar → APTO/NO APTO → processed/
  ↓
CONTEXTO         Regime Engine: etiquetar barras/sesiones (causal)
  ↓
HIPÓTESIS        Hypothesis Engine: ficha formal con mecanismo + predicción
                 + dataset de diseño + OOS reservado + criterio PRE-REGISTRADO
  ↓
IMPLEMENTACIÓN   Strategy Lab: una hipótesis = una variante = un cambio
  ↓
BACKTEST         Backtest Engine: dataset de diseño (in-sample declarado)
  ↓
DIAGNÓSTICO      Evaluation Engine: métricas globales + por régimen/mes/hora,
                 descomposición del delta, sensibilidad
  ↓
VALIDACIÓN       OOS intocado + (cuando exista) walk-forward.
                 El MECANISMO debe replicar, no solo las métricas.
  ↓
DECISIÓN         Decision Engine: aprobar / observar / descartar contra el
                 criterio pre-registrado. Sin renegociación a posteriori.
  ↓
MEMORIA          Research Memory + decision log: registro inmutable.
                 Lo descartado no se re-testea sin evidencia nueva.
```

## 5. Reglas anti-curve-fitting (constitución del sistema)

Codificadas desde la práctica del ciclo anterior — no son aspiraciones, ya
se aplicaron todas:

1. **Una hipótesis = una variante = un cambio.** Nada de paquetes de cambios.
2. **Mecanismo antes que métrica**: si no se puede explicar POR QUÉ debería
   funcionar antes de medirlo, no se mide.
3. **Umbrales redondos y conservadores**, deliberadamente lejos del óptimo
   in-sample (near_vwap: 30 vs borde 40; atr_filter: 8 vs borde 10).
4. **Prohibido el grid search** y probar múltiples valores de un parámetro.
5. **El OOS se define ANTES de mirar los datos** y no se toca. Los datasets
   que generaron una hipótesis quedan marcados como in-sample para ella.
6. **Criterio de aceptación pre-registrado** en el decision log antes de
   correr la validación. No se renegocia después de ver el resultado.
7. **El mecanismo debe replicar, no solo las métricas**: los trades que un
   filtro elimina deben ser malos también en el período nuevo (esta regla
   descartó a near_vwap y validó a atr_filter).
8. **Cortes condicionales de un diagnóstico = hipótesis nuevas**, jamás
   filtros directos.
9. **Solo features causales** en lógica operable; las features de día
   completo son diagnóstico y se marcan como tales.
10. **Muestra mínima** por veredicto (≥30 trades orientativo; subgrupos
    chicos se marcan y no fundan conclusiones).
11. **Toda decisión queda en el decision log, inmutable**: las entradas no
    se reescriben, se agregan.

## 6. Criterios mínimos para pasar a paper trading

Borrador PRE-REGISTRADO (a ratificar antes del primer candidato; una vez
ratificado, no se negocia):

1. **Expectancia R > 0 en OOS nunca visto**, con ≥ 100 trades o cobertura de
   al menos dos regímenes de mercado distintos.
2. **Profit factor ≥ 1.15 en el OOS completo** y positivo en la mayoría de
   sus sub-períodos (sin depender de un solo tramo).
3. **Mecanismo económico explicable** documentado antes de la validación.
4. **Walk-forward**: expectancia positiva en ≥ 60% de las ventanas, sin
   ninguna ventana catastrófica (pérdida > 2x el drawdown de diseño).
5. **Sensibilidad**: variar ±25% los parámetros clave no invierte el signo
   de la expectancia (mide fragilidad; no se usa para re-elegir valores).
6. **Drawdown OOS** compatible con el risk manager (< 10% del capital) y
   racha perdedora sobrevivible con el sizing configurado.
7. **Decision log completo**: hipótesis, criterio pre-registrado, resultado
   y aprobación explícita registrada.

Ninguna estrategia actual cumple esto — por eso no hay nada en paper.

## 7. Qué ya existe (inventario honesto)

- Pipeline de datos completo con gate de calidad y calendario CME. ✅
- Motor de backtesting event-driven sin lookahead, con costos realistas,
  risk manager y 74 tests. ✅
- Simulador de ejecución conservador (stop-first, gaps, spread). ✅
- Herramientas de análisis: post-backtest, comparación de variantes,
  validadores OOS con veredicto automático, diagnósticos de edge y régimen. ✅
- Protocolo de investigación funcionando (decision log con 6 decisiones,
  criterios pre-registrados aplicados de verdad). ✅
- Ejecución real bloqueada por doble llave. ✅
- ~30 meses de MNQ 1m real limpio (2024 completo, 2025, H1-2026). ✅
- Conocimiento validado y anti-hallazgos documentados (sección 3.7). ✅

## 8. Qué falta construir

| Pieza | Módulo | Prioridad |
|---|---|---|
| Research Memory estructurada (`research/`, ficha por hipótesis) | 3.7 | Alta (Fase 2) |
| Decision Engine con gates ejecutables y estados formales | 3.6 | Alta (Fase 2) |
| Market Regime Engine como módulo (`src/nqbot/regime/`) + métricas por régimen en todo backtest | 3.2 + 3.5 | Alta (Fase 3) |
| Ficha formal de hipótesis + plantilla de experimento | 3.3 | Media (Fase 4) |
| Extensión controlada del motor: salidas dinámicas in-trade | 3.4 | Media (Fase 5) |
| Walk-forward + sensibilidad de parámetros | 3.5 | Media (Fase 5) |
| Resumen ejecutivo Markdown automático por experimento | 3.9 | Baja (transversal) |
| Paper trading engine (feed vivo + simulator reutilizado) | 3.10 | Solo tras Fase 5 exitosa |

## 9. Roadmap por fases

**Fase 1 — Arquitectura Quant Brain.** Este documento. ✅

**Fase 2 — Research Memory + Decision Engine.**
Estructura `research/` con ficha por hipótesis (cargar retroactivamente las
7 del ciclo RR2), estados formales, y checklist ejecutable de gates.
*Done cuando*: cualquier hipótesis pasada o futura se consulta en un solo
lugar y el gate de paper es un comando, no un recuerdo.

**Fase 3 — Market Regime Engine.**
`src/nqbot/regime/` con etiquetado causal (volatilidad, expansión,
estructura, dirección) + tests anti-lookahead + integración en Evaluation
(todo backtest reporta por régimen). *Done cuando*: `compare_strategies` y
los validadores muestran métricas por régimen sin código ad-hoc.

**Fase 4 — Hypothesis Engine.**
Plantilla formal, pipeline diagnóstico→ficha, y backlog priorizado inicial
(empezando por las candidatas de gestión dinámica ya identificadas).
*Done cuando*: ninguna variante se implementa sin ficha previa.

**Fase 5 — Investigación: gestión dinámica de salida.**
Primera línea nueva de investigación (la que el cierre del ciclo RR2
recomendó): time-stop, salida por no-avance (+0.5R en N min), salida por
día sin expansión. Requiere la extensión del motor (3.4) hecha con tests.
Protocolo completo: diseño en un período, OOS reservado, criterios
pre-registrados. *Done cuando*: cada hipótesis de salida tiene veredicto.

**Fase 6 — Paper trading.**
Solo si algo pasa los criterios de la sección 6. Feed en vivo + el mismo
ExecutionSimulator + el mismo risk manager. La doble llave de live sigue
cerrada hasta que el paper demuestre correspondencia con el backtest.

## 10. Reglas de gobierno del proyecto

- El decision log es la única fuente de verdad sobre decisiones. Inmutable.
- Nada avanza de fase sin cumplir el "done" de la fase anterior.
- **Sigue vigente**: no optimizar filtros de entrada de la familia RR2; sus
  estrategias quedan como benchmark y biblioteca de referencia.
- Toda esta arquitectura está al servicio de una sola pregunta, siempre la
  misma: *¿esta idea tiene edge real, o solo memoria del pasado?*
