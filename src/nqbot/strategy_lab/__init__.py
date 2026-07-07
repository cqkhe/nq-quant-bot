"""Strategy Lab / Strategy Search Engine."""

from .families import available_families, get_family, registered_families
from .filters import apply_filters
from .models import (
    ExperimentResult,
    ParameterGrid,
    StrategyFamily,
    StrategyFilterConfig,
    StrategyRanking,
    StrategySearchConfig,
    StrategySearchSuite,
    StrategyVariant,
)
from .ranking import rank_results, score_result
from .runner import run_strategy_search, run_strategy_search_suite, write_strategy_search_outputs
from .variants import generate_variants
from .volume_features import (
    classify_volume,
    classify_volume_zscore,
    is_volume_climax,
    is_volume_dry_up,
    is_volume_spike,
    relative_volume,
    rolling_volume_mean,
    rolling_volume_std,
    volume_zscore,
)

__all__ = [
    "ExperimentResult",
    "ParameterGrid",
    "StrategyFamily",
    "StrategyFilterConfig",
    "StrategyRanking",
    "StrategySearchConfig",
    "StrategySearchSuite",
    "StrategyVariant",
    "apply_filters",
    "available_families",
    "generate_variants",
    "get_family",
    "classify_volume",
    "classify_volume_zscore",
    "is_volume_climax",
    "is_volume_dry_up",
    "is_volume_spike",
    "rank_results",
    "relative_volume",
    "registered_families",
    "rolling_volume_mean",
    "rolling_volume_std",
    "run_strategy_search",
    "run_strategy_search_suite",
    "score_result",
    "volume_zscore",
    "write_strategy_search_outputs",
]
