# Data pipeline and baseline construction

## Scope

This implementation covers the proposal's initial data-pipeline and baseline
milestone:

1. retrieve and normalize OpenSky state vectors;
2. apply an auditable cleaning policy;
3. construct continuous aircraft tracks;
4. convert geodetic positions into local Cartesian coordinates;
5. create leakage-resistant train/validation/test partitions;
6. construct fixed-length trajectory windows;
7. evaluate constant-velocity dead reckoning; and
8. save reproducible metrics, latency measurements, and intermediate artifacts.

Archive ingestion and Trino ingestion terminate at the same canonical DataFrame.
Everything described below operates on canonical columns and is therefore
independent of the source.

## End-to-end flow

```text
.csv.tar or Trino DataFrame
          |
          v
canonical normalization + quality flags
          |
          v
explicit cleaning policy
          |
          v
time-gap and position-jump segmentation
          |
          v
trajectory-local East/North/Up coordinates
          |
          +----------> aircraft-grouped split manifest
          |
          +----------> fixed-length sequence windows
          |
          +----------> constant-velocity predictions
                                  |
                                  v
                       accuracy and latency metrics
```

The default experiment parameters live in
[`configs/baseline.yaml`](../configs/baseline.yaml). A run records the resolved
configuration in `run_report.json`.

## Cleaning policy

Normalization retains every row and adds quality flags. The separate cleaning
stage removes rows lacking a valid timestamp, aircraft address, or position;
rows with future update timestamps; stale positions or contacts; and states
explicitly marked on the ground. Duplicate `(icao24, timestamp_s)` observations
are resolved deterministically by retaining the newest contact.

Missing ground status remains unknown and is not treated as either true or
false. Optional model variables such as velocity and altitude are not globally
required during cleaning. Each later estimator selects observations containing
the variables it actually needs.

See [state-vector normalization](data-normalization.md) for the complete schema
and row-level edge-case policy.

## Trajectory construction

Rows are sorted by `icao24` and event time. A new trajectory begins when:

- an aircraft is first observed;
- the time since its previous observation exceeds `maximum_gap_s`;
- timestamps are repeated or move backward; or
- the great-circle distance divided by elapsed time exceeds
  `maximum_implied_speed_mps`.

Every row receives a deterministic `trajectory_id`, `sequence_index`, elapsed
time, step distance, and implied speed. Short tracks are retained and marked
with `is_short`; model construction excludes them under the configured minimum.

Tracks touching the beginning or end of the source interval are marked. With a
single hourly file these tracks may be censored by the file boundary and must
not be interpreted as complete flights.

The initial gap and speed thresholds are deliberately configurable. They are
engineering defaults for pipeline development, not final scientific findings.
Their sensitivity should be checked after multiple days are available.

## Coordinate system

Each trajectory uses a local East-North-Up (ENU) frame whose origin is its first
valid barometric-altitude position. Conversion uses:

```text
WGS84 latitude/longitude/altitude
        -> Earth-Centered Earth-Fixed (EPSG:4978)
        -> trajectory-local East/North/Up rotation
```

Using ECEF as the intermediate system avoids Universal Transverse Mercator zone
changes and longitude wraparound. The reference latitude, longitude, altitude,
and ECEF coordinates are stored with the observations so the transformation is
reproducible.

The model convention is:

- `east_m`: local x;
- `north_m`: local y;
- `up_m`: local z;
- `velocity_east_mps = speed * sin(heading)`;
- `velocity_north_mps = speed * cos(heading)`; and
- `velocity_up_mps = vertical_rate`.

OpenSky heading is clockwise from true north, which explains the sine/cosine
arrangement. Ground speed is not airspeed.

## Dataset partitions

Splits are assigned by `icao24`, not by row or window. Every trajectory from an
aircraft belongs to exactly one of training, validation, or test. This prevents
overlapping windows or multiple track fragments from the same aircraft leaking
between partitions.

The manifest records `trajectory_id`, aircraft, partition, split group, and
random seed. All future estimators must consume the saved manifest rather than
creating their own split.

Aircraft-grouped splitting tests generalization to unseen aircraft. With more
dates, a second date-based holdout should be added for temporal generalization.

## Fixed-length windows

The default window contains 120 seconds of history sampled every 10 seconds and
predicts 10 seconds ahead. A candidate window is accepted only when:

- it remains inside one trajectory and one partition;
- all adjacent timestamps match the configured interval within tolerance;
- required features and targets are present; and
- it does not cross a coverage gap.

Numeric arrays are saved in compressed NPZ form. Searchable provenance—track,
aircraft, partition, observation time, and target time—is saved as Parquet.

Window length and prediction horizon are defined in seconds rather than only in
row counts. This allows the same code to run at a different sampling interval
when Trino data becomes available.

## Constant-velocity baseline

For prediction horizon `tau`, the baseline uses:

```text
east(t + tau)  = east(t)  + velocity_east(t)  * tau
north(t + tau) = north(t) + velocity_north(t) * tau
up(t + tau)    = up(t)    + velocity_up(t)    * tau
```

Velocity is held constant. Predictions are matched only to a ground-truth state
from the same trajectory at the exact requested horizon. The default archive
evaluation uses 10, 20, 30, and 60 seconds because the public sample cadence is
approximately 10 seconds.

Two- and five-second experiments from the proposal are not fabricated through
interpolation at this stage. They require denser observations from Trino or an
explicitly documented interpolation experiment.

Batch prediction throughput and scalar per-update latency are measured
separately. Scalar latency is sampled with `perf_counter_ns`; it should be
treated as host- and runtime-specific rather than a universal hardware result.

## Metrics

Metrics are summarized separately by partition and prediction horizon:

- horizontal mean absolute error;
- horizontal root mean squared error;
- horizontal median and 95th-percentile error;
- vertical MAE and RMSE;
- three-dimensional position error on individual predictions;
- velocity-vector MAE and RMSE;
- contributing observation count; and
- contributing trajectory count.

Latency output includes mean, median, and 95th percentile in microseconds.
Later estimator implementations must emit the same prediction-column contract
so they can reuse these metrics unchanged.

## Running the pipeline

Run the full archive:

```bash
uv run build-baseline \
  data/raw/states_2022-01-17-07.csv.tar \
  --config configs/baseline.yaml \
  --output-root artifacts/baseline-2022-01-17-07
```

For a development smoke test:

```bash
uv run build-baseline \
  data/raw/states_2022-01-17-07.csv.tar \
  --config configs/baseline.yaml \
  --output-root artifacts/smoke-test \
  --nrows 100000
```

`--nrows` is only for software validation because the archive is ordered by
time. A leading-row subset is not a statistically representative sample.

## Artifacts

| Artifact | Purpose |
| --- | --- |
| `interim/normalized.parquet` | Complete canonical data with quality flags |
| `interim/cleaned.parquet` | Rows passing the configured cleaning policy |
| `processed/trajectories.parquet` | Segmented tracks in geodetic and ENU coordinates |
| `processed/trajectory_summary.parquet` | Track lengths, times, and boundary flags |
| `processed/split_manifest.parquet` | Stable aircraft-grouped partitions |
| `processed/windows.npz` | Sequence-model feature and target tensors |
| `processed/windows.metadata.parquet` | Window provenance and partition membership |
| `evaluation/dead_reckoning_predictions.parquet` | Per-observation truth and predictions |
| `evaluation/dead_reckoning_metrics.csv` | Accuracy summaries by split and horizon |
| `evaluation/dead_reckoning_latency.parquet` | Raw scalar latency samples |
| `run_report.json` | Data-quality counts and resolved configuration |

Generated data and experiment artifacts are excluded from version control.
Configuration, code, tests, and documentation are versioned.

## Current limitations

The present one-hour archive is adequate for implementation and preliminary
baseline validation, but not final scientific conclusions. It contains
boundary-censored flights, only one time of day, and no date-level holdout.
Final experiments should use multiple dates and preserve a temporal test set.

The current stage also does not interpolate tracks, classify maneuvers, inject
telemetry degradation, or estimate confidence intervals. Those are separate
stages so interpolation and artificial delay cannot contaminate clean ground
truth unnoticed.
