# Extensión del motor: salidas dinámicas (Quant Brain, Fase 5)

**Fecha:** 2026-07-05
**Archivos:** `src/nqbot/backtesting/models.py` (TradeState, EarlyExitSignal,
EarlyExitReason), `src/nqbot/strategies/base.py` (hook `should_exit_early`),
`src/nqbot/backtesting/engine.py` (paso 3b del loop).
**Tests:** `tests/test_dynamic_exit_engine.py` (7 garantías, suite total 114).

## Qué se extendió

El ciclo de vida de una posición era fijo: stop, target o session_flatten.
Ahora una estrategia puede OPCIONALMENTE evaluar, al cierre de cada barra con
posición abierta, si debe salir antes:

```python
def should_exit_early(self, ts, row, trade_state) -> EarlyExitSignal | None:
    # row: la barra actual PREPARADA (incluye los indicadores de la estrategia)
    # trade_state: snapshot causal del trade (ver abajo)
    if trade_state.minutes_held >= 30 and trade_state.mfe_r < 0.5:
        return EarlyExitSignal(EarlyExitReason.NO_PROGRESS, "sin +0.5R a los 30min")
    return None
```

`TradeState` (inmutable, causal): dirección, contratos, entrada, stop,
target, riesgo inicial, `bars_held`, `minutes_held`, `current_close`,
`current_r` (mark al cierre actual en R), `mfe_r` y `mae_r` (excursiones
máximas acumuladas SOLO con las barras transcurridas).

## Semántica de ejecución (decisiones documentadas)

1. **Orden dentro de la barra**: el hook se evalúa DESPUÉS de stop/target y
   del flatten. Si cualquiera de ellos cierra la posición en esa barra, el
   hook ni siquiera se llama: **jamás pisa stop/target/flatten**.
2. **Fill**: salida a mercado al CIERRE de la barra de decisión, con el
   costo adverso completo (slippage + medio spread) — exactamente la misma
   convención que el session_flatten existente.
3. **Registro**: el Trade resultante lleva `exit_reason="early_exit"`; la
   categoría (`EarlyExitReason`) y el detalle quedan en el log del motor
   junto con el estado del trade al decidir (minutos, MFE, mark).
4. **Causalidad**: el `TradeState` se construye con excursiones acumuladas
   barra a barra; un movimiento futuro no puede aparecer en el MFE/MAE del
   presente. Verificado por test (spike futuro invisible hasta que ocurre).

## Por qué NO altera las estrategias actuales

El hook tiene default `return None` en la clase base: toda estrategia que no
lo implemente se comporta **exactamente** igual que antes. Tres capas de
garantía:

- Test de equivalencia: la misma estrategia con hook-que-devuelve-None
  produce trades y curva de equity **idénticos** a la versión sin hook.
- Los 107 tests previos de la suite — que assertan trades, precios y
  métricas exactas de todas las estrategias existentes — siguen en verde
  sin ninguna modificación.
- Ninguna estrategia del repositorio implementa el hook todavía.

## Cómo habilita H002 (y H003)

La regla congelada de H002 ("salir si el trade no alcanzó +0.5R a los 30
minutos") es una línea sobre `trade_state.minutes_held` y `trade_state.mfe_r`,
y el `current_r` del estado resuelve el faltante que dejó el diagnóstico
(el mark exacto en T). H003 ("expansión fallida") usará además la fila
preparada (`row`), que puede llevar features del Regime Engine.

## Qué falta para que H002 pase de DESIGNED a READY_FOR_TEST

1. **Implementar la variante** (p. ej. `..._dynamic_exit`) con la regla
   congelada de la ficha — decisión aparte, no tomada todavía; será una
   subclase fina que solo implementa el hook.
2. Sus tests conductuales (regla dispara/no dispara donde corresponde).

Para pasar de READY_FOR_TEST a TESTED: correr el protocolo completo contra
el **OOS virgen** declarado en la ficha (jul-2026 en adelante o histórico
2023). El diseño in-sample ya está hecho; no se re-diseña con los mismos datos.
