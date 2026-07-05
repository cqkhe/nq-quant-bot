# nqbot — Plataforma cuantitativa para futuros NQ/MNQ

Plataforma modular de trading algorítmico en Python para futuros del Nasdaq
(NQ / MNQ), pensada para **investigar, backtestear, validar y — recién al
final — operar** estrategias intradía de forma controlada.

> ⚠️ **Estado actual: fase 1 (backtesting).** El bot NO opera dinero real.
> La ejecución real está deshabilitada por diseño con doble llave de
> seguridad (ver [Seguridad](#seguridad)).

---

## Inicio rápido

```bash
# 1. Instalar dependencias (Python >= 3.10)
pip install -r requirements.txt

# 2. Generar datos sintéticos de prueba (o usar un CSV propio)
python scripts/generate_sample_data.py --days 60 --out data/MNQ_1m_sample.csv

# 3. Correr el backtest
python main.py --mode backtest --symbol MNQ --strategy base_vwap_ema --data data/MNQ_1m_sample.csv

# 4. Correr los tests
python -m pytest -q
```

Cada corrida imprime el resumen de performance en consola y guarda en
`reports/<timestamp>_<símbolo>_<estrategia>/`:

| Archivo            | Contenido                                        |
|--------------------|--------------------------------------------------|
| `summary.txt`      | métricas principales (mismo texto que consola)   |
| `trades.csv`       | todas las operaciones con su detalle completo    |
| `equity_curve.csv` | equity mark-to-market barra a barra              |
| `equity_curve.png` | curva de capital + drawdown                      |

El log detallado de **cada decisión** (señal, descarte, fill, salida,
bloqueo de riesgo) queda en `logs/`.

---

## Datos reales: importación y control de calidad

### Flujo de trabajo

```bash
# 1. Dejar el CSV original del proveedor en data/raw/ (nunca se modifica)
# 2. Importarlo: audita calidad y, solo si es APTO, escribe la versión limpia
python scripts/import_data.py --input data/raw/MNQ_2025.csv

# 3. Backtestear siempre contra data/processed/
python main.py --mode backtest --symbol MNQ --strategy base_vwap_ema --data data/processed/MNQ_2025_clean.csv
```

### Formato esperado

CSV OHLCV de 1 minuto con timestamps en hora del exchange (ET):

```csv
datetime,open,high,low,close,volume
2026-01-05 09:30:00,21000.25,21005.50,20998.00,21003.75,1523
```

El loader acepta alias comunes (`o/h/l/c/vol`, `timestamp`, `date`+`time`
separados, epoch en segundos o milisegundos). Si los timestamps traen offset
de timezone, se convierten automáticamente a ET y queda registrado en el
reporte de calidad.

### Gate de calidad (bloqueante)

Antes de **cada** backtest se audita el dataset y se escribe
`reports/data_quality_report.txt`. Si el veredicto es **NO APTO**, el
backtest no corre (exit code 4). Chequeos:

| Chequeo | Bloquea si… |
|---|---|
| Timestamps duplicados | > `max_duplicate_pct` |
| Velas faltantes en la ventana operada | > `max_missing_bars_pct` |
| Valores nulos en OHLC | > `max_nan_pct` |
| Precios incoherentes (high<low, OHLC imposible, precios ≤ 0) | > `max_incoherent_pct` |
| Volumen cero en la ventana operada | > `max_zero_volume_pct` |
| Gaps intra-sesión > `max_gap_minutes` | nunca (se reportan como warning) |
| Barras en fin de semana | siempre |
| Datos que parecen UTC (masa horaria desplazada +4/+5h del RTH) | siempre |

Por debajo del umbral el problema queda como WARNING y el saneador lo
repara/descarta. Umbrales en `config.yaml → data_quality`. Para debugging
existe `--ignore-data-quality` (backtest) y `--force` (importación).

> Los datos de `scripts/generate_sample_data.py` son **sintéticos**: sirven
> para validar la mecánica del motor, **no** para evaluar el edge de una
> estrategia. Para investigación real usar datos históricos de un proveedor
> (Databento, Polygon, CME DataMine, el broker).

### Sesiones del Nasdaq Futures

Los futuros operan casi 24 h (Globex). El día de *trading* no es el día
calendario: la sesión del martes abre el lunes 18:00 ET, y el motor asigna
cada barra a su sesión real. Ventanas configurables en `config.yaml → session`:

| Ventana | Horario ET (default) |
|---|---|
| `overnight` | 18:00 → 04:00 (cruza medianoche) |
| `premarket` | 04:00 → 09:30 |
| `regular` (RTH) | 09:30 → 16:00 |
| `all` | 18:00 → 17:00 |

`trade_session` define cuál opera el bot (default `regular`): los datos fuera
de esa ventana se filtran antes del backtest, y `flatten_time` (cierre forzado
de posiciones) solo aplica dentro de ella. La estrategia base está pensada y
calibrada para `regular`; operar otras ventanas requiere revisar sus parámetros.

---

## Arquitectura

```
nq-quant-bot/
├── main.py                     # CLI: backtest | paper | live
├── config/config.yaml          # TODO parámetro tunable vive acá
├── src/nqbot/
│   ├── config/                 # YAML -> dataclasses tipadas e inmutables
│   ├── data/                   # loader CSV + auditoría de calidad (quality.py) + saneo
│   ├── indicators/             # EMA, VWAP sesión, vol. relativo, estructura, niveles
│   ├── strategies/             # Strategy ABC + registry + base_vwap_ema
│   ├── risk/                   # RiskManager (bloqueos) + position sizing
│   ├── execution/              # simulador de fills + interfaz broker (guardada)
│   ├── backtesting/            # motor event-driven + métricas + reportes
│   ├── portfolio/              # estado de cuenta
│   └── utils/                  # logging + sesiones Globex (trade date, ventanas)
├── tests/                      # pytest: matemática crítica verificada a mano
├── scripts/                    # import_data.py (raw -> processed) + datos sintéticos
├── notebooks/                  # investigación exploratoria (nada operable vive acá)
├── data/raw/                   # CSVs originales del proveedor (intocables)
├── data/processed/             # datos auditados y limpios (lo que se backtestea)
├── logs/ · reports/            # salidas (gitignoradas)
└── requirements.txt · .env.example
```

**Flujo de una barra en el motor** (orden crítico, sin lookahead):

1. Llenar la entrada pendiente (señal de la barra anterior) al **open**.
2. Evaluar stop / target de la posición abierta contra el rango de la barra.
3. Flatten forzado por horario (`flatten_time`) o última barra de la sesión.
4. Solo si está flat: pedir señal a la estrategia (al **cierre**), pasarla
   por Risk Manager y position sizing, y dejarla pendiente para el próximo open.
5. Marcar equity mark-to-market.

---

## Estrategia base: `base_vwap_ema`

Pullback a valor con filtro de tendencia y volumen. Es deliberadamente
simple: su función es **validar el motor** y servir de línea base
estadística. Setup long (short = espejo):

1. **Régimen**: cierre > EMA200, EMA13 > EMA25 > EMA55, cierre > VWAP de sesión.
2. **Pullback**: en las últimas N barras el precio visitó la EMA25 o el VWAP.
3. **Reanudación**: barra alcista que cierra sobre la EMA13.
4. **Volumen**: volumen relativo ≥ umbral configurable.
5. **Stop técnico**: mínimo del pullback − colchón de ticks.
6. **Target**: RR configurable (default 2R) sobre el riesgo real del fill.

Además expone contexto de estructura (swings confirmados sin lookahead,
PDH/PDL como zonas de liquidez) para iterar versiones con confluencia.

Parámetros en `config/config.yaml` → `strategy.base_vwap_ema`.

## Estrategia day trading: `daytrading_vwap_liquidity_rr2`

Day trading puro sobre MNQ/NQ en sesión regular, **RR fijo 2:1** (si el stop
es de 20 pts, el target es de 40). Base: price action + VWAP + EMAs +
liquidez + volumen + estructura intradía. Setup long (short = espejo):

1. **Régimen**: cierre > EMA200, EMA13 > EMA25 > EMA55 con **pendiente mínima**
   de EMA55 (EMAs planas o mezcladas = no operar).
2. **Valor**: cierre sobre el VWAP de sesión pero a menos de
   `max_vwap_distance_points` (no perseguir precio extendido).
3. **Estructura intradía**: el rango inicial (`opening_range_minutes`, default
   30 min) debe estar cerrado y el precio del lado comprador de su punto medio.
4. **Gatillo**: pullback a VWAP/EMA25 en las últimas N barras + barra de
   rechazo alcista (cierra alcista, sobre la EMA13 y en el 40% superior de su
   rango) + volumen relativo ≥ 1.10.
5. **Stop técnico**: bajo el mínimo del pullback y el último **swing low
   intradía confirmado** (los swings de sesiones anteriores no cuentan), con
   colchón de ticks. Rechazado si queda fuera de `[min_stop_points, max_stop_points]`.
6. **Target**: siempre `rr` × riesgo (default 2.0), calculado sobre el fill
   real; el motor valida y loguea el RR planificado de cada entrada.

Garantías intradía: sin señales en la apertura inmediata ni mientras se forma
el rango inicial, última entrada en `entry_cutoff` (15:15), flatten obligatorio
en `flatten_time` (15:50): **ninguna posición pasa la noche**. Los límites
diarios (trades, pérdida máxima, rachas) los impone el Risk Manager.

```bash
python main.py --mode backtest --symbol MNQ --strategy daytrading_vwap_liquidity_rr2 --data data/processed/MNQ_1m.csv
```

Parámetros en `config/config.yaml` → `strategy.daytrading_vwap_liquidity_rr2`
(valores redondos y lógicos, **no optimizados contra backtests**).

### Arquitectura Quant Brain

El proyecto evolucionó de "bot con una estrategia" a **plataforma de
investigación cuantitativa**. La arquitectura maestra (módulos, flujo de
investigación, reglas anti-curve-fitting, criterios para paper trading y
roadmap) está en **`docs/quant_brain_architecture.md`**. El ciclo de la
familia VWAP+RR2 quedó cerrado (`reports/final_vwap_rr2_research_closure.md`):
sus estrategias son benchmark y biblioteca, no candidatas operativas.

La **memoria de investigación** vive en `research/`: toda hipótesis, su
estado y su decisión están indexados en **`research/research_memory_index.md`**
(qué se probó, qué replicó, qué quedó descartado y por qué — para no repetir
experimentos inútiles). Reglas y flujo en `research/README.md`.

### Estado de las estrategias y variantes

El gobierno de qué estrategia es benchmark, cuál está en evaluación y con qué
criterio se decide vive en **`docs/strategy_decision_log.md`**. Estado actual:
la original es el benchmark; la variante `_no_midday` (sin entradas
11:00-12:59) es candidata **pendiente de validación out-of-sample**:

```bash
python scripts/validate_no_midday.py --data data/processed/DATOS_NUEVOS_clean.csv
```

Regla vigente: no se optimizan parámetros ni se crean variantes hasta
completar esa validación. Herramientas de análisis:
`scripts/analyze_backtest.py` (desglose post-backtest de un reporte) y
`scripts/compare_strategies.py` (N estrategias sobre un mismo dataset).

### Agregar una estrategia nueva

1. Crear `src/nqbot/strategies/mi_estrategia.py` heredando de `Strategy`
   (implementar `prepare()` y `signal_for_bar()`).
2. Registrarla en `src/nqbot/strategies/registry.py`.
3. Agregar sus parámetros bajo `strategy.mi_estrategia` en el YAML.
4. Correr: `python main.py --mode backtest --strategy mi_estrategia ...`

---

## Gestión de riesgo

Todo configurable en `config.yaml`; cualquier violación **bloquea nuevas
entradas hasta la sesión siguiente** y queda logueada:

- **Riesgo por operación**: % del equity (default 0.5%). El tamaño se
  calcula como `floor(riesgo_permitido / (distancia_stop × valor_punto))`;
  si no alcanza para 1 contrato, la operación no se toma.
- **Pérdida máxima diaria**: % del equity al abrir la sesión (default 2%).
- **Máximo de trades por día** (default 5).
- **Racha máxima de pérdidas consecutivas** (default 3).
- **Techo de contratos** y **distancia máxima de stop**.

## Supuestos del simulador de ejecución

Deliberadamente conservadores (sesgan el resultado **en contra**):

- Toda orden a **mercado** (entrada, stop, flatten) paga `slippage_ticks` +
  **medio spread** bid/ask (`spread_ticks / 2`): el precio de la barra es el
  último operado, pero un market order cruza el libro.
- Entradas a mercado en el open de la barra siguiente a la señal.
- Stop = stop-market con costo adverso; si la barra abre gapeada más allá
  del stop, el fill es al open (peor), no al precio del stop.
- Target = orden límite, fill exacto sin slippage ni spread.
- Si stop y target caen en la misma barra → **gana el stop** (no hay datos
  intra-barra para saber el orden real).
- Comisión por lado y por contrato (configurable por símbolo).
- Ninguna posición pasa la noche; ninguna orden pendiente cruza de sesión.

## Seguridad

- `--mode live` exige **doble llave**: `LIVE_TRADING=true` en `.env` **y**
  `live_trading: true` en `config.yaml`. Sin ambas, aborta con error.
- Incluso con ambas llaves, hoy lanza `NotImplementedError`: no existe
  código capaz de enviar órdenes reales (fase 3 sin implementar).
- El flujo obligatorio del proyecto es **backtest → paper trading →
  revisión de resultados → live**, en ese orden.

---

## Decisiones de diseño

| Decisión | Motivo |
|---|---|
| Paquete único `src/nqbot/` | evita colisiones de nombres genéricos e instala con `pip install -e .` |
| Config YAML → dataclasses congeladas | cero números mágicos; config inmutable en runtime |
| Señal al cierre de t, fill al open de t+1 | elimina lookahead de ejecución |
| Swings publicados k barras después | un swing no existe hasta que se confirma (anti-lookahead) |
| VWAP anclado por sesión | es el VWAP que mira un trader intradía de futuros |
| Stop primero si SL y TP caen en la misma barra | sesgo conservador ante ambigüedad intra-barra |
| Estrategia no dimensiona ni ejecuta | separación estricta señal / riesgo / ejecución |
| Equity mark-to-market barra a barra | drawdown real, no solo sobre PnL realizado |
| Bloqueos de riesgo hasta fin de sesión | el peor enemigo del intradía es seguir operando en un mal día |
| Gate de calidad de datos bloqueante | un backtest sobre datos rotos produce confianza falsa |
| La auditoría ve los datos CRUDOS (pre-saneo) | el saneador repara en silencio; la auditoría deja constancia |
| Fecha de sesión de trading ≠ fecha calendario | la sesión Globex del martes abre el lunes 18:00 ET |
| data/raw intocable, backtest solo sobre data/processed | trazabilidad: siempre se puede volver al origen |

## Roadmap

- [x] **Fase 1 — Backtesting**: motor, riesgo, métricas, estrategia base, tests.
- [x] **Fase 1.5a — Infraestructura de datos reales**: pipeline raw→processed,
      auditoría de calidad bloqueante, sesiones Globex, costos con spread.
- [ ] **Fase 1.5b — Investigación**: datos reales de MNQ, walk-forward, estudio
      de sensibilidad de parámetros, mejora de la estrategia base
      (confluencia con PDH/PDL, breakout-retest de swings confirmados).
- [ ] **Fase 2 — Paper trading**: feed en vivo + ejecución simulada en tiempo
      real reutilizando el mismo `ExecutionSimulator`.
- [ ] **Fase 2.5 — Order flow**: delta, footprint, perfil de volumen
      (POC/VAH/VAL) como features de estrategia (requiere datos de mejor
      granularidad que OHLCV).
- [ ] **Fase 3 — Ejecución real**: adaptador de broker detrás de
      `BrokerInterface`, kill switch, reconciliación de posiciones.
      Se habilita solo tras superar las fases anteriores.

## Disclaimer

Software con fines educativos y de investigación. Operar futuros implica
riesgo sustancial de pérdida. Nada de lo que produce este sistema es
recomendación de inversión.
