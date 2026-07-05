# Composición de regímenes de mercado

- **Dataset:** `data/processed/MNQ_2024_full_1m_ninjatrader_combined_clean.csv`
- **Período:** 2024-01-02 09:30:00 → 2024-12-31 15:59:00 (284 sesiones RTH, 98,890 barras)
- **Motor:** `nqbot.regime` (100% causal: sin información futura; la
  volatilidad se mide contra las sesiones previas, no contra el dataset).

## Volatilidad

| Etiqueta | % barras | % sesiones (dominante) |
|---|---|---|
| alta | 43.4% | 43.3% |
| baja | 33.8% | 44.0% |
| media | 19.1% | 9.2% |
| no_clasificable | 3.8% | 3.5% |

## Tendencia

| Etiqueta | % barras | % sesiones (dominante) |
|---|---|---|
| tendencia_alcista | 42.4% | 47.2% |
| tendencia_bajista | 31.6% | 31.7% |
| lateral | 25.9% | 21.1% |
| no_clasificable | 0.0% | 0.0% |

## Expansión

| Etiqueta | % barras | % sesiones (dominante) |
|---|---|---|
| neutral | 43.8% | 43.3% |
| expansion | 36.7% | 40.1% |
| compresion | 11.7% | 7.4% |
| no_clasificable | 7.9% | 9.2% |

## Sesgo direccional

| Etiqueta | % barras | % sesiones (dominante) |
|---|---|---|
| alcista | 44.3% | 44.4% |
| bajista | 37.9% | 38.4% |
| neutral | 17.8% | 17.3% |

## Cruce tendencia × volatilidad (% de barras clasificadas)

| tendencia \ vol | alta | baja | media |
|---|---|---|---|
| lateral | 13.9% | 7.6% | 4.6% |
| tendencia_alcista | 12.7% | 21.1% | 8.6% |
| tendencia_bajista | 18.4% | 6.4% | 6.7% |

## Evolución mensual (% de barras)

| mes | expansión | tendencia | vol alta |
|---|---|---|---|
| 2024-01 | 40.4% | 73.0% | 25.3% |
| 2024-02 | 36.2% | 76.0% | 38.0% |
| 2024-03 | 24.6% | 69.2% | 39.8% |
| 2024-04 | 44.5% | 72.5% | 54.8% |
| 2024-05 | 28.9% | 73.5% | 32.8% |
| 2024-06 | 38.3% | 70.4% | 48.4% |
| 2024-07 | 44.4% | 77.5% | 61.2% |
| 2024-08 | 45.9% | 74.0% | 37.0% |
| 2024-09 | 49.8% | 74.5% | 37.0% |
| 2024-10 | 29.7% | 74.7% | 43.1% |
| 2024-11 | 28.7% | 74.2% | 48.1% |
| 2024-12 | 27.7% | 78.6% | 56.0% |

> Nota: 'no_clasificable' = warmup de indicadores, rango inicial
> incompleto o historia de volatilidad insuficiente. El motor prefiere
> no etiquetar antes que etiquetar mirando el futuro.
