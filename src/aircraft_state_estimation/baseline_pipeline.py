"""End-to-end data pipeline and constant-velocity baseline command."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from aircraft_state_estimation.data import (
    NormalizationConfig,
    SplitConfig,
    TrajectoryConfig,
    WindowConfig,
    add_local_enu_coordinates,
    build_fixed_windows,
    clean_state_vectors,
    construct_trajectories,
    create_split_manifest,
    load_opensky_archive,
    quality_report,
    save_window_dataset,
)
from aircraft_state_estimation.evaluation import (
    add_error_columns,
    summarize_errors,
    summarize_latency,
)
from aircraft_state_estimation.models import benchmark_latency, predict_dead_reckoning


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build trajectory artifacts and the dead-reckoning baseline"
    )
    parser.add_argument("archive", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/baseline.yaml"))
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/baseline"))
    parser.add_argument(
        "--nrows", type=int, help="Development-only limit passed to pandas"
    )
    return parser.parse_args()


def _dataclass_config(
    config: dict[str, Any], section: str, cls: type[Any]
) -> Any:
    return cls(**config.get(section, {}))


def run_pipeline(
    archive: Path,
    *,
    settings: dict[str, Any],
    output_root: Path,
    nrows: int | None = None,
) -> None:
    normalization = _dataclass_config(settings, "normalization", NormalizationConfig)
    trajectory_config = _dataclass_config(
        settings, "trajectories", TrajectoryConfig
    )
    split_config = _dataclass_config(settings, "split", SplitConfig)
    window_config = _dataclass_config(settings, "windows", WindowConfig)
    horizons = tuple(settings.get("baseline", {}).get("horizons_s", [10, 20, 30, 60]))

    interim = output_root / "interim"
    processed = output_root / "processed"
    evaluation = output_root / "evaluation"
    for directory in (interim, processed, evaluation):
        directory.mkdir(parents=True, exist_ok=True)

    read_options = {"nrows": nrows} if nrows is not None else None
    normalized = load_opensky_archive(
        archive, config=normalization, read_csv_options=read_options
    )
    cleaned = clean_state_vectors(normalized, config=normalization)
    normalized.to_parquet(interim / "normalized.parquet", index=False)
    cleaned.to_parquet(interim / "cleaned.parquet", index=False)

    trajectories, summary = construct_trajectories(
        cleaned, config=trajectory_config
    )
    trajectories = add_local_enu_coordinates(trajectories)
    manifest = create_split_manifest(summary, config=split_config)
    trajectories = trajectories.merge(
        manifest[["trajectory_id", "partition"]],
        on="trajectory_id",
        how="left",
        validate="many_to_one",
    )
    trajectories.to_parquet(processed / "trajectories.parquet", index=False)
    summary.to_parquet(processed / "trajectory_summary.parquet", index=False)
    manifest.to_parquet(processed / "split_manifest.parquet", index=False)

    eligible = trajectories.loc[~trajectories["is_short"]].copy()
    windows = build_fixed_windows(eligible, config=window_config)
    save_window_dataset(windows, str(processed / "windows"))

    predictions = predict_dead_reckoning(eligible, horizons_s=horizons)
    predictions = add_error_columns(predictions)
    predictions.to_parquet(evaluation / "dead_reckoning_predictions.parquet", index=False)
    metrics = summarize_errors(predictions)
    metrics.to_csv(evaluation / "dead_reckoning_metrics.csv", index=False)

    latency = benchmark_latency(eligible)
    latency.to_parquet(evaluation / "dead_reckoning_latency.parquet", index=False)
    audit = quality_report(normalized, cleaned=cleaned, config=normalization)
    audit["trajectory_count"] = len(summary)
    audit["eligible_trajectory_count"] = int((~summary["is_short"]).sum())
    audit["window_count"] = len(windows.metadata)
    audit["latency"] = summarize_latency(latency)
    audit["pipeline_configuration"] = {
        "normalization": asdict(normalization),
        "trajectories": asdict(trajectory_config),
        "split": asdict(split_config),
        "windows": asdict(window_config),
        "baseline": {"horizons_s": list(horizons)},
    }
    (output_root / "run_report.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n"
    )

    print(f"Normalized rows: {len(normalized):,}")
    print(f"Cleaned rows: {len(cleaned):,}")
    print(f"Trajectories: {len(summary):,}")
    print(f"Windows: {len(windows.metadata):,}")
    print(f"Baseline predictions: {len(predictions):,}")
    print(f"Artifacts: {output_root}")


def main() -> None:
    args = parse_args()
    settings = yaml.safe_load(args.config.read_text()) or {}
    run_pipeline(
        args.archive,
        settings=settings,
        output_root=args.output_root,
        nrows=args.nrows,
    )


if __name__ == "__main__":
    main()
