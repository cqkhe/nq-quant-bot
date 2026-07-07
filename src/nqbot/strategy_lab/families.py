"""Familias predefinidas del Strategy Lab."""

from __future__ import annotations

from .models import ParameterGrid, StrategyFamily


def _scaffold(
    name: str,
    *,
    description: str,
    hypothesis: str,
    works_when: str,
    fails_when: str,
    main_params: tuple[str, ...],
    parameter_grid: ParameterGrid | None = None,
) -> StrategyFamily:
    return StrategyFamily(
        name=name,
        base_strategy=f"scaffold::{name}",
        description=description,
        parameter_grid=parameter_grid or ParameterGrid({"prototype": ["baseline"]}),
        implemented=False,
        hypothesis=hypothesis,
        works_when=works_when,
        fails_when=fails_when,
        overfitting_risk="alto hasta tener estrategia y tests propios",
        main_params=main_params,
    )


def _implemented_volume(
    name: str,
    *,
    description: str,
    hypothesis: str,
    works_when: str,
    fails_when: str,
    main_params: tuple[str, ...],
    parameter_grid: ParameterGrid,
) -> StrategyFamily:
    return StrategyFamily(
        name=name,
        base_strategy=name,
        description=description,
        parameter_grid=parameter_grid,
        implemented=True,
        hypothesis=hypothesis,
        works_when=works_when,
        fails_when=fails_when,
        overfitting_risk="alto: primera implementacion OHLCV-only, requiere OOS",
        main_params=main_params,
    )


_FAMILIES: dict[str, StrategyFamily] = {
    "rr2_atr_filter": StrategyFamily(
        name="rr2_atr_filter",
        base_strategy="daytrading_vwap_liquidity_rr2_no_midday_atr_filter",
        description=(
            "Busqueda limitada sobre parametros existentes de la familia "
            "VWAP liquidity RR2 no_midday atr_filter."
        ),
        parameter_grid=ParameterGrid({
            "min_atr20_points": [6.0, 8.0, 10.0],
            "rel_volume_threshold": [1.05, 1.10],
            "max_vwap_distance_points": [40.0, 60.0],
            "min_slope_points": [1.5, 2.0],
        }),
        fixed_params={"blocked_entry_windows": [["11:00", "13:00"]]},
        hypothesis="Pullback a valor con filtro de volatilidad minima.",
        works_when="sesiones RTH con volatilidad suficiente y tendencia limpia",
        fails_when="cinta muerta, chop de mediodia o breaks sin continuidad",
        overfitting_risk="medio: familia ya marco fragilidad en Fase 8",
        main_params=(
            "min_atr20_points",
            "rel_volume_threshold",
            "max_vwap_distance_points",
            "min_slope_points",
        ),
    ),
    "base_vwap_ema": StrategyFamily(
        name="base_vwap_ema",
        base_strategy="base_vwap_ema",
        description="Busqueda pequena y conservadora sobre la estrategia base.",
        parameter_grid=ParameterGrid({
            "rel_volume_threshold": [1.00, 1.05, 1.10],
            "pullback_lookback": [8, 10],
            "rr": [1.5, 2.0],
        }),
        hypothesis="Pullback a valor alineado con EMAs y volumen relativo.",
        works_when="tendencias intradia ordenadas con pullbacks poco profundos",
        fails_when="rangos estrechos o cambios violentos de regimen",
        main_params=("rel_volume_threshold", "pullback_lookback", "rr"),
    ),
    "vwap_mean_reversion": StrategyFamily(
        name="vwap_mean_reversion",
        base_strategy="daytrading_vwap_liquidity_rr2_no_midday_near_vwap",
        description="Reversion a VWAP usando variante near_vwap existente.",
        parameter_grid=ParameterGrid({
            "max_vwap_distance_points_near": [20.0, 30.0],
            "rel_volume_threshold": [1.00, 1.10],
            "rejection_close_pct": [0.55, 0.60],
        }),
        fixed_params={"blocked_entry_windows": [["11:00", "13:00"]]},
        hypothesis="Entradas cerca de VWAP deberian reducir persecucion de precio.",
        works_when="mercado rota alrededor de valor con rechazo claro",
        fails_when="dias de tendencia persistente donde VWAP no actua como iman",
        main_params=(
            "max_vwap_distance_points_near",
            "rel_volume_threshold",
            "rejection_close_pct",
        ),
    ),
    "trend_pullback_ema": StrategyFamily(
        name="trend_pullback_ema",
        base_strategy="base_vwap_ema",
        description="Pullback de tendencia con EMAs existentes.",
        parameter_grid=ParameterGrid({
            "ema_fast": [13],
            "ema_mid": [25],
            "ema_slow": [55],
            "pullback_lookback": [8, 12],
            "rr": [1.5, 2.0],
        }),
        hypothesis="La continuidad despues de pullback mejora si las EMAs estan ordenadas.",
        works_when="tendencias limpias con retrocesos a medias",
        fails_when="rangos laterales y reversiones bruscas",
        main_params=("pullback_lookback", "rr"),
    ),
    "pullback_to_vwap_trend": StrategyFamily(
        name="pullback_to_vwap_trend",
        base_strategy="daytrading_vwap_liquidity_rr2",
        description="Pullback a VWAP en tendencia usando la estrategia RR2 base.",
        parameter_grid=ParameterGrid({
            "max_vwap_distance_points": [30.0, 45.0],
            "min_slope_points": [1.5, 2.0],
            "rel_volume_threshold": [1.05, 1.10],
        }),
        hypothesis="Un pullback a valor con pendiente positiva/negativa deberia continuar.",
        works_when="tendencias con pullbacks ordenados a VWAP",
        fails_when="VWAP plana, rangos y falsa continuacion",
        main_params=("max_vwap_distance_points", "min_slope_points", "rel_volume_threshold"),
    ),
    "ema_trend_continuation": StrategyFamily(
        name="ema_trend_continuation",
        base_strategy="base_vwap_ema",
        description="Continuacion de tendencia por estructura EMA existente.",
        parameter_grid=ParameterGrid({
            "ema_fast": [13],
            "ema_mid": [21, 25],
            "ema_slow": [55],
            "rel_volume_threshold": [1.00, 1.05],
        }),
        hypothesis="La alineacion de EMAs deberia filtrar operaciones contra tendencia.",
        works_when="sesiones direccionales con volumen estable",
        fails_when="mean reversion fuerte o EMAs cruzandose constantemente",
        main_params=("ema_mid", "rel_volume_threshold"),
    ),
    "opening_range_breakout": _scaffold(
        "opening_range_breakout",
        description="Breakout del rango inicial; pendiente de estrategia real.",
        hypothesis="La ruptura del rango inicial captura expansion temprana.",
        works_when="open con compresion inicial y expansion direccional",
        fails_when="falsos breaks y rotacion dentro del rango inicial",
        main_params=("opening_range_minutes", "breakout_buffer_ticks", "min_volume_ratio"),
    ),
    "opening_range_reversal": _scaffold(
        "opening_range_reversal",
        description="Reversion contra ruptura fallida del rango inicial.",
        hypothesis="Un breakout fallido del rango inicial tiende a volver a valor.",
        works_when="open emocional que falla y revierte al VWAP",
        fails_when="dias de trend desde apertura",
        main_params=("opening_range_minutes", "failure_minutes", "reclaim_buffer_ticks"),
    ),
    "volatility_expansion_breakout": _scaffold(
        "volatility_expansion_breakout",
        description="Breakout tras expansion de volatilidad; pendiente de estrategia real.",
        hypothesis="La expansion de rango con volumen confirma desplazamiento.",
        works_when="volatilidad comprimida seguida de vela expansiva",
        fails_when="spikes aislados sin follow-through",
        main_params=("atr_window", "atr_expansion_ratio", "volume_ratio"),
    ),
    "regime_aware_rr2": _scaffold(
        "regime_aware_rr2",
        description="RR2 condicionado por Market Regime Engine.",
        hypothesis="La familia RR2 solo deberia operar en regimenes favorables.",
        works_when="regimen de tendencia/volatilidad confirmado",
        fails_when="regimen lateral o transicion no clasificada",
        main_params=("allowed_regimes", "min_regime_confidence"),
    ),
    "vwap_reclaim": _scaffold(
        "vwap_reclaim",
        description="Reclaim de VWAP tras perdida temporal; pendiente de estrategia real.",
        hypothesis="Recuperar VWAP con volumen puede marcar cambio de control.",
        works_when="falso breakdown/breakout alrededor de VWAP",
        fails_when="VWAP deja de actuar como referencia",
        main_params=("reclaim_window", "volume_ratio", "max_distance_after_reclaim"),
    ),
    "previous_day_high_low_breakout": _scaffold(
        "previous_day_high_low_breakout",
        description="Breakout de high/low del dia previo.",
        hypothesis="Niveles del dia previo concentran liquidez y continuacion.",
        works_when="ruptura limpia con aceptacion fuera del nivel",
        fails_when="barridas de liquidez que revierten rapido",
        main_params=("level_buffer_ticks", "confirmation_bars", "volume_ratio"),
    ),
    "previous_day_high_low_reversal": _scaffold(
        "previous_day_high_low_reversal",
        description="Reversion tras rechazo de high/low del dia previo.",
        hypothesis="Barridas del dia previo pueden revertir al rango.",
        works_when="stop run y rechazo fuerte del nivel",
        fails_when="breakout con aceptacion real fuera del nivel",
        main_params=("rejection_window", "level_buffer_ticks", "target_to_vwap"),
    ),
    "range_expansion_continuation": _scaffold(
        "range_expansion_continuation",
        description="Continuacion despues de expansion de rango intradia.",
        hypothesis="Una expansion amplia con cierre fuerte tiende a continuar.",
        works_when="velas de expansion con participacion creciente",
        fails_when="climax bars y agotamiento",
        main_params=("range_window", "expansion_ratio", "close_strength"),
    ),
    "failed_breakout_reversal": _scaffold(
        "failed_breakout_reversal",
        description="Reversion de breakout fallido.",
        hypothesis="La falta de follow-through despues de romper un nivel crea reversals.",
        works_when="ruptura, rechazo y retorno dentro del rango",
        fails_when="breakouts reales con aceptacion",
        main_params=("failure_bars", "level_buffer_ticks", "reversal_confirmation"),
    ),
    "high_volume_reversal": _scaffold(
        "high_volume_reversal",
        description="Reversion con volumen extremo.",
        hypothesis="Volumen climatico cerca de extremos puede indicar absorcion.",
        works_when="spikes de volumen con rechazo de precio",
        fails_when="volumen alto de continuacion institucional",
        main_params=("volume_zscore", "wick_ratio", "location_filter"),
    ),
    "low_volatility_breakout": _scaffold(
        "low_volatility_breakout",
        description="Breakout desde baja volatilidad.",
        hypothesis="Compresion de volatilidad precede expansion direccional.",
        works_when="ATR bajo y rango estrecho antes del impulso",
        fails_when="baja volatilidad persistente sin expansion",
        main_params=("compression_window", "atr_percentile", "breakout_buffer_ticks"),
    ),
    "session_momentum_breakout": _scaffold(
        "session_momentum_breakout",
        description="Breakout por momentum de sesion.",
        hypothesis="Momentum temprano de sesion puede extenderse si hay volumen.",
        works_when="sesiones direccionales con impulso inicial",
        fails_when="aperturas con reversals rapidos",
        main_params=("momentum_window", "min_session_return", "volume_ratio"),
    ),
}

_VOLUME_FAMILIES: dict[str, StrategyFamily] = {
    "relative_volume_breakout": _implemented_volume(
        "relative_volume_breakout",
        description=(
            "Breakout contra rango previo confirmado por volumen relativo OHLCV."
        ),
        hypothesis="Una ruptura con participacion superior al promedio tiene mas continuidad.",
        works_when="rangos definidos, apertura comprimida y expansion con volumen creciente",
        fails_when="spikes aislados, news whipsaw o rupturas sin aceptacion",
        main_params=("rel_volume_threshold", "volume_window", "breakout_lookback"),
        parameter_grid=ParameterGrid({
            "rel_volume_threshold": [1.2, 1.5],
            "volume_window": [20, 50],
            "breakout_lookback": [20, 30],
            "rr": [1.5, 2.0],
        }),
    ),
    "volume_climax_reversal": _implemented_volume(
        "volume_climax_reversal",
        description="Reversion tras volumen climatico OHLCV y rechazo de precio.",
        hypothesis="Un pico de volumen con rechazo cerca de extremos puede indicar agotamiento.",
        works_when="spike de volumen, mecha/rechazo y cierre contrario al impulso previo",
        fails_when="volumen alto de continuacion o breakouts con aceptacion real",
        main_params=("spike_threshold", "volume_window", "rejection_close_pct"),
        parameter_grid=ParameterGrid({
            "spike_threshold": [1.5, 2.0],
            "volume_window": [20, 50],
            "rejection_close_pct": [0.55, 0.65],
            "rr": [1.5],
        }),
    ),
    "volume_dry_up_breakout": _implemented_volume(
        "volume_dry_up_breakout",
        description="Ruptura tras compresion con volumen seco.",
        hypothesis="La contraccion de participacion puede preceder una expansion direccional.",
        works_when="dry-up claro, rango estrecho y ruptura con volumen creciente",
        fails_when="baja liquidez persistente o falsas expansiones sin follow-through",
        main_params=("dry_up_threshold", "rel_volume_threshold", "volume_window"),
        parameter_grid=ParameterGrid({
            "dry_up_threshold": [0.6, 0.8],
            "rel_volume_threshold": [1.2, 1.5],
            "volume_window": [20, 50],
            "breakout_lookback": [20],
        }),
    ),
    "volume_expansion_continuation": _scaffold(
        "volume_expansion_continuation",
        description="Continuacion por expansion de rango con volumen creciente.",
        hypothesis="Rango amplio mas volumen relativo alto puede confirmar desplazamiento.",
        works_when="vela de expansion con cierre fuerte y participacion creciente",
        fails_when="climax de agotamiento o extension lejos de valor",
        main_params=("rel_volume_threshold", "min_atr20_points", "rr"),
        parameter_grid=ParameterGrid({
            "rel_volume_threshold": [1.2, 1.5],
            "min_atr20_points": [8.0, 12.0],
            "rr": [1.5, 2.0],
        }),
    ),
    "high_volume_failed_breakout": _scaffold(
        "high_volume_failed_breakout",
        description="Breakout fallido con alto volumen OHLCV.",
        hypothesis="Una ruptura con volumen que no sostiene aceptacion puede revertir al rango.",
        works_when="barrida de nivel, retorno al rango y rechazo confirmado",
        fails_when="rupturas con aceptacion y continuacion institucional",
        main_params=("rel_volume_threshold", "failure_bars", "rejection_close_pct"),
        parameter_grid=ParameterGrid({
            "rel_volume_threshold": [1.5, 2.0],
            "failure_bars": [2, 3],
            "rejection_close_pct": [0.55, 0.65],
        }),
    ),
    "low_volume_pullback_continuation": _scaffold(
        "low_volume_pullback_continuation",
        description="Continuacion de tendencia tras pullback con volumen bajo.",
        hypothesis="Retrocesos con baja participacion pueden ser pausas dentro de tendencia.",
        works_when="tendencia limpia, pullback ordenado y reanudacion con volumen normal/alto",
        fails_when="pullbacks que se convierten en reversion o tendencia agotada",
        main_params=("dry_up_threshold", "pullback_lookback", "rr"),
        parameter_grid=ParameterGrid({
            "dry_up_threshold": [0.6, 0.8],
            "pullback_lookback": [8, 12],
            "rr": [1.5, 2.0],
        }),
    ),
    "vwap_volume_reclaim": _implemented_volume(
        "vwap_volume_reclaim",
        description="Reclaim de VWAP confirmado por volumen relativo.",
        hypothesis="Recuperar VWAP con volumen puede marcar cambio de control intradia.",
        works_when="falso quiebre alrededor de VWAP y participacion creciente en reclaim",
        fails_when="VWAP plana sin aceptacion o rangos estrechos",
        main_params=("rel_volume_threshold", "max_vwap_distance_points", "volume_window"),
        parameter_grid=ParameterGrid({
            "rel_volume_threshold": [1.2, 1.5],
            "max_vwap_distance_points": [40.0, 60.0],
            "volume_window": [20, 50],
            "rr": [1.5],
        }),
    ),
    "opening_range_volume_breakout": _implemented_volume(
        "opening_range_volume_breakout",
        description="Opening range breakout con confirmacion de volumen OHLCV.",
        hypothesis="La ruptura del rango inicial requiere participacion superior al promedio.",
        works_when="open con rango definido y expansion con volumen relativo alto",
        fails_when="aperturas erraticas o stop runs sin aceptacion",
        main_params=("opening_range_minutes", "rel_volume_threshold", "volume_window"),
        parameter_grid=ParameterGrid({
            "opening_range_minutes": [15, 30],
            "rel_volume_threshold": [1.2, 1.5],
            "volume_window": [20, 50],
            "rr": [1.5, 2.0],
        }),
    ),
    "volume_spike_mean_reversion": _scaffold(
        "volume_spike_mean_reversion",
        description="Mean reversion tras spike de volumen lejos de VWAP.",
        hypothesis="Spikes de volumen extendidos pueden indicar agotamiento de corto plazo.",
        works_when="extension lejos de VWAP, spike de volumen y rechazo claro",
        fails_when="spikes que inician tendencia o news con continuidad",
        main_params=("spike_threshold", "max_vwap_distance_points", "rejection_close_pct"),
        parameter_grid=ParameterGrid({
            "spike_threshold": [1.5, 2.0],
            "max_vwap_distance_points": [40.0, 60.0],
            "rejection_close_pct": [0.55, 0.65],
        }),
    ),
    "volume_trend_confirmation": _scaffold(
        "volume_trend_confirmation",
        description="Filtro de tendencia que exige confirmacion por volumen OHLCV.",
        hypothesis="La tendencia deberia tener participacion suficiente para continuar.",
        works_when="EMAs/VWAP alineadas y volumen normal-alto en desplazamientos",
        fails_when="tendencias agotadas o avances con participacion decreciente",
        main_params=("rel_volume_threshold", "volume_window", "rr"),
        parameter_grid=ParameterGrid({
            "rel_volume_threshold": [1.2, 1.5],
            "volume_window": [20, 50],
            "rr": [1.5, 2.0],
        }),
    ),
}

_GAUSSIAN_VOLUME_FAMILIES: dict[str, StrategyFamily] = {
    "gaussian_volume_breakout": _implemented_volume(
        "gaussian_volume_breakout",
        description="Breakout confirmado por z-score de volumen; no es order flow real.",
        hypothesis="Una ruptura con volumen estadisticamente alto tiene mejor aceptacion.",
        works_when="rango definido y volume_zscore alto sin extension excesiva",
        fails_when="spikes aislados o rupturas con volumen climatico de agotamiento",
        main_params=("volume_window", "volume_zscore_threshold", "breakout_lookback"),
        parameter_grid=ParameterGrid({
            "volume_window": [20, 50],
            "volume_zscore_threshold": [1.5, 2.0],
            "breakout_lookback": [20, 30],
            "rr": [1.5, 2.0],
        }),
    ),
    "gaussian_volume_reversal": _implemented_volume(
        "gaussian_volume_reversal",
        description="Reversion con volumen estadisticamente extremo y rechazo.",
        hypothesis="Volumen muy lejos de su media movil puede marcar agotamiento.",
        works_when="z-score alto, rechazo de precio y cierre contrario al impulso",
        fails_when="continuacion fuerte con volumen persistentemente alto",
        main_params=("volume_window", "volume_zscore_threshold", "rejection_close_pct"),
        parameter_grid=ParameterGrid({
            "volume_window": [20, 50],
            "volume_zscore_threshold": [2.0, 2.5],
            "rejection_close_pct": [0.55, 0.65],
            "rr": [1.5],
        }),
    ),
    "gaussian_volume_climax": _scaffold(
        "gaussian_volume_climax",
        description="Deteccion de posible climax mediante z-score de volumen.",
        hypothesis="z-score de volumen extremo puede senalar absorcion o agotamiento.",
        works_when="z-score > 2.0/2.5 cerca de extremos con rechazo de precio",
        fails_when="dias de tendencia donde volumen extremo confirma continuacion",
        main_params=("volume_window", "volume_zscore_threshold", "rejection_close_pct"),
        parameter_grid=ParameterGrid({
            "volume_window": [20, 50],
            "volume_zscore_threshold": [2.0, 2.5],
            "rejection_close_pct": [0.55, 0.65],
        }),
    ),
    "gaussian_volume_dry_up_breakout": _implemented_volume(
        "gaussian_volume_dry_up_breakout",
        description="Breakout tras dry-up estadistico de volumen.",
        hypothesis="Volumen bajo relativo a su distribucion puede preceder expansion.",
        works_when="z-score bajo previo, compresion y ruptura con volumen normal-alto",
        fails_when="mercado iliquido o compresion sin expansion posterior",
        main_params=("volume_window", "dry_up_zscore_threshold", "volume_zscore_threshold"),
        parameter_grid=ParameterGrid({
            "volume_window": [20, 50],
            "dry_up_zscore_threshold": [-0.5, -1.0],
            "volume_zscore_threshold": [1.5, 2.0],
            "breakout_lookback": [20],
        }),
    ),
    "gaussian_volume_trend_confirmation": _scaffold(
        "gaussian_volume_trend_confirmation",
        description="Confirmacion de tendencia con volumen normalizado por z-score.",
        hypothesis="La continuidad mejora cuando la participacion supera su media reciente.",
        works_when="tendencia alineada y volume_zscore positivo en impulsos",
        fails_when="tendencia agotada o volumen extremo de climax",
        main_params=("volume_window", "volume_zscore_threshold", "rr"),
        parameter_grid=ParameterGrid({
            "volume_window": [20, 50],
            "volume_zscore_threshold": [1.0, 1.5],
            "rr": [1.5, 2.0],
        }),
    ),
    "gaussian_volume_failed_breakout": _scaffold(
        "gaussian_volume_failed_breakout",
        description="Breakout fallido con volumen estadisticamente alto.",
        hypothesis="Un z-score extremo que no sostiene precio puede revertir al rango.",
        works_when="ruptura con z-score alto, fallo rapido y retorno al rango",
        fails_when="breakout con aceptacion fuera del nivel",
        main_params=("volume_window", "volume_zscore_threshold", "failure_bars"),
        parameter_grid=ParameterGrid({
            "volume_window": [20, 50],
            "volume_zscore_threshold": [2.0, 2.5],
            "failure_bars": [2, 3],
        }),
    ),
    "gaussian_volume_mean_reversion": _scaffold(
        "gaussian_volume_mean_reversion",
        description="Mean reversion con z-score alto lejos de VWAP.",
        hypothesis="Volumen extremo lejos de valor puede indicar exhaustacion del movimiento.",
        works_when="extension a distancia de VWAP, z-score alto y rechazo",
        fails_when="tendencias fuertes que aceptan nuevos niveles",
        main_params=("volume_window", "volume_zscore_threshold", "max_vwap_distance_points"),
        parameter_grid=ParameterGrid({
            "volume_window": [20, 50],
            "volume_zscore_threshold": [2.0, 2.5],
            "max_vwap_distance_points": [40.0, 60.0],
        }),
    ),
    "gaussian_volume_expansion_continuation": _scaffold(
        "gaussian_volume_expansion_continuation",
        description="Continuacion por expansion de rango con volume_zscore alto.",
        hypothesis="Expansion de rango mas volumen estadisticamente alto puede continuar.",
        works_when="vela expansiva, cierre fuerte y z-score alto no climatico",
        fails_when="barra de climax o extension final del movimiento",
        main_params=("volume_window", "volume_zscore_threshold", "rr"),
        parameter_grid=ParameterGrid({
            "volume_window": [20, 50],
            "volume_zscore_threshold": [1.5, 2.0],
            "rr": [1.5, 2.0],
        }),
    ),
}

_FAMILIES.update(_VOLUME_FAMILIES)
_FAMILIES.update(_GAUSSIAN_VOLUME_FAMILIES)

_ALIASES = {
    "daytrading_vwap_liquidity_rr2_no_midday_atr_filter": "rr2_atr_filter",
}


def available_families(*, include_scaffolds: bool = True) -> list[str]:
    names = _FAMILIES
    if include_scaffolds:
        return sorted(names)
    return sorted(name for name, family in names.items() if family.implemented)


def get_family(name: str) -> StrategyFamily:
    key = _ALIASES.get(name, name)
    try:
        return _FAMILIES[key]
    except KeyError as exc:
        raise ValueError(
            f"Familia desconocida: {name!r}. Disponibles: {', '.join(available_families())}"
        ) from exc


def registered_families(*, include_scaffolds: bool = True) -> list[StrategyFamily]:
    return [get_family(name) for name in available_families(include_scaffolds=include_scaffolds)]


__all__ = ["available_families", "get_family", "registered_families"]
