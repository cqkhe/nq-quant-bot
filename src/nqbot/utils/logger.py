"""Logger central.

Cada corrida escribe a consola (resumen) y a un archivo propio en logs/
(detalle completo con timestamp). Toda decisión del bot — señal, skip,
fill, salida, bloqueo de riesgo — pasa por acá para poder auditarla.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

_CONSOLE_FMT = "%(asctime)s %(levelname)-7s %(message)s"
_FILE_FMT = "%(asctime)s %(levelname)-7s [%(module)s] %(message)s"


def setup_logger(
    name: str = "nqbot",
    log_dir: str | Path | None = "logs",
    level: int = logging.INFO,
) -> logging.Logger:
    """Configura y devuelve el logger del proyecto (idempotente)."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_CONSOLE_FMT, datefmt="%H:%M:%S"))
    logger.addHandler(console)

    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_handler = logging.FileHandler(log_dir / f"{name}_{stamp}.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(_FILE_FMT))
        logger.addHandler(file_handler)

    return logger
