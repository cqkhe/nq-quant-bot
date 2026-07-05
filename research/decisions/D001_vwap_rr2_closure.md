# D001 — Cierre del ciclo VWAP + Liquidity RR2

| Campo | Valor |
|---|---|
| **ID** | D001 |
| **Fecha** | 2026-07-05 |
| **Hipótesis relacionada** | H001 (`research/hypotheses/H001_vwap_liquidity_rr2.md`) |
| **Experimento relacionado** | `reports/final_vwap_rr2_research_closure.md`, `reports/atr_filter_validation_MNQ_2024_full_*`, `reports/true_oos_2025_01_11_validation.*`, `reports/strategy_variants_comparison.csv` |

## Resultado

Validación final en 2024 virgen (284 sesiones): la mejor variante de la
familia (`atr_filter`) pierde **-$2,948** (PF 0.82, expR -0.12) y la base
`no_midday` pierde **-$4,716** (PF 0.77). En ~30 meses de datos reales la
familia solo fue rentable en un régimen (dic-2025→jun-2026).

## Evidencia a favor (de la familia)

- Dos mecanismos de filtro replicaron con el mismo signo en todos los
  períodos: mediodía tóxico (2 períodos) y ATR bajo = cinta muerta
  (3 períodos, incluido 2024 virgen: eliminados -$1,673).
- `atr_filter` cumplió íntegro su criterio pre-registrado en OOS: expR mayor,
  mecanismo replicado, muestra 258 trades, DD -34%.
- En días tendenciales la lógica es genuinamente buena (+0.45R, PF 1.89).

## Evidencia en contra

- El núcleo de entrada pierde en 2024 (PF 0.77) y 2025 (PF 0.93).
- El único entorno donde gana (día tendencial) no es identificable a la
  entrada con features causales simples — techo estructural de los filtros.
- Pautas de lado y horario resultaron régimen-dependientes (no estructura).

## Decisión final

**CERRADO / NO OPERABLE.**

- `daytrading_vwap_liquidity_rr2` (original): **descartada** como estrategia final.
- `no_midday`: documentada como **mejora parcial** (mecanismo válido).
- `near_vwap`, `longs_only`, `morning_only`, `no_midday_longs_only`: **descartadas**.
- `atr_filter`: **promovida como mejor variante de la familia** — y
  **bloqueada para paper trading, live trading y cuentas de fondeo**.

## Motivo

Reduce daño de forma replicable pero no crea edge: un filtro que convierte
-$4,716 en -$2,948 sigue administrando una expectativa negativa. Los
criterios mínimos para paper (`docs/quant_brain_architecture.md` §6 —
expectancia positiva en OOS, PF ≥ 1.15, robustez entre regímenes) no se
cumplen ni de cerca.

## Próximo paso

Fase 5 del roadmap Quant Brain: investigación de **gestión dinámica de
salida** (time-stop, salida por no-avance a +0.5R en N minutos, no sostener
trades en días sin expansión) — ataca el hallazgo estructural de que el
régimen se revela DESPUÉS de entrar. Como investigación nueva: ficha H
propia, OOS reservado, criterios pre-registrados.

## Bloqueos operativos

- **Regla de cierre: no continuar optimizando filtros de entrada sobre esta
  lógica.** No re-testear variantes descartadas sin evidencia nueva.
- Ninguna estrategia de la familia puede ir a paper/live/fondeo.
- La doble llave de ejecución real permanece cerrada.
- El código de la familia queda en el repo como benchmark y biblioteca.
