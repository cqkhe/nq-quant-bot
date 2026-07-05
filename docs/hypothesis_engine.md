# Hypothesis Engine (Quant Brain, Fase 4)

**Módulo:** `src/nqbot/research/hypothesis_engine.py` (+ modelos en `models.py`)
**CLI:** `scripts/create_hypothesis.py`
**Tests:** `tests/test_hypothesis_engine.py`

## Qué es

El componente que estructura la investigación ANTES de que exista código:
toda idea entra al sistema como una `Hypothesis` con identidad (HNNN, título,
tipo), enunciado medible, **mecanismo causal**, plan de validación (datasets
de diseño y out-of-sample, criterios de aceptación y de descarte) y una
**prioridad calculada** — y recién después de eso puede implementarse.

Estados: `PROPOSED → DESIGNED → READY_FOR_TEST → TESTED →
{PROMOTED | OBSERVATION | REJECTED}` (+ `ARCHIVED`).
Tipos: ENTRY_LOGIC, EXIT_LOGIC, RISK_MANAGEMENT, MARKET_REGIME, FILTER,
POSITION_SIZING, EXECUTION, DATA_QUALITY.

## Cómo se usa

```bash
# esqueleto mínimo (PROPOSED): el motor reporta qué falta para DESIGNED
python scripts/create_hypothesis.py --id H005 --title "Mi idea" --type EXIT_LOGIC

# ficha completa desde la línea de comandos
python scripts/create_hypothesis.py --id H005 --title "..." --type FILTER \
    --statement "..." --mechanism "..." --impact ALTO --clarity MEDIA --cf-risk MEDIO \
    --design-dataset "..." --oos-dataset "PENDIENTE jul-2026+" --oos-pending \
    --acceptance "..." --rejection "..."
```

La ficha se escribe en `research/hypotheses/HNNN_<slug>.md` (el motor se
niega a pisar fichas existentes) y la fila se registra a mano en
`research/research_memory_index.md`.

## Por qué una hipótesis se registra ANTES de mirar resultados

Una hipótesis escrita después de ver los números no es una hipótesis: es una
descripción del pasado con forma de predicción. El ciclo H001 lo demostró en
ambas direcciones — near_vwap (criterios escritos antes, resultado adverso,
descarte limpio y barato) versus el contraejemplo clásico de la industria
(renegociar el criterio al ver el resultado). El registro previo convierte
"me parece que funciona" en una apuesta falsable con condiciones de derrota
firmadas de antemano.

## Cómo evita curve fitting

1. **Mecanismo obligatorio**: `missing_for_design` no deja congelar una
   ficha sin explicación causal. Sin POR QUÉ, no se mide.
2. **OOS declarado al crear la ficha** y verificado contra el **registro de
   contaminación** (`CONTAMINATED_DATASETS`): todos los datasets actuales
   fueron mirados durante H001, así que usarlos como OOS es error duro del
   validador. El único OOS legítimo hoy es `oos_pending=True` (datos
   futuros jul-2026+ o histórico 2023 sin adquirir) — la única garantía
   física de que nadie lo miró.
3. **Criterios de aceptación Y de descarte pre-registrados**, incluyendo la
   regla que decidió el ciclo H001: el mecanismo debe replicar (los trades
   afectados por la regla deben comportarse igual en el OOS), no solo las
   métricas.
4. **Prioridad calculada, no vibras**: `impacto + claridad causal − riesgo
   de curve fitting`, con escala fija (≥5 ALTA, 3-4 MEDIA, ≤2 BAJA). La
   fórmula codifica las lecciones: H004 (filtro de entrada por régimen,
   riesgo CF alto, techo conocido) sale BAJA aunque suene atractiva; las
   salidas dinámicas (mecanismo claro, ataca el hallazgo central) salen ALTA.

## Conexiones con el resto del Quant Brain

- **Research Memory**: la ficha vive en `research/hypotheses/` y su fila en
  el índice; los estados del motor son los del índice. Lo descartado queda
  registrado y el validador de contaminación impide reciclar sus datos.
- **Decision Engine**: cuando una hipótesis llega a TESTED, sus reportes se
  evalúan con `scripts/evaluate_experiment.py`; la decisión final es una
  ficha DXXX que actualiza el estado (PROMOTED/OBSERVATION/REJECTED). Los
  criterios de aceptación de la ficha y los gates del Decision Engine son
  complementarios: la ficha define el éxito del experimento, el gate define
  el mínimo para paper.
- **Market Regime Engine**: las fichas expresan condiciones de régimen con
  el vocabulario estándar de la Fase 3 (`vol_regime`, `expansion_ratio`,
  `trade_vs_bias`), en lugar de redefinir features ad-hoc por experimento
  (H003 y H004 ya lo usan).

## Hipótesis registradas al crear el motor

| ID | Título | Tipo | Prioridad | Estado |
|---|---|---|---|---|
| H002 | Salida dinámica si no alcanza +0.5R en X min | EXIT_LOGIC | ALTA | PROPOSED |
| H003 | Salida por expansión fallida post-entrada | EXIT_LOGIC | ALTA | PROPOSED |
| H004 | Entradas solo bajo regímenes causales favorables | MARKET_REGIME | BAJA | PROPOSED |

H002 y H003 requieren la extensión del motor de backtesting para salidas
dinámicas (única obra pendiente en el motor, Fase 5): ninguna se implementa
hasta que esa extensión exista con tests propios.
