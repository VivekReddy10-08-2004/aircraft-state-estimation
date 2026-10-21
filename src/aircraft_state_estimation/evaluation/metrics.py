"""Source- and model-independent state-estimation metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_error_columns(predictions: pd.DataFrame) -> pd.DataFrame:
    """Add horizontal, vertical, 3-D position, and velocity errors."""
    df = predictions.copy()
    east_error = df["predicted_east_m"] - df["true_east_m"]
    north_error = df["predicted_north_m"] - df["true_north_m"]
    up_error = df["predicted_up_m"] - df["true_up_m"]
    velocity_east_error = (
        df["predicted_velocity_east_mps"] - df["true_velocity_east_mps"]
    )
    velocity_north_error = (
        df["predicted_velocity_north_mps"] - df["true_velocity_north_mps"]
    )
    velocity_up_error = (
        df["predicted_velocity_up_mps"] - df["true_velocity_up_mps"]
    )
    df["horizontal_error_m"] = np.hypot(east_error, north_error)
    df["vertical_absolute_error_m"] = up_error.abs()
    df["position_3d_error_m"] = np.sqrt(
        east_error**2 + north_error**2 + up_error**2
    )
    df["velocity_error_mps"] = np.sqrt(
        velocity_east_error**2
        + velocity_north_error**2
        + velocity_up_error**2
    )
    return df


def summarize_errors(
    predictions: pd.DataFrame,
    *,
    group_columns: tuple[str, ...] = ("partition", "prediction_horizon_s"),
) -> pd.DataFrame:
    """Summarize metrics without pooling different partitions or horizons."""
    required = {
        "horizontal_error_m",
        "vertical_absolute_error_m",
        "velocity_error_mps",
        *group_columns,
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"Missing metric columns: {sorted(missing)}")

    def summarize(group: pd.DataFrame) -> pd.Series:
        horizontal = group["horizontal_error_m"]
        vertical = group["vertical_absolute_error_m"]
        velocity = group["velocity_error_mps"]
        return pd.Series(
            {
                "observation_count": len(group),
                "trajectory_count": group["trajectory_id"].nunique(),
                "horizontal_mae_m": horizontal.mean(),
                "horizontal_rmse_m": np.sqrt(np.mean(horizontal**2)),
                "horizontal_median_m": horizontal.median(),
                "horizontal_p95_m": horizontal.quantile(0.95),
                "vertical_mae_m": vertical.mean(),
                "vertical_rmse_m": np.sqrt(np.mean(vertical**2)),
                "velocity_mae_mps": velocity.mean(),
                "velocity_rmse_mps": np.sqrt(np.mean(velocity**2)),
            }
        )

    return (
        predictions.groupby(list(group_columns), dropna=False)
        .apply(summarize, include_groups=False)
        .reset_index()
    )


def summarize_latency(latency: pd.DataFrame) -> dict[str, float | int]:
    values = latency["latency_ns"] / 1_000
    return {
        "sample_count": len(values),
        "mean_latency_us": float(values.mean()),
        "median_latency_us": float(values.median()),
        "p95_latency_us": float(values.quantile(0.95)),
    }
