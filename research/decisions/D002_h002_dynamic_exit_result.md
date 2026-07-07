# D002 — Resultado de H002 (salida dinámica por falta de progreso)

| Campo | Valor |
|---|---|
| **ID** | D002 |
| **Fecha** | 2026-07-05 |
| **Hipótesis relacionada** | H002 (`research/hypotheses/H002_dynamic_exit_no_progress.md`) |
| **Experimento relacionado** | `reports/h002_dynamic_exit_comparison.csv` · `reports/h002_dynamic_exit_summary.md` |

## Resultado

Variante `..._dynamic_exit_h002` (regla congelada: early_exit si ≥30 min y
MFE < +0.5R) vs base `atr_filter`, en los tres datasets de DISEÑO:

| Dataset | ΔPnL | ΔexpR | ΔDD | Beneficio directo regla | Re-secuenciación | ¿Mataría targets? |
|---|---|---|---|---|---|---|
| 2024 | -$180 | +0.005 | +$291 (peor) | **+$185** | -$755 | 17.2% (<20% ✓) |
| 2025 ene-nov | -$6 | +0.005 | -$171 (mejor) | **+$290** | -$418 | 15.8% ✓ |
| 2025-2026 completo | -$22 | -0.001 | -$171 (mejor) | **+$493** | -$636 | 11.1% ✓ |

## Evidencia a favor

- **El mecanismo de H002 es real y replicó en los tres períodos**: los
  trades cortados eran mayoritariamente stop-bound (69-79% en el
  contrafactual exacto), la regla ahorró dinero en los trades que tocó
  (+$185/+$290/+$493) y no mató ganadores (11-17% de targets, bajo el
  límite pre-registrado del 20%).
- Early exits salen en promedio a -0.23/-0.34R en vez de dejar correr hacia
  -1R: exactamente el comportamiento hipotetizado.

## Evidencia en contra

- **El beneficio neto es ~cero** (ΔPnL -$180/-$6/-$22; expR ±0.005): el
  slot que la regla libera toma trades nuevos que pierden
  (-$755/-$418/-$636). Es la CUARTA observación independiente del patrón
  "trades por re-secuenciación son tóxicos" (antes: near_vwap ×2, no_midday
  OOS). El efecto colateral cancela el mecanismo.
- En 2024 el drawdown empeora (+$291) y el PnL neto también.

## Decisión final

**OBSERVATION.**

No es REJECTED: el mecanismo replicó al pie de su pre-registro y la regla no
daña (neto ~0, sin matar ganadores). No es PROMOTED: no produce mejora neta.

## Motivo

La hipótesis era "reducir pérdidas sin destruir ganadores": la mitad
"sin destruir ganadores" se cumplió; la mitad "reducir pérdidas" se cumple
solo en los trades tocados y la cancela un efecto separable (la re-entrada
posterior). El resultado no refuta el mecanismo — refina dónde está el
problema.

## Próximo paso

1. Hipótesis derivada candidata para el backlog (**no implementada**):
   *tras un early_exit, bloquear la re-entrada por el resto de la sesión o
   por N minutos* — atacaría directamente el patrón de re-secuenciación,
   que ya tiene 4 observaciones independientes. Requiere ficha nueva (H005)
   con su propio pre-registro.
2. H002 queda en OBSERVATION hasta el OOS virgen (jul-2026+ o 2023): si el
   mecanismo replica también ahí, la combinación con la hipótesis de
   re-entrada se vuelve la línea principal.

## Bloqueos operativos

- **Decision Engine** sobre la variante: 2024 REJECTED · 2025
  APPROVED_FOR_RESEARCH · completo **BLOCKED_FOR_PAPER** (números de nivel
  paper, validación no limpia). En los tres casos:
  **NO apta para paper trading, live ni cuentas de fondeo** — sin OOS
  virgen y con datos de diseño contaminados por construcción.
- La regla congelada no se modifica ni se re-parametriza sin nueva ficha.
- La doble llave de ejecución real permanece cerrada.
