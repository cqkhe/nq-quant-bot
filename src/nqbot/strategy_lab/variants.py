"""Generacion controlada de variantes."""

from __future__ import annotations

import random

from .models import StrategyFamily, StrategyVariant, make_variant


def generate_variants(
    family: StrategyFamily,
    *,
    max_variants: int | None = None,
    seed: int | None = None,
) -> list[StrategyVariant]:
    """Genera variantes deterministas desde la grilla de una familia."""

    if max_variants is not None and max_variants <= 0:
        raise ValueError("max_variants debe ser > 0")

    combos = family.parameter_grid.combinations()
    if max_variants is not None and max_variants < len(combos):
        rng = random.Random(seed)
        indices = list(range(len(combos)))
        rng.shuffle(indices)
        selected = sorted(indices[:max_variants])
        combos = [combos[i] for i in selected]

    return [make_variant(family, params) for params in combos]


__all__ = ["generate_variants"]
