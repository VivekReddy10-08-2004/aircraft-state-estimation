from __future__ import annotations

import numpy as np
import pandas as pd

from aircraft_state_estimation.data import (
    SplitConfig,
    TrajectoryConfig,
    WindowConfig,
    add_local_enu_coordinates,
    build_fixed_windows,
    construct_trajectories,
    create_split_manifest,
)
from aircraft_state_estimation.evaluation import add_error_columns, summarize_errors
from aircraft_state_estimation.models import predict_dead_reckoning


def straight_tracks() -> pd.DataFrame:
    rows = []
    for aircraft_index, icao24 in enumerate(("abc123", "def456", "987abc")):
        for index in range(8):
            rows.append(
                {
                    "icao24": icao24,
                    "timestamp_s": float(index * 10),
                    "latitude_deg": 44.0 + aircraft_index * 0.1 + index * 0.0009,
                    "longitude_deg": -68.0,
                    "baro_altitude_m": 1000.0 + index * 10,
                    "ground_speed_mps": 10.0,
                    "heading_deg": 0.0,
                    "vertical_rate_mps": 1.0,
                    "contact_age_s": 1.0,
                    "position_age_s": 1.0,
                }
            )
    return pd.DataFrame(rows)


def test_trajectory_segmentation_on_time_gap_and_jump() -> None:
    frame = straight_tracks().loc[lambda value: value["icao24"] == "abc123"].copy()
    frame.loc[4:, "timestamp_s"] += 200

    trajectories, summary = construct_trajectories(
        frame, config=TrajectoryConfig(maximum_gap_s=120, minimum_points=3)
    )

    assert trajectories["trajectory_id"].nunique() == 2
    assert summary["point_count"].tolist() == [4, 4]
    assert trajectories["segment_break_time_gap"].sum() == 1


def test_enu_coordinates_have_local_origin_and_velocity_convention() -> None:
    trajectories, _ = construct_trajectories(straight_tracks())
    projected = add_local_enu_coordinates(trajectories)
    first = projected.groupby("trajectory_id", sort=False).first()

    assert np.allclose(first["east_m"], 0, atol=1e-6)
    assert np.allclose(first["north_m"], 0, atol=1e-6)
    assert np.allclose(first["up_m"], 0, atol=1e-6)
    assert np.allclose(projected["velocity_east_mps"], 0, atol=1e-12)
    assert np.allclose(projected["velocity_north_mps"], 10)


def test_aircraft_grouped_splits_prevent_leakage() -> None:
    _, summary = construct_trajectories(straight_tracks())
    manifest = create_split_manifest(
        summary,
        config=SplitConfig(
            train_fraction=1 / 3,
            validation_fraction=1 / 3,
            test_fraction=1 / 3,
            random_seed=7,
        ),
    )

    assert manifest.groupby("icao24")["partition"].nunique().max() == 1
    assert set(manifest["partition"]) == {"train", "validation", "test"}


def test_fixed_windows_do_not_cross_time_gaps() -> None:
    trajectories, summary = construct_trajectories(straight_tracks())
    projected = add_local_enu_coordinates(trajectories)
    manifest = create_split_manifest(summary)
    projected = projected.merge(
        manifest[["trajectory_id", "partition"]], on="trajectory_id"
    )
    windows = build_fixed_windows(
        projected,
        config=WindowConfig(
            history_seconds=30,
            prediction_horizon_seconds=10,
            sample_interval_seconds=10,
        ),
    )

    # Each eight-point track yields five 3-step histories with a one-step target.
    assert windows.features.shape == (15, 3, 8)
    assert windows.targets.shape == (15, 6)
    assert len(windows.metadata) == 15


def test_dead_reckoning_predictions_and_metrics() -> None:
    trajectories, summary = construct_trajectories(straight_tracks())
    projected = add_local_enu_coordinates(trajectories)
    manifest = create_split_manifest(summary)
    projected = projected.merge(
        manifest[["trajectory_id", "partition"]], on="trajectory_id"
    )
    predictions = predict_dead_reckoning(projected, horizons_s=(10,))
    predictions = add_error_columns(predictions)
    metrics = summarize_errors(predictions)

    assert len(predictions) == 21
    assert predictions["horizontal_error_m"].notna().all()
    assert metrics["observation_count"].sum() == 21
