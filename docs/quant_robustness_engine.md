# Quant Robustness Engine

El Quant Robustness Engine es la Fase 6 del Quant Brain. Su objetivo es evaluar
si una estrategia o experimento sigue siendo defendible cuando el orden de los
trades cambia, la muestra se remuestrea, los costos suben o los mejores trades
desaparecen.

No crea estrategias nuevas, no modifica entradas, no modifica salidas, no corre
backtests y no conecta broker. Trabaja sobre trades ya generados.

## Por qué un backtest positivo no alcanza

Un backtest positivo puede esconder fragilidad:

- El resultado puede depender de pocos ganadores extremos.
- El orden real de los trades puede producir un drawdown mucho peor que el visto.
- La expectancia puede no ser estadísticamente distinta de cero.
- Costos, slippage o degradación mínima del edge pueden borrar la ventaja.
- La muestra puede haber tenido suerte.

Por eso el backtest es evidencia inicial, no prueba final.

## Monte Carlo

Monte Carlo simula miles de curvas de equity usando la distribución histórica de
trades. El módulo permite dos usos:

- Remuestreo con reemplazo: estima posibles secuencias futuras usando trades
  parecidos a los observados.
- Reordenamiento sin reemplazo: mantiene los mismos trades y cambia solo el path.

Métricas principales:

- Distribución de PnL final.
- Distribución de max drawdown.
- Distribución de rachas perdedoras.
- Probabilidad de terminar negativo.
- Probabilidad de superar un drawdown definido.
- Percentiles 5%, 50% y 95%.

La seed fija hace que el resultado sea reproducible.

## Bootstrap

Bootstrap remuestrea trades con reemplazo para estimar intervalos de confianza.
Responde si las métricas centrales son estables o si podrían ser producto de la
muestra observada.

Calcula:

- Intervalo de confianza de expectancia R.
- Intervalo de confianza de profit factor.
- Intervalo de confianza de winrate.
- Intervalo de confianza de PnL medio por trade.
- Probabilidad de expectancia <= 0.

Si el CSV no trae `r_multiple`, el reporte puede calcular PnL medio, winrate y
profit factor, pero la expectancia R queda como no disponible.

## Riesgo

El módulo de riesgo usa simulación empírica para estimar:

- Risk of ruin aproximado.
- Probabilidad de perder X% del capital.
- Capital mínimo sugerido según drawdown simulado.
- Peor racha esperada.
- Drawdown esperado y drawdown extremo en percentil 95.

Estos números no prometen el futuro; son una forma disciplinada de preguntar
"qué tan feo puede ponerse si el edge observado es real pero el orden no ayuda".

## Stress Tests

El módulo de stress degrada los trades existentes:

- Aumenta costos por trade.
- Modela slippage adicional.
- Reduce ganancias promedio.
- Aumenta pérdidas promedio.
- Elimina top 5 o top 10 ganadores.
- Simula degradación del edge.

Una estrategia robusta no debería necesitar que todo salga perfecto para seguir
teniendo edge.

## Uso

Desde la raíz del proyecto:

```powershell
python scripts/robustness_report.py --trades reports/ARCHIVO_DE_TRADES.csv --initial-capital 25000 --iterations 10000 --seed 42
```

Genera:

- `reports/robustness_report.csv`
- `reports/robustness_report_summary.md`

El CSV de trades debe tener una columna de PnL, preferentemente `pnl_net`. Si
tiene `r_multiple`, el bootstrap también reporta expectancia R.

## Interpretación rápida

- `probability_negative`: probabilidad Monte Carlo de terminar con PnL final < 0.
- `max_drawdown_pct_p95`: drawdown que solo el 5% de simulaciones empeora.
- `worst_losing_streak_p95`: racha perdedora esperada en escenario severo.
- `probability_expectancy_le_zero`: probabilidad bootstrap de que la expectancia
  no sea positiva.
- `risk_of_ruin`: probabilidad simulada de tocar el umbral de ruina configurado.
- `remove_top_5_winners`: prueba si el resultado depende de pocos trades.
- `costs_plus_reasonable`: prueba si el edge sobrevive a costos más altos.

## Conexión con Decision Engine

`ExperimentMetrics` acepta campos opcionales de robustez:

- `mc_probability_negative`
- `mc_probability_extreme_drawdown`
- `bootstrap_probability_expectancy_le_zero`
- `depends_on_few_winners`
- `cost_stress_survives`

Si estos campos están presentes y fallan, la estrategia no puede ser
`PAPER_CANDIDATE`. Queda `BLOCKED_FOR_PAPER` aunque sus métricas tradicionales
parezcan de nivel paper.

Umbrales sugeridos por defecto:

- Monte Carlo probabilidad de terminar negativo <= 20%.
- Monte Carlo probabilidad de drawdown extremo <= 20%.
- Bootstrap probabilidad de expectancia <= 0 <= 25%.
- No depender de top 5 ganadores.
- Sobrevivir costos razonablemente más altos.

## Criterios mínimos sugeridos para paper trading

Antes de proponer paper trading, una estrategia debería cumplir:

- Criterios existentes del Decision Engine: muestra, PF, expectancia, drawdown,
  OOS limpio y sin contaminación de diseño.
- Robustez Monte Carlo sin probabilidad alta de terminar negativo.
- Drawdown extremo compatible con el capital disponible.
- Bootstrap sin probabilidad alta de expectancia no positiva.
- PnL todavía positivo sin los 5 mejores ganadores.
- Edge todavía positivo con costos más altos.

`PAPER_CANDIDATE` no es aprobación automática. Solo habilita registrar una
decisión humana explícita en `research/decisions/`.
