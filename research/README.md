# research/ — Research Memory del Quant Brain

Memoria estructurada de investigación: **qué se probó, qué funcionó, qué
falló y por qué**. Su función es que el proyecto nunca repita un experimento
inútil ni "redescubra" una idea ya descartada con evidencia.

## Estructura

```
research/
├── research_memory_index.md   # tabla principal: TODA hipótesis pasa por acá
├── hypotheses/                # una ficha por hipótesis (HXXX_*.md)
├── decisions/                 # una ficha por decisión (DXXX_*.md)
├── experiments/               # notas de corridas: qué comando, qué dataset,
│                              #   qué reporte generó (enlaza a reports/)
└── templates/                 # plantillas obligatorias
```

## Reglas de la memoria (no negociables)

1. **Una hipótesis = una variante = un cambio.** Si una idea necesita dos
   cambios, son dos hipótesis.
2. **Toda hipótesis se registra ANTES de mirar resultados.** La ficha se
   crea con mecanismo, datasets y criterios de aceptación/descarte
   completos, y recién después se corre el backtest. Una hipótesis escrita
   después de ver los números no vale como hipótesis.
3. **No se puede validar sobre datos usados para diseñar.** El dataset
   out-of-sample se declara en la ficha al crearla y no se toca. Los
   datasets que originaron una hipótesis quedan marcados como in-sample
   para ella (y para sus derivadas).
4. **No se puede operar sin decisión aprobatoria.** Ninguna estrategia va a
   paper, live ni cuentas de fondeo sin una decisión `APROBADA` registrada
   en `decisions/` que verifique los criterios mínimos de
   `docs/quant_brain_architecture.md` (sección 6).
5. **Las fichas son inmutables en sus conclusiones**: los estados se
   actualizan, las decisiones tomadas no se reescriben. Si algo cambia, se
   agrega una decisión nueva que referencia la anterior.
6. **Lo descartado no se re-testea** sin evidencia nueva que lo justifique
   (y esa justificación se escribe en una ficha nueva que referencia a la
   descartada).

## Estados de una hipótesis

`propuesta → en diseño → testeada → { promovida | en observación | descartada }`

- **propuesta**: idea con mecanismo, sin ficha completa.
- **en diseño**: ficha completa (datasets + criterios pre-registrados), aún
  sin correr.
- **testeada**: corrió in-sample y/o OOS; resultado documentado.
- **en observación**: evidencia mixta; ni se adopta ni se descarta; requiere
  datos nuevos (el caso near_vwap).
- **descartada** / **promovida**: decisión final registrada en `decisions/`.

## Flujo mínimo

1. Copiar `templates/hypothesis_template.md` → `hypotheses/HXXX_nombre.md`.
2. Completar TODO antes de implementar o correr nada.
3. Registrar la fila en `research_memory_index.md`.
4. Implementar (Strategy Lab), correr, documentar resultado en la ficha.
5. **Evaluar con el Decision Engine** (gates ejecutables):
   `python scripts/evaluate_experiment.py --report <carpeta> --oos si|no --overlaps si|no`
   — reglas y umbrales pre-registrados en `decisions/decision_engine_rules.md`;
   la evaluación queda guardada en `experiments/`.
6. Copiar `templates/decision_template.md` → `decisions/DXXX_nombre.md` con
   el veredicto contra los criterios pre-registrados (la decisión humana
   puede ser más estricta que el motor, nunca más laxa).
7. Actualizar estado en el índice.

## Conocimiento validado hasta ahora (resumen vivo)

**Mecanismos que replicaron** (utilizables como building blocks):
- Mediodía 11:00–12:59 en MNQ RTH = pérdida sistemática (2 períodos).
- ATR-20 previo bajo = cinta muerta = no operar (3 períodos, incl. 2024 virgen).

**Descartado con evidencia** (no re-testear sin justificación nueva):
- Sesgo por lado (long/short) como filtro: es régimen, se invirtió entre períodos.
- Horario fino ("solo 10-11h"): inestable (la franja perdió -$2,132 en 2024).
- Distancia al VWAP como filtro estático: régimen-dependiente (flip de signo).

**Hechos estructurales**:
- El edge de la lógica de continuación vive en días tendenciales/expansión;
  el día tendencial NO es anticipable a la entrada con features simples.
- Los trades "nuevos por re-secuenciación" al remover trades de una
  secuencia tendieron a ser malos (3 de 4 casos medidos).
