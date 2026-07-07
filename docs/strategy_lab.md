# Strategy Lab / Strategy Search Engine

Strategy Lab es la Fase 8 del proyecto. Es una fabrica de investigacion para
generar, probar, filtrar y rankear variantes de estrategias de forma
controlada.

No crea ordenes reales, no conecta broker y no habilita paper/live/fondeo. Su
trabajo es descartar muchas variantes fragiles y dejar evidencia reproducible.

## Que es Strategy Lab

Strategy Lab toma una familia de estrategia ya existente y una grilla limitada
de parametros. Para cada combinacion:

1. Crea una `StrategyVariant`.
2. Corre un backtest en modo research.
3. Calcula metricas basicas.
4. Corre Robustness Engine.
5. Evalua Decision Engine.
6. Aplica filtros minimos.
7. Rankea por robustez.
8. Guarda resultados reproducibles en `reports/`.

La variante es una combinacion de parametros. No se modifica la clase de
estrategia ni el backtester.

## Por que no elegir solo por PnL

El PnL total es una metrica facil de sobreoptimizar. Una variante puede ganar
mucho porque:

- tuvo pocos trades excepcionales;
- evito por azar una racha mala;
- se beneficia de un orden historico particular;
- no sobrevive a costos o slippage un poco mayores;
- tiene un drawdown inaceptable;
- tiene expectancia positiva solo por ruido estadistico.

Por eso Strategy Lab no ordena solo por PnL. El ranking penaliza fragilidad.

## Como se evita el overfitting

Strategy Lab reduce el riesgo de overfitting con reglas practicas:

- Grillas pequenas y declaradas antes de correr.
- `--max-variants` obligatorio para limitar la busqueda.
- Ranking por robustez, no por PnL.
- Filtros minimos configurables.
- Monte Carlo y Bootstrap por variante.
- Stress de costos/slippage.
- Bloqueo si depende de top winners.
- Decision Engine como gate final.
- Ninguna variante se promueve a paper solo por ganar una busqueda.

Una busqueda grande sobre un mismo dataset sigue siendo in-sample. El motor no
convierte ese resultado en verdad operativa.

## In-sample, validation y out-of-sample

El flujo recomendado es:

| Etapa | Uso | Regla |
|---|---|---|
| In-sample | Generar ideas y descartar variantes obvias | No habilita paper |
| Validation | Confirmar que el ranking no fue puro ajuste | No tocar la grilla despues |
| Out-of-sample | Test virgen final | Puede alimentar Decision Engine |

La division debe declararse antes de correr. Una variante que gana in-sample
pero falla validation u OOS queda descartada o bloqueada.

## Ranking robusto

El score no usa PnL neto total como criterio principal. Premia:

- mas trades hasta un limite razonable;
- profit factor;
- expectancia R;
- Robustness Engine positivo;
- filtros minimos cumplidos;
- Decision Engine favorable.

Penaliza:

- drawdown alto;
- baja cantidad de trades;
- probabilidad Monte Carlo de terminar negativo;
- probabilidad Monte Carlo de drawdown extremo;
- probabilidad Bootstrap de expectancia <= 0;
- dependencia de pocos ganadores;
- falla ante costos/slippage;
- estados `REJECTED` o `BLOCKED_FOR_PAPER`.

## Filtros minimos

Los filtros configurables son:

- minimo de trades;
- profit factor minimo;
- expectancia R minima;
- drawdown maximo;
- Monte Carlo probability negative maxima;
- Bootstrap probability expectancy <= 0 maxima;
- stress de costos obligatorio;
- dependencia de pocos ganadores bloqueante.

Una variante puede tener buen score relativo y aun asi fallar filtros. Eso es
una senal para investigar, no para operar.

## PAPER_CANDIDATE

`PAPER_CANDIDATE` significa que una estrategia paso los criterios minimos del
Decision Engine y la robustez requerida. No significa aprobacion automatica.

Para paper trading todavia hace falta:

- evidencia fuera de muestra limpia;
- decision humana registrada como `DXXX`;
- no estar bloqueada por Robustness Engine;
- no depender de pocos ganadores;
- sobrevivir costos razonables.

Strategy Lab nunca selecciona automaticamente una estrategia para fondeo.

## Volumen OHLCV y volumen gaussiano

El Strategy Lab puede registrar familias basadas en volumen, pero el dataset
actual solo tiene OHLCV de 1 minuto. Eso permite investigar volumen de vela,
volumen relativo, spikes, dry-up, compresion/expansion y z-score de volumen.

No permite inferir order flow real: no hay bid/ask, delta, footprint, DOM ni
volumen por precio. Por eso una familia `gaussian_volume_*` significa volumen
normalizado por media movil y desviacion estandar, no flujo de ordenes real.

Toda estadistica rolling de volumen debe evitar lookahead. Las utilidades de
Strategy Lab calculan media, desviacion estandar, volumen relativo y z-score
usando barras pasadas (`shift(1)`) para que una barra no use informacion futura
al clasificar su contexto.

## Uso

Ejemplo en Windows PowerShell:

```powershell
python scripts/run_strategy_search.py `
  --symbol MNQ `
  --data data/processed/MNQ_2024_01_2026_06_full_1m_ninjatrader_combined_clean.csv `
  --family rr2_atr_filter `
  --initial-capital 25000 `
  --max-variants 12 `
  --iterations 1000 `
  --seed 42
```

Salidas:

```text
reports/strategy_search_results.csv
reports/strategy_search_summary.md
reports/strategy_search_family_summary.csv
```

Las familias registradas se documentan en `docs/strategy_families.md`. Tambien
se acepta el alias:

- `daytrading_vwap_liquidity_rr2_no_midday_atr_filter`

## Interpretacion de resultados

El CSV contiene una fila por variante con parametros, metricas, robustez,
estado del Decision Engine, filtros y score. El resumen Markdown muestra el
ranking y deja claro si hay `PAPER_CANDIDATE`.

Si no hay candidatas, eso es un resultado valido. Una buena fabrica de
investigacion descarta mucho mas de lo que promueve.

## Correr todas las familias

Para ampliar el universo de investigacion sin elegir una familia a mano:

```powershell
python scripts/run_strategy_search.py `
  --symbol MNQ `
  --data data/processed/MNQ_2024_01_2026_06_full_1m_ninjatrader_combined_clean.csv `
  --family all `
  --initial-capital 25000 `
  --max-variants-per-family 4 `
  --iterations 1000 `
  --seed 42
```

`--family all` recorre todas las familias registradas. Las familias con
estrategia real se evaluan normalmente. Las familias en scaffolding quedan en
el registry y aparecen en los resumenes como no ejecutables, pero no entran al
ciclo de backtest de `all`. Esto evita inventar logica sin tests.

`--max-variants` sigue funcionando para una sola familia. Para `all`, usar
`--max-variants-per-family` mantiene la busqueda acotada.

## Ranking global

Cuando se corre `--family all`, el resumen incluye:

- familias evaluadas;
- familias registradas;
- familias ejecutables;
- familias no ejecutables/scaffolding;
- variantes por familia;
- `PAPER_CANDIDATE` total y por familia;
- top 10 global;
- top 3 por familia;
- familias completamente rechazadas;
- motivos frecuentes de rechazo.

El ranking global sigue sin ordenar por PnL. Una familia puede aparecer con PnL
positivo y quedar descartada si su drawdown es alto, si depende de pocos
ganadores, si falla ante costos/slippage, o si Monte Carlo/Bootstrap muestran
fragilidad. La regla es deliberadamente conservadora: si no hay robustez, no hay
paper.
