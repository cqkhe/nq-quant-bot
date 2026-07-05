# Decision Engine — Reglas y criterios pre-registrados

**Fecha de registro:** 2026-07-05
**Implementación:** `src/nqbot/research/decision_engine.py` (+ `models.py`)
**CLI:** `scripts/evaluate_experiment.py`

Este documento ES el pre-registro de los gates. Cambiar un umbral requiere
una decisión DXXX registrada ANTES de evaluar al próximo candidato — nunca
después de ver un resultado que no gustó.

---

## Estados posibles

| Estado | Significado | Qué sigue |
|---|---|---|
| `PAPER_CANDIDATE` | Cumple TODOS los criterios mínimos | Proponer a paper con decisión DXXX humana. **No es aprobación automática.** |
| `BLOCKED_FOR_PAPER` | Performance de nivel paper, pero sin validación limpia/completa (OOS faltante o negativo, contaminación, dependencia sin verificar) | Conseguir OOS virgen y completar datos; re-evaluar |
| `APPROVED_FOR_RESEARCH` | Señales positivas (expR > 0, PF ≥ 1.0) por debajo del nivel paper | Continuar protocolo: más muestra, OOS, walk-forward |
| `OBSERVATION` | Evidencia mixta o muestra insuficiente (< 30 trades) | Juntar más historia antes de decidir |
| `REJECTED` | Sin edge (expR ≤ 0 o PF < 1.0) con muestra suficiente | Registrar descarte; no re-testear sin evidencia nueva |

## Criterios para PAPER_CANDIDATE (todos obligatorios)

| # | Criterio | Umbral |
|---|---|---|
| 1 | Muestra mínima | ≥ 100 trades |
| 2 | Profit factor | ≥ 1.15 |
| 3 | Expectancia R | > 0 |
| 4 | Drawdown máximo | < 10% del capital (mark-to-market) |
| 5 | Validación out-of-sample | período declarado OOS **y** PnL positivo en él |
| 6 | No dependencia de pocos trades | PnL sin los 5 mejores ganadores sigue > 0 |
| 7 | Sin contaminación | los datos NO se solapan con el período de diseño |

**Regla de datos faltantes:** un criterio NO EVALUABLE (p.ej. dependencia
cuando la fuente es un CSV sin trades, u OOS sin declarar) cuenta como NO
cumplido para la candidatura. Certificar exige datos completos: usar la
carpeta de reporte (`--report`) y declarar `--oos` / `--overlaps`.

## Árbol de decisión

```
1. ¿Cumple los 7 criterios?                        -> PAPER_CANDIDATE
2. ¿Performance nivel paper (1-4) pero falla 5-7?  -> BLOCKED_FOR_PAPER
3. ¿Muestra < 30 trades?                           -> OBSERVATION
4. ¿expR <= 0 o PF < 1.0?                          -> REJECTED
5. ¿expR > 0 y PF >= 1.0?                          -> APPROVED_FOR_RESEARCH
6. Cualquier otro caso                             -> OBSERVATION
```

## Métricas informativas (se muestran, no gatean)

Winrate, racha perdedora máxima, % de meses positivos, PnL neto absoluto.
Se reportan siempre; alimentan la decisión humana, no el gate automático.

## Relación con la arquitectura (§6 del documento maestro)

Los criterios de `docs/quant_brain_architecture.md` §6 incluyen además
walk-forward (≥60% de ventanas positivas) y sensibilidad de parámetros
(±25% sin inversión de signo). **Esos dos se incorporarán al gate cuando
exista el tooling (Fase 5)**; hasta entonces, ningún PAPER_CANDIDATE puede
aprobarse sin verificarlos manualmente en la decisión DXXX.

## Jerarquía de autoridad

1. El Decision Engine produce un estado **recomendado** y verificable.
2. La decisión final SIEMPRE es una ficha DXXX en `research/decisions/`,
   escrita por el investigador, que puede ser más estricta que el motor
   pero nunca más laxa (no se puede aprobar lo que el motor bloquea).
3. La doble llave de ejecución real (`LIVE_TRADING`) es independiente y
   permanece cerrada sin importar los estados de este motor.

## Uso

```bash
# Fuente completa (carpeta de reporte): evalúa los 7 criterios
python scripts/evaluate_experiment.py --report reports/<carpeta> --oos si --overlaps no

# Fuente parcial (CSV de validador): criterios sin datos = no evaluables
python scripts/evaluate_experiment.py --csv reports/<archivo>.csv --strategy <nombre> --oos si --overlaps no
```

Cada evaluación se guarda en `research/experiments/EVAL_*.md` (histórico).
