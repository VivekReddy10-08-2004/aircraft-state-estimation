"""Constant-velocity dead-reckoning baseline."""

from __future__ import annotations

from time import perf_counter_ns

import numpy as np
import pandas as pd


def predict_dead_reckoning(
    frame: pd.DataFrame,
    *,
    horizons_s: tuple[int, ...] = (10, 20, 30, 60),
    interval_tolerance_s: float = 1.0,
) -> pd.DataFrame:
    """Evaluate constant-velocity propagation against future track states."""
    required = {
        "trajectory_id",
        "icao24",
        "timestamp_s",
        "partition",
        "east_m",
        "north_m",
        "up_m",
        "velocity_east_mps",
        "velocity_north_mps",
        "velocity_up_mps",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing dead-reckoning columns: {sorted(missing)}")

    base_columns = [
        "trajectory_id",
        "icao24",
        "partition",
        "timestamp_s",
        "east_m",
        "north_m",
        "up_m",
        "velocity_east_mps",
        "velocity_north_mps",
        "velocity_up_mps",
    ]
    observed = frame[base_columns].dropna().copy()
    predictions: list[pd.DataFrame] = []
    for horizon in horizons_s:
        future = observed[
            [
                "trajectory_id",
                "timestamp_s",
                "east_m",
                "north_m",
                "up_m",
                "velocity_east_mps",
                "velocity_north_mps",
                "velocity_up_mps",
            ]
        ].rename(
            columns={
                "timestamp_s": "target_time_s",
                "east_m": "true_east_m",
                "north_m": "true_north_m",
                "up_m": "true_up_m",
                "velocity_east_mps": "true_velocity_east_mps",
                "velocity_north_mps": "true_velocity_north_mps",
                "velocity_up_mps": "true_velocity_up_mps",
            }
        )
        current = observed.rename(
            columns={
                "timestamp_s": "observation_time_s",
                "east_m": "observed_east_m",
                "north_m": "observed_north_m",
                "up_m": "observed_up_m",
                "velocity_east_mps": "observed_velocity_east_mps",
                "velocity_north_mps": "observed_velocity_north_mps",
                "velocity_up_mps": "observed_velocity_up_mps",
            }
        )
        current["expected_target_time_s"] = current["observation_time_s"] + horizon
        result = current.merge(
            future,
            left_on=["trajectory_id", "expected_target_time_s"],
            right_on=["trajectory_id", "target_time_s"],
            how="inner",
            validate="many_to_one",
        )
        actual_horizon = result["target_time_s"] - result["observation_time_s"]
        result = result.loc[
            (actual_horizon - horizon).abs() <= interval_tolerance_s
        ].copy()
        result["prediction_horizon_s"] = horizon
        result["predicted_east_m"] = (
            result["observed_east_m"]
            + result["observed_velocity_east_mps"] * horizon
        )
        result["predicted_north_m"] = (
            result["observed_north_m"]
            + result["observed_velocity_north_mps"] * horizon
        )
        result["predicted_up_m"] = (
            result["observed_up_m"]
            + result["observed_velocity_up_mps"] * horizon
        )
        # Constant velocity predicts unchanged velocity components.
        result["predicted_velocity_east_mps"] = result[
            "observed_velocity_east_mps"
        ]
        result["predicted_velocity_north_mps"] = result[
            "observed_velocity_north_mps"
        ]
        result["predicted_velocity_up_mps"] = result["observed_velocity_up_mps"]
        predictions.append(result)

    return pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()


def benchmark_latency(
    states: pd.DataFrame,
    *,
    horizon_s: float = 10.0,
    sample_size: int = 10_000,
    random_seed: int = 42,
) -> pd.DataFrame:
    """Measure scalar per-update latency separately from batch evaluation."""
    columns = [
        "east_m",
        "north_m",
        "up_m",
        "velocity_east_mps",
        "velocity_north_mps",
        "velocity_up_mps",
    ]
    values = states[columns].dropna().to_numpy(dtype=float)
    if not len(values):
        return pd.DataFrame(columns=["latency_ns"])
    rng = np.random.default_rng(random_seed)
    indices = rng.choice(len(values), size=min(sample_size, len(values)), replace=False)
    latency = np.empty(len(indices), dtype=np.int64)
    for output_index, row_index in enumerate(indices):
        state = values[row_index]
        start = perf_counter_ns()
        _predict_one(state, horizon_s)
        latency[output_index] = perf_counter_ns() - start
    return pd.DataFrame({"latency_ns": latency})


def _predict_one(state: np.ndarray, horizon_s: float) -> tuple[float, ...]:
    east, north, up, velocity_east, velocity_north, velocity_up = state
    return (
        east + velocity_east * horizon_s,
        north + velocity_north * horizon_s,
        up + velocity_up * horizon_s,
        velocity_east,
        velocity_north,
        velocity_up,
    )
