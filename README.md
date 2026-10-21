# Latency-Aware Aircraft State Estimation

This project studies how well aircraft state estimators recover an aircraft's
current position and motion when telemetry is delayed, irregular, or missing.
The planned comparison includes constant-velocity dead reckoning, an Extended
Kalman Filter (EKF), a Gated Recurrent Unit (GRU), and a Long Short-Term Memory
network (LSTM).

The central question is whether recurrent models provide enough additional
accuracy under degraded telemetry to justify their computational cost compared
with a classical state estimator. The complete research plan is available in
[Research Proposal.md](Research%20Proposal.md).

## Current status

The initial data-pipeline and baseline milestone is implemented:

- download public OpenSky CSV archives;
- normalize archive and future Trino data into one schema;
- flag and clean invalid, stale, or duplicated observations;
- segment observations into continuous aircraft trajectories;
- convert WGS84 positions into trajectory-local East-North-Up coordinates;
- create aircraft-grouped train, validation, and test partitions;
- construct fixed-length sequence windows;
- run the constant-velocity dead-reckoning baseline; and
- calculate position, altitude, velocity, and inference-latency metrics.

The EKF, telemetry degradation simulator, GRU, and LSTM are planned subsequent
stages.

## Pipeline overview

```text
OpenSky .csv.tar --> archive adapter --+
                                      +--> canonical state-vector DataFrame
Trino query result -> Trino adapter ---+
                                                 |
                                                 v
                                       validation and cleaning
                                                 |
                                                 v
                                       trajectory segmentation
                                                 |
                                                 v
                                        local ENU coordinates
                                                 |
                           +---------------------+---------------------+
                           v                     v                     v
                     split manifest       sequence windows      dead reckoning
                                                                       |
                                                                       v
                                                               evaluation metrics
```

Only the source adapter changes when Trino access becomes available. Every
downstream stage consumes the same canonical schema.

## Requirements

- Python 3.12 or later
- [`uv`](https://docs.astral.sh/uv/) for environment and dependency management

Install the environment:

```bash
uv sync
```

## Getting OpenSky data

Download CSV archives recursively from one OpenSky date/hour folder:

```bash
uv run python -m pipeline.pipeline \
  "https://opensky-network.org/datasets/states/2022-01-17/07/" \
  --output-dir data/raw
```

Supplying a date-level folder downloads CSV archives from all hourly child
folders:

```bash
uv run python -m pipeline.pipeline \
  "https://opensky-network.org/datasets/states/2022-01-17/" \
  --output-dir data/raw
```

Higher-level folders can contain large amounts of data. Start with one hour
while developing.

OpenSky publishes the CSV inside a TAR as a gzip-compressed member:

```text
states_2022-01-17-07.csv.tar
└── states_2022-01-17-07.csv.gz
```

The source adapter reads this structure directly; manual extraction is not
required.

## Normalize an archive

Create canonical and cleaned Parquet files without running the full baseline:

```bash
uv run normalize-opensky \
  data/raw/states_2022-01-17-07.csv.tar \
  --output data/interim/states_2022-01-17-07.normalized.parquet \
  --clean-output data/processed/states_2022-01-17-07.clean.parquet
```

This also creates a JSON data-quality report beside the normalized output.
Normalization is non-destructive: questionable rows receive explicit quality
flags. Cleaning separately applies the configured filtering policy. See
[Data normalization](docs/data-normalization.md) for the canonical schema and
edge-case policy.

## Run the complete baseline pipeline

Experiment settings are stored in
[configs/baseline.yaml](configs/baseline.yaml).

Run the full available archive:

```bash
uv run build-baseline \
  data/raw/states_2022-01-17-07.csv.tar \
  --config configs/baseline.yaml \
  --output-root artifacts/baseline-2022-01-17-07
```

Run a faster integration test:

```bash
uv run build-baseline \
  data/raw/states_2022-01-17-07.csv.tar \
  --config configs/baseline.yaml \
  --output-root artifacts/smoke-test \
  --nrows 100000
```

`--nrows` reads the leading rows and is intended only for software validation.
Because the archive is ordered by time, that subset is not statistically
representative.

## Generated artifacts

```text
artifacts/<run-name>/
├── interim/
│   ├── normalized.parquet
│   └── cleaned.parquet
├── processed/
│   ├── trajectories.parquet
│   ├── trajectory_summary.parquet
│   ├── split_manifest.parquet
│   ├── windows.npz
│   └── windows.metadata.parquet
├── evaluation/
│   ├── dead_reckoning_predictions.parquet
│   ├── dead_reckoning_metrics.csv
│   └── dead_reckoning_latency.parquet
└── run_report.json
```

Generated data and artifacts are ignored by Git. Configuration, source code,
tests, and documentation remain versioned.

## Current baseline run

The complete `2022-01-17 07:00-08:00 UTC` archive produced:

| Stage | Count |
| --- | ---: |
| Normalized observations | 1,219,248 |
| Cleaned airborne positions | 801,854 |
| Trajectory segments | 8,860 |
| Eligible trajectories | 7,240 |
| Fixed-length windows | 668,542 |
| Dead-reckoning predictions | 3,041,421 |

Preliminary test-partition horizontal errors were:

| Prediction horizon | Median error | RMSE | 95th percentile |
| ---: | ---: | ---: | ---: |
| 10 seconds | 77.7 m | 331.8 m | 530.0 m |
| 20 seconds | 122.2 m | 384.8 m | 753.8 m |
| 30 seconds | 174.9 m | 506.8 m | 1,109.7 m |
| 60 seconds | 373.3 m | 1,208.5 m | 2,549.4 m |

These are engineering-validation results from one global hour, not final
research conclusions. Many tracks are truncated by the hourly file boundaries,
and the data does not yet provide date-level generalization tests.

## Using future Trino data

The Trino adapter accepts a query result as a Pandas DataFrame:

```python
from aircraft_state_estimation.data import normalize_trino_result

raw_trino_frame = trino_client.query("SELECT ... FROM state_vectors_data4 ...")

normalized = normalize_trino_result(
    raw_trino_frame,
    query_id="experiment-001",
)
```

The resulting DataFrame uses the same columns as archive-normalized data and can
be passed directly into trajectory construction, coordinate conversion,
windowing, and evaluation.

## Tests and code quality

```bash
uv run pytest -q
uv run ruff check src tests pipeline
uv run mypy src/aircraft_state_estimation
```

The test suite covers schema normalization, compressed archive ingestion,
quality flags, deterministic cleaning, trajectory segmentation, coordinate
conversion, leakage-resistant splitting, sequence windows, dead reckoning, and
evaluation metrics.

## Project structure

```text
aircraft-state-estimation/
├── configs/
│   └── baseline.yaml
├── docs/
│   ├── data-normalization.md
│   └── data-pipeline-and-baseline.md
├── notebooks/
│   └── explore_open_sky.ipynb
├── pipeline/
│   └── pipeline.py
├── src/aircraft_state_estimation/
│   ├── baseline_pipeline.py
│   ├── data/
│   │   ├── coordinates.py
│   │   ├── normalize.py
│   │   ├── schema.py
│   │   ├── sources.py
│   │   ├── splits.py
│   │   ├── trajectories.py
│   │   └── windows.py
│   ├── evaluation/
│   │   └── metrics.py
│   └── models/
│       └── dead_reckoning.py
├── tests/
├── pyproject.toml
└── Research Proposal.md
```

## Detailed methodology

- [State-vector normalization](docs/data-normalization.md)
- [Data pipeline and baseline construction](docs/data-pipeline-and-baseline.md)
- [Research proposal](Research%20Proposal.md)

README.md
