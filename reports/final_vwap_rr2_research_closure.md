# Cierre del ciclo de investigación: VWAP + Liquidity RR2

**Fecha de cierre:** 2026-07-05
**Estado:** CERRADO — sin aprobación operativa
**Documentos relacionados:** `docs/strategy_decision_log.md` (decisiones),
`reports/atr_filter_validation_MNQ_2024_full_*` (validación final)

---

## 1. Objetivo inicial

Construir y validar una estrategia de day trading para futuros del Nasdaq
(MNQ/NQ) en sesión regular (09:30–16:00 ET), con RR fijo 2:1, basada en
price action, VWAP, EMAs, liquidez, volumen y estructura intradía — sin
conceptos ICT, sin curve fitting, y con validación estadística estricta:
todo cambio nace como hipótesis con mecanismo explicable, se mide contra un
criterio pre-registrado y se acepta o descarta con datos que no participaron
de su diseño.

## 2. Datos usados

Exports reales de NinjaTrader (MNQ, 1 minuto, UTC → ET), importados por el
pipeline `data/raw` → auditoría de calidad → `data/processed`. Total: ~30
meses de mercado real.

| Dataset | Rol |
|---|---|
| dic-2025 → jun-2026 (113 sesiones) | Período de diseño original (estrategia + filtro no_midday) |
| ene-2025 → nov-2025 (271 sesiones) | Out-of-sample de no_midday; luego fuente de los diagnósticos de edge y régimen |
| ene-2025 → jun-2026 (18 meses) | Dataset combinado de contraste |
| **año 2024 completo (284 sesiones)** | **Out-of-sample final: ninguna hipótesis lo vio** |

## 3. Estrategias testeadas

| Estrategia | Descripción | Destino |
|---|---|---|
| `daytrading_vwap_liquidity_rr2` | Núcleo: pullback a valor (VWAP/EMA25) con tendencia, rechazo, volumen, stop técnico intradía, TP = 2R | **Descartada** |
| `_no_midday` | + sin entradas 11:00–12:59 | Mejora parcial documentada |
| `_longs_only` | + solo longs | Descartada (el sesgo por lado se invirtió entre períodos) |
| `_morning_only` | + solo entradas 10:00–10:59 | Descartada (la franja "buena" perdió -$2,132 en 2024) |
| `_no_midday_longs_only` | combinación | Descartada (hereda el problema de longs_only) |
| `_no_midday_near_vwap` | + entrada a ≤30 pts del VWAP | Descartada (efecto régimen-dependiente: los trades eliminados fueron malos en 2025 pero buenos en dic-25→jun-26) |
| `_no_midday_atr_filter` | + no operar con ATR-20 previo < 8 pts | **Promovida: mejor variante de la familia** |

## 4. Resultado in-sample (dic-2025 → jun-2026, período de diseño)

| Métrica | Original | no_midday |
|---|---|---|
| Trades | 89 | 59 |
| PnL neto | +$1,452 | +$2,271 |
| Profit factor | 1.31 | 1.83 |
| Expectancia | +0.15 R | +0.38 R |
| Drawdown | $1,184 (4.7%) | $589 |
| Racha perdedora | 10 | 4 |

Prometedor en apariencia — y la razón por la que existe la validación
out-of-sample.

## 5. Resultado out-of-sample 2024 (veredicto final)

Dataset: `data/processed/MNQ_2024_full_1m_ninjatrader_combined_clean.csv`
(2024-01-02 09:30 → 2024-12-31 15:59, 284 sesiones).

| Métrica | no_midday | atr_filter |
|---|---|---|
| Trades | 332 | 258 |
| PnL neto | **-$4,716.30** | **-$2,948.06** |
| Profit factor | 0.765 | 0.818 |
| Winrate | 31.33% | 31.78% |
| Expectancia | -0.149 R | -0.120 R |
| Drawdown | $5,359.78 | $3,553.20 (-34%) |
| Racha perdedora | 10 | 12 |

El filtro ATR eliminó 102 trades de ATR bajo que tenían PnL **-$1,672.98**
(expR -0.19) y mejoró en 7 de 12 meses. Cumplió los tres puntos de su
criterio pre-registrado. Y aun así: **la mejor versión de la familia pierde
casi $3,000 en el año que no vio.** Contexto completo por período: 2024
pierde (PF 0.77 base), 2025 pierde (PF 0.93), solo dic-25→jun-26 ganó.

## 6. Qué filtros SÍ replicaron (conocimiento ganado)

Dos mecanismos demostraron ser reales, con el mismo signo en todos los
períodos testeados:

1. **Mediodía (11:00–12:59) = pérdida sistemática.** Los trades de esa
   franja fueron netos negativos en el período de diseño Y en 2025.
2. **ATR-20 previo bajo = cinta muerta = no operar.** Los trades eliminados
   por el filtro fueron netos negativos en tres períodos consecutivos:
   2025 (-$1,065), 18 meses (-$595) y 2024 virgen (-$1,673).

Y dos anti-hallazgos igual de valiosos:

3. Los sesgos de **lado** (long/short) y de **horario fino** son propiedades
   del régimen, no de la estrategia: se invirtieron entre períodos.
4. La **distancia al VWAP** es régimen-dependiente: tóxica en mercado
   lateral, rentable en tendencia fuerte. No sirve como filtro estático.

## 7. Por qué la estrategia NO es operable

- El núcleo de entrada solo tuvo expectancia positiva en un régimen
  (dic-25→jun-26). En ~30 meses agregados, pierde.
- El diagnóstico de régimen mostró que el edge vive en días tendenciales /
  de expansión (+0.45R, PF 1.89) y muere en laterales (-0.2R) — pero el día
  tendencial **se conoce al cierre, no a la entrada**: los proxies causales
  de expansión resultaron inconsistentes o invertidos entre datasets.
- Por lo tanto, los filtros de entrada tienen techo estructural: pueden
  recortar el daño (lo hicieron), no pueden crear el edge que el núcleo no
  tiene.

## 8. Decisión final

- `daytrading_vwap_liquidity_rr2` (original): **descartada** como estrategia final.
- `no_midday`: documentada como **mejora parcial** (su mecanismo replicó).
- `atr_filter`: **promovida como la mejor variante de esta familia**.
- **`atr_filter` NO queda aprobada para paper trading, live trading ni
  cuentas de fondeo.** Reduce daño de forma replicable, pero el núcleo de
  entrada sigue sin edge estable.

> **REGLA DE CIERRE: no continuar optimizando filtros de entrada sobre esta
> lógica.**

El código de toda la familia queda en el repositorio como referencia y
benchmark para futuras líneas — no se elimina, no se toca.

## 9. Próxima fase recomendada (investigación NUEVA)

El hallazgo central — el edge existe pero se revela *después* de entrar —
apunta a atacar el problema donde vive. Candidatas, en orden sugerido:

1. **Gestión dinámica dentro del trade**: hoy cada posición sobrevive hasta
   stop, target o flatten; el 2R fijo obliga a financiar la espera completa
   en días muertos.
2. **Salida temprana si el trade no expande**: tiempo máximo en trade, o
   abandono si el rango del día no se desarrolla tras la entrada (las
   señales de no-expansión sí son causales *después* de entrar).
3. **No sostener trades en días que no desarrollan rango**: la versión
   defensiva de lo anterior.
4. **Rediseño completo de la lógica de entrada** si lo anterior no alcanza.

Requisitos de protocolo para esa fase (los mismos que hicieron funcionar
esta): período de diseño y out-of-sample separados ANTES de mirar nada
(queda 2024-H2/2023 si se consigue, o jul-2026 en adelante), criterios de
promoción pre-registrados en `docs/strategy_decision_log.md`, una sola
hipótesis por variante con mecanismo explicable, y umbral redondo lejos del
óptimo in-sample.

---

*Este ciclo no produjo una estrategia operable. Produjo algo que vale más a
largo plazo: una plataforma de investigación honesta que descarta ideas con
evidencia en backtest — donde descartar es barato — en lugar de descubrirlo
con dinero real.*
