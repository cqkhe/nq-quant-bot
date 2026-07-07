import math

import pandas as pd
import pytest

from nqbot.strategy_lab.volume_features import (
    classify_volume_zscore,
    is_volume_climax,
    is_volume_dry_up,
    is_volume_spike,
    relative_volume,
    rolling_volume_mean,
    rolling_volume_std,
    volume_zscore,
)


def test_rolling_volume_statistics_use_only_past_bars():
    volume = pd.Series([10, 20, 30, 40, 100], dtype="float64")

    mean = rolling_volume_mean(volume, window=3)
    std = rolling_volume_std(volume, window=3)

    assert mean.iloc[4] == 30.0
    assert math.isclose(std.iloc[4], 8.1649658093, rel_tol=1e-9)

    changed_current_bar = volume.copy()
    changed_current_bar.iloc[4] = 10_000
    assert rolling_volume_mean(changed_current_bar, window=3).iloc[4] == mean.iloc[4]
    assert rolling_volume_std(changed_current_bar, window=3).iloc[4] == std.iloc[4]


def test_volume_zscore_uses_past_mean_and_std():
    volume = pd.Series([10, 12, 14, 16, 30], dtype="float64")

    zscore = volume_zscore(volume, window=3)

    expected_mean = 14.0
    expected_std = math.sqrt(((12 - 14) ** 2 + (14 - 14) ** 2 + (16 - 14) ** 2) / 3)
    assert math.isclose(zscore.iloc[4], (30 - expected_mean) / expected_std, rel_tol=1e-9)


def test_relative_volume_uses_prior_average():
    volume = pd.Series([10, 20, 30, 40, 60], dtype="float64")

    rel = relative_volume(volume, window=3)

    assert rel.iloc[4] == 2.0


def test_volume_classification_and_detectors():
    zscore = pd.Series([-1.2, 0.0, 1.6, 2.1, 2.7, None])

    labels = classify_volume_zscore(zscore)

    assert labels.tolist() == ["low", "normal", "high", "extreme", "climax", "unknown"]
    assert is_volume_dry_up(zscore).tolist() == [True, False, False, False, False, False]
    assert is_volume_spike(zscore).tolist() == [False, False, True, True, True, False]
    assert is_volume_climax(zscore).tolist() == [False, False, False, False, True, False]


def test_volume_feature_parameter_validation():
    volume = pd.Series([1, 2, 3], dtype="float64")

    with pytest.raises(ValueError):
        rolling_volume_mean(volume, window=1)
    with pytest.raises(ValueError):
        rolling_volume_std(volume, window=0)
    with pytest.raises(ValueError):
        volume_zscore(volume, window=-5)
