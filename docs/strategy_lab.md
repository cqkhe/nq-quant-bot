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
```

Familias disponibles inicialmente:

- `rr2_atr_filter`
- `base_vwap_ema`

Tambien se acepta el alias:

- `daytrading_vwap_liquidity_rr2_no_midday_atr_filter`

## Interpretacion de resultados

El CSV contiene una fila por variante con parametros, metricas, robustez,
estado del Decision Engine, filtros y score. El resumen Markdown muestra el
ranking y deja claro si hay `PAPER_CANDIDATE`.

Si no hay candidatas, eso es un resultado valido. Una buena fabrica de
investigacion descarta mucho mas de lo que promueve.
