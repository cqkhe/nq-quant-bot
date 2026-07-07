# Research Factory Workflow

La Research Factory automatiza el flujo completo de investigacion:

```text
hypothesis -> backtest -> trades.csv -> robustness -> decision engine -> decision log
```

El objetivo no es encontrar una estrategia que gane por fuerza bruta. El objetivo
es que cada idea quede evaluada de forma reproducible, con evidencia, riesgos y
bloqueos operativos claros.

## Principios

- Solo modo research/backtest.
- No modifica estrategias.
- No modifica reglas de entrada.
- No modifica reglas de salida.
- No toca el risk manager.
- No conecta broker.
- No agrega paper/live/fondeo.
- No optimiza parametros.
- No cambia resultados historicos ya generados.

## Flujo completo

### 1. Hypothesis

La investigacion empieza con una hipotesis registrada o una idea explicitada por
CLI. Si existe una ficha `HXXX`, se pasa con `--hypothesis-id`.

La hipotesis no se edita durante el workflow. El script solo la referencia para
dejar trazabilidad.

### 2. Backtest

El workflow ejecuta el backtest usando el entrypoint existente `main.py`:

```powershell
python main.py --mode backtest --symbol MNQ --strategy <estrategia> --data <csv>
```

La carpeta generada queda bajo `reports/` con el formato normal del proyecto:

```text
reports/<timestamp>_<symbol>_<strategy>/
```

### 3. trades.csv

El workflow detecta el `trades.csv` generado por el backtest. Ese archivo es la
entrada canonica para robustez cuantitativa: a partir de ahi no se toca la
estrategia ni se recalculan reglas.

Si no hay `trades.csv`, el workflow falla. Una estrategia sin operaciones no
tiene muestra para Monte Carlo, Bootstrap ni Decision Engine completo.

### 4. Robustness Engine

Sobre `trades.csv`, el workflow corre:

- Monte Carlo.
- Bootstrap.
- Risk of ruin.
- Drawdown probability.
- Stress tests.
- Dependencia de pocos ganadores.

Los resultados se guardan dentro de la misma carpeta del backtest:

```text
reports/<backtest>/robustness_report.csv
reports/<backtest>/robustness_report_summary.md
```

Esto evita pisar reportes historicos globales.

### 5. Decision Engine

El workflow calcula las metricas tradicionales desde la carpeta de reporte:

- trades.
- PnL neto.
- profit factor.
- expectancia R.
- max drawdown.
- racha perdedora.
- meses positivos.
- PnL sin top 5 ganadores.

Luego agrega los campos opcionales de robustez:

- `mc_probability_negative`
- `mc_probability_extreme_drawdown`
- `bootstrap_probability_expectancy_le_zero`
- `depends_on_few_winners`
- `cost_stress_survives`

Si estos campos muestran fragilidad, una estrategia no puede ser
`PAPER_CANDIDATE`.

El resumen del Decision Engine se guarda en:

```text
reports/<backtest>/decision_engine_summary.md
```

### 6. Decision log / Research Memory

El workflow genera un registro estructurado en:

```text
research/experiments/WORKFLOW_<timestamp>_<hypothesis>_<strategy>.md
```

Ese registro incluye:

- hipotesis relacionada, si fue declarada;
- dataset usado;
- carpeta de backtest;
- `trades.csv`;
- reporte de robustez;
- estado final del Decision Engine;
- motivos del bloqueo o promocion.

Importante: este archivo no reemplaza una decision humana `DXXX`. Si el estado
fuera `PAPER_CANDIDATE`, todavia hace falta una decision explicita en
`research/decisions/`.

## Uso

Ejemplo principal:

```powershell
python scripts/run_research_workflow.py `
  --strategy daytrading_vwap_liquidity_rr2_no_midday_atr_filter `
  --symbol MNQ `
  --data data/processed/MNQ_2024_01_2026_06_full_1m_ninjatrader_combined_clean.csv `
  --initial-capital 25000 `
  --iterations 10000 `
  --seed 42 `
  --hypothesis-id H002
```

Metadata opcional para Decision Engine:

```powershell
  --oos si `
  --overlaps no
```

Si `--oos` o `--overlaps` no se declaran, el Decision Engine los considera no
evaluables. Eso bloquea `PAPER_CANDIDATE` de forma conservadora.

## Salida esperada

El script imprime un veredicto claro:

```text
RESEARCH WORKFLOW COMPLETADO
Estrategia: ...
Reporte:    reports/<backtest>
Trades:     reports/<backtest>/trades.csv
Robustez:   ROBUSTA o FRAGIL
Decision:   PAPER_CANDIDATE / BLOCKED_FOR_PAPER / OBSERVATION / ...
Registro:   research/experiments/WORKFLOW_...
```

## Interpretacion

- `PAPER_CANDIDATE`: cumple criterios numericos, validacion declarada y robustez.
  No es aprobacion automatica.
- `BLOCKED_FOR_PAPER`: parece de nivel paper en performance, pero falla o falta
  validacion/robustez.
- `APPROVED_FOR_RESEARCH`: hay senales positivas, pero todavia no alcanza para
  paper.
- `OBSERVATION`: muestra insuficiente o evidencia mixta.
- `REJECTED`: sin edge con muestra suficiente.

La fabrica no decide por intuicion. Solo produce evidencia auditable.
