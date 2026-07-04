"""Auditoría de calidad de datos — el gate previo a todo backtest.

Filosofía: un backtest sobre datos rotos es peor que no backtestear, porque
produce confianza falsa. Este módulo inspecciona los datos CRUDOS (antes del
saneo) y emite un veredicto:

  * WARNING  -> problema menor, por debajo del umbral configurado; el
                saneador (validators) lo repara o descarta. El backtest corre.
  * ERROR    -> problema estructural o por encima del umbral. El backtest
                NO corre (ver assert_fit_for_backtest).

Chequeos implementados:
  1. Timestamps duplicados.
  2. Velas faltantes en la ventana de sesión activa (vs. las esperadas).
  3. Valores nulos en OHLC / volumen.
  4. Precios incoherentes (high < low, OHLC imposible, precios <= 0) y
     saltos barra-a-barra sospechosos de bad ticks.
  5. Volumen cero dentro de la ventana activa.
  6. Gaps intra-sesión (huecos contiguos mayores a N minutos).
  7. Problemas de zona horaria: offsets tz en el archivo (se convierten a ET
     y se informa), barras en fin de semana (los futuros no operan sábado ni
     domingo antes de la reapertura Globex) y heurística de datos en UTC
     (la masa horaria no coincide con la sesión RTH pero sí desplazada +4/+5h).

Los umbrales viven en config.yaml -> data_quality.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

import numpy as np
import pandas as pd

from ..config.settings import CalendarConfig, DataQualityConfig, SessionConfig
from ..utils.sessions import (
    expected_bars_per_session,
    filter_to_trade_session,
    time_in_range,
    trade_session_key,
    window_minutes,
)
from .loader import ParseMeta

SEV_ERROR = "ERROR"
SEV_WARNING = "WARNING"

_OHLC = ["open", "high", "low", "close"]


class DataQualityError(Exception):
    """Los datos no superan las validaciones mínimas para backtestear."""


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    code: str
    message: str


@dataclass
class QualityReport:
    source: str
    stats: dict[str, Any] = field(default_factory=dict)
    issues: list[QualityIssue] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    def add(self, severity: str, code: str, message: str) -> None:
        self.issues.append(QualityIssue(severity, code, message))

    @property
    def errors(self) -> list[QualityIssue]:
        return [i for i in self.issues if i.severity == SEV_ERROR]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    @property
    def verdict(self) -> str:
        return "NO APTO PARA BACKTEST" if self.has_errors else "APTO PARA BACKTEST"

    def to_text(self) -> str:
        lines = [
            "=" * 66,
            "  REPORTE DE CALIDAD DE DATOS — nqbot",
            f"  Fuente:   {self.source}",
            f"  Generado: {self.generated_at:%Y-%m-%d %H:%M:%S}",
            "=" * 66,
            f"  VEREDICTO: {self.verdict}",
            "-" * 66,
        ]
        for key, value in self.stats.items():
            lines.append(f"  {key:<34} {value}")
        lines.append("-" * 66)
        if not self.issues:
            lines.append("  Sin problemas detectados.")
        else:
            lines.append(f"  Problemas detectados: {len(self.issues)}")
            for issue in sorted(self.issues, key=lambda i: i.severity != SEV_ERROR):
                lines.append(f"  [{issue.severity}] {issue.code}: {issue.message}")
        lines.append("=" * 66)
        return "\n".join(lines)


def assert_fit_for_backtest(report: QualityReport) -> None:
    """Lanza DataQualityError si el dataset tiene errores bloqueantes."""
    if report.has_errors:
        detail = "; ".join(f"{i.code}: {i.message}" for i in report.errors)
        raise DataQualityError(f"Datos NO aptos para backtest -> {detail}")


class DataQualityChecker:
    def __init__(
        self,
        session_cfg: SessionConfig,
        cfg: DataQualityConfig,
        calendar: CalendarConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.session_cfg = session_cfg
        self.cfg = cfg
        self.calendar = calendar or CalendarConfig()
        self.log = logger or logging.getLogger("nqbot")

    # ------------------------------------------------------------------ público
    def check(self, df: pd.DataFrame, meta: ParseMeta | None = None) -> QualityReport:
        report = QualityReport(source=meta.source if meta else "(DataFrame en memoria)")
        n_total = len(df)
        if n_total == 0:
            report.add(SEV_ERROR, "vacio", "el dataset no tiene filas")
            return report

        dedup = df[~df.index.duplicated(keep="first")].sort_index()
        interval_min = self._infer_interval(dedup.index)

        report.stats["Barras totales"] = f"{n_total:,}"
        report.stats["Rango"] = f"{dedup.index[0]} -> {dedup.index[-1]}"
        report.stats["Intervalo inferido"] = f"{interval_min} min"

        if meta is not None:
            self._check_parse_meta(report, meta)
        self._check_duplicates(report, df, n_total)
        self._check_nulls(report, df, n_total)
        valid = dedup.dropna(subset=_OHLC)
        self._check_price_coherence(report, valid)
        self._check_weekend_bars(report, dedup.index)
        self._check_utc_heuristic(report, dedup.index)
        self._check_active_session(report, valid, interval_min)
        return report

    # ------------------------------------------------------------------ chequeos
    def _infer_interval(self, idx: pd.DatetimeIndex) -> int:
        diffs = idx.to_series().diff().dropna()
        if diffs.empty:
            return 1
        mode = diffs.mode().iloc[0]
        return max(1, int(round(mode / pd.Timedelta(minutes=1))))

    def _pct_issue(
        self, report: QualityReport, count: int, total: int,
        threshold_pct: float, code: str, what: str,
    ) -> None:
        """WARNING por debajo del umbral, ERROR por encima."""
        if count <= 0 or total <= 0:
            return
        pct = count / total * 100.0
        severity = SEV_ERROR if pct > threshold_pct else SEV_WARNING
        report.add(severity, code, f"{count} {what} ({pct:.2f}% ; umbral {threshold_pct}%)")

    def _check_parse_meta(self, report: QualityReport, meta: ParseMeta) -> None:
        if meta.had_timezone:
            report.add(
                SEV_WARNING, "timezone",
                f"el archivo traía offsets de timezone; convertido a {self.session_cfg.timezone}",
            )
        self._pct_issue(
            report, meta.invalid_timestamps, max(1, meta.rows_in_file),
            self.cfg.max_nan_pct, "timestamps_invalidos", "timestamps no parseables",
        )

    def _check_duplicates(self, report: QualityReport, df: pd.DataFrame, n: int) -> None:
        dups = int(df.index.duplicated().sum())
        self._pct_issue(report, dups, n, self.cfg.max_duplicate_pct,
                        "duplicados", "timestamps duplicados")

    def _check_nulls(self, report: QualityReport, df: pd.DataFrame, n: int) -> None:
        nan_rows = int(df[_OHLC].isna().any(axis=1).sum())
        self._pct_issue(report, nan_rows, n, self.cfg.max_nan_pct,
                        "nulos", "filas con OHLC nulo")
        nan_vol = int(df["volume"].isna().sum())
        if nan_vol:
            report.add(SEV_WARNING, "nulos", f"{nan_vol} filas con volumen nulo")

    def _check_price_coherence(self, report: QualityReport, valid: pd.DataFrame) -> None:
        if valid.empty:
            return
        incoherent = (
            (valid["high"] < valid["low"])
            | (valid["high"] < valid[["open", "close"]].max(axis=1))
            | (valid["low"] > valid[["open", "close"]].min(axis=1))
            | (valid[_OHLC] <= 0).any(axis=1)
            | (valid["volume"] < 0)
        )
        self._pct_issue(report, int(incoherent.sum()), len(valid),
                        self.cfg.max_incoherent_pct, "precios_incoherentes",
                        "filas con OHLC imposible / precios no positivos")

        jumps = valid["close"].pct_change().abs() > self.cfg.max_bar_return_pct / 100.0
        n_jumps = int(jumps.sum())
        if n_jumps:
            first = valid.index[jumps][:3].tolist()
            report.add(
                SEV_WARNING, "saltos_extremos",
                f"{n_jumps} saltos > {self.cfg.max_bar_return_pct}% entre barras "
                f"(posibles bad ticks); primeros: {first}",
            )

    def _check_weekend_bars(self, report: QualityReport, idx: pd.DatetimeIndex) -> None:
        """Barras en fin de semana: pocas = prints espurios del proveedor (WARNING,
        se ignoran para la expectativa RTH); muchas = timezone corrida (ERROR)."""
        dow = idx.dayofweek
        saturday = int((dow == 5).sum())
        sunday_mask = dow == 6
        sunday_early = 0
        if sunday_mask.any():
            open_t = self.session_cfg.globex_open
            sunday_early = int(sum(t < open_t for t in idx[sunday_mask].time))
        total = saturday + sunday_early
        if not total:
            return
        pct = total / max(1, len(idx)) * 100.0
        detail = (
            f"{total} barras en fin de semana ({saturday} sábado, {sunday_early} domingo "
            f"antes de la reapertura Globex; {pct:.3f}%)"
        )
        if pct > self.cfg.max_weekend_bars_pct:
            report.add(SEV_ERROR, "fin_de_semana",
                       f"{detail}: probable timezone corrida o datos corruptos")
        else:
            report.add(SEV_WARNING, "fin_de_semana",
                       f"{detail}: prints espurios del proveedor; se ignoran para la "
                       f"expectativa de velas RTH")

    def _check_utc_heuristic(self, report: QualityReport, idx: pd.DatetimeIndex) -> None:
        if len(idx) < 500:
            return  # muestra chica: heurística poco confiable
        times = list(idx.time)
        rth_s, rth_e = self.session_cfg.rth_start, self.session_cfg.rth_end
        share_rth = np.mean([time_in_range(t, rth_s, rth_e) for t in times])
        # Datos RTH correctos: ~100% en RTH. Globex completo: ~28%. Datos RTH
        # en UTC: ~23% (solapamiento 14:30-16:00). El corte al 35% separa los
        # casos sanos de los sospechosos sin falsos positivos sobre Globex.
        if share_rth >= 0.35:
            return
        for offset in (4, 5):  # EDT / EST vs UTC
            s, e = _shift_time(rth_s, offset), _shift_time(rth_e, offset)
            share_shifted = np.mean([time_in_range(t, s, e) for t in times])
            if share_shifted > 0.50:
                report.add(
                    SEV_ERROR, "timezone",
                    f"solo {share_rth:.0%} de las barras cae en RTH pero {share_shifted:.0%} "
                    f"cae en RTH+{offset}h: los datos parecen estar en UTC, no en ET",
                )
                return

    def _check_active_session(
        self, report: QualityReport, valid: pd.DataFrame, interval_min: int
    ) -> None:
        cfg = self.session_cfg
        window = filter_to_trade_session(valid, cfg)
        report.stats["Ventana activa"] = (
            f"{cfg.trade_session} ({cfg.trade_window()[0]:%H:%M} -> {cfg.trade_window()[1]:%H:%M})"
        )
        report.stats["Barras en ventana activa"] = f"{len(window):,}"
        if window.empty:
            report.add(
                SEV_ERROR, "sesion_sin_datos",
                f"no hay ninguna barra dentro de la sesión configurada ({cfg.trade_session})",
            )
            return

        keys = trade_session_key(window.index, cfg)
        counts = window.groupby(keys).size()
        expected_full = expected_bars_per_session(cfg, interval_min)
        interval = max(1, interval_min)
        win_start = cfg.trade_window()[0]

        # --- clasificación de sesiones según el calendario del exchange
        # Sábados/domingos NUNCA son sesiones RTH esperadas (barras espurias de
        # finde crean "sesiones fantasma" que inflarían las velas faltantes).
        weekend_keys = [k for k in counts.index if k.dayofweek >= 5]
        holiday_keys = [
            k for k in counts.index
            if k.dayofweek < 5 and k.date() in self.calendar.no_session
        ]
        partial_keys = {
            k: self.calendar.partial_session[k.date()]
            for k in counts.index
            if k.dayofweek < 5
            and k.date() in self.calendar.partial_session
            and k.date() not in self.calendar.no_session
        }
        ignored = set(weekend_keys) | set(holiday_keys)
        evaluated = [k for k in counts.index if k not in ignored]

        # --- sección de sesiones del reporte (transparencia total)
        report.stats["Sesiones detectadas"] = len(counts)
        report.stats["Sesiones normales evaluadas"] = len(evaluated) - len(partial_keys)
        report.stats["Sesiones ignoradas (fin de semana)"] = (
            ", ".join(str(k.date()) for k in weekend_keys) if weekend_keys else 0
        )
        report.stats["Sesiones ignoradas (feriado)"] = (
            ", ".join(str(k.date()) for k in holiday_keys) if holiday_keys else 0
        )
        report.stats["Sesiones parciales aceptadas"] = (
            ", ".join(f"{k.date()} (cierre {t:%H:%M})" for k, t in partial_keys.items())
            if partial_keys else 0
        )
        report.stats["Velas esperadas por sesión normal"] = expected_full
        if holiday_keys:
            report.add(
                SEV_WARNING, "feriado_con_datos",
                f"{len(holiday_keys)} fecha(s) declaradas sin sesión traen datos igualmente: "
                f"{', '.join(str(k.date()) for k in holiday_keys)} (se ignoran)",
            )

        if not evaluated:
            report.add(SEV_ERROR, "sesion_sin_datos",
                       "ninguna sesión evaluable (todo cayó en fin de semana/feriados)")
            return

        # --- expectativa de velas por sesión evaluada
        expected_per_session = pd.Series(expected_full, index=pd.Index(evaluated))
        for k, early_close in partial_keys.items():
            expected_per_session.loc[k] = min(
                expected_full, window_minutes(win_start, early_close) // interval
            )
        # La última sesión evaluada puede estar cortada por el propio export
        # (tomado a mitad de rueda): solo se esperan velas hasta su última barra.
        last_key = max(evaluated)
        if last_key not in partial_keys:
            last_bar_time = window.index[keys == last_key].max().time()
            expected_last = min(
                int(expected_per_session.loc[last_key]),
                window_minutes(win_start, last_bar_time) // interval + 1,
            )
            if expected_last < expected_per_session.loc[last_key]:
                expected_per_session.loc[last_key] = expected_last
                report.stats["Última sesión (parcial por export)"] = (
                    f"{last_key.date()}: termina {last_bar_time:%H:%M}, se esperan {expected_last} velas"
                )

        # --- velas faltantes (solo sesiones evaluadas, con expectativa justa)
        missing_per_session = (expected_per_session - counts.reindex(evaluated)).clip(lower=0)
        total_missing = int(missing_per_session.sum())
        total_expected = int(expected_per_session.sum())
        report.stats["Velas faltantes (sesiones evaluadas)"] = f"{total_missing:,}"
        if total_missing:
            worst = missing_per_session.nlargest(3)
            worst_txt = ", ".join(f"{k.date()}: -{int(v)}" for k, v in worst.items() if v > 0)
            self._pct_issue(report, total_missing, total_expected,
                            self.cfg.max_missing_bars_pct, "velas_faltantes",
                            f"velas faltantes en sesiones evaluadas (peores: {worst_txt})")

        # --- volumen cero dentro de la ventana operada
        zero_vol = int((window["volume"] == 0).sum())
        self._pct_issue(report, zero_vol, len(window), self.cfg.max_zero_volume_pct,
                        "volumen_cero", "barras con volumen 0 en la ventana activa")

        # --- gaps intra-sesión REALES (solo en sesiones evaluadas; los huecos
        #     internos de una sesión parcial también cuentan)
        max_gap = pd.Timedelta(minutes=self.cfg.max_gap_minutes)
        events: list[str] = []
        for key in evaluated:
            session_df = window[keys == key]
            deltas = session_df.index.to_series().diff()
            for ts, delta in deltas[deltas > max_gap].items():
                events.append(f"{ts - delta} -> {ts} ({int(delta.total_seconds() // 60)} min)")
        report.stats["Gaps reales detectados"] = len(events)
        if events:
            shown = "; ".join(events[:5])
            extra = f" (+{len(events) - 5} más)" if len(events) > 5 else ""
            report.add(SEV_WARNING, "gaps_sesion",
                       f"{len(events)} gaps intra-sesión > {self.cfg.max_gap_minutes} min: "
                       f"{shown}{extra}")


def _shift_time(t: time, hours: int) -> time:
    total = (t.hour * 60 + t.minute + hours * 60) % 1440
    return time(total // 60, total % 60)
