# State-vector normalization

## Purpose

The archive and Trino ingestion paths must produce the same tabular contract.
All trajectory construction, coordinate conversion, windowing, simulation, and
modeling code consumes canonical Parquet rather than depending on a particular
OpenSky source.

```text
OpenSky .csv.tar -> archive adapter --+
                                      +-> normalize -> validate/flag -> Parquet
Trino DataFrame  -> Trino adapter -----+
```

Normalization is intentionally non-destructive. It standardizes names and
types, derives observation ages, records provenance, and flags questionable
rows. Cleaning is a separate, configurable operation. This makes data loss
auditable and allows source-quality comparisons when Trino becomes available.

## Canonical contract

The stable columns are:

| Column | Type/units | Meaning |
| --- | --- | --- |
| `timestamp_s` | Unix seconds | State-vector event time |
| `datetime_utc` | UTC datetime | Human-readable event time |
| `icao24` | string | Lowercase six-digit hexadecimal aircraft address |
| `callsign` | string | Trimmed broadcast callsign; not a unique flight ID |
| `latitude_deg`, `longitude_deg` | WGS84 degrees | Observed position |
| `baro_altitude_m`, `geo_altitude_m` | metres | Separate altitude measurements |
| `ground_speed_mps` | m/s | Ground speed, not airspeed |
| `heading_deg` | degrees | Clockwise from north, normalized to `[0, 360)` |
| `vertical_rate_mps` | m/s | Positive means climbing |
| `on_ground`, `alert`, `spi` | nullable boolean | OpenSky status fields |
| `squawk` | string | Preserves leading zeroes |
| `last_position_update_s`, `last_contact_s` | Unix seconds | Source update times |
| `position_age_s`, `contact_age_s` | seconds | Event time minus update time |
| `source`, `source_file`, `source_member` | string | Provenance |
| `schema_version` | string | Contract version |

Source-only columns such as Trino's `hour` and `serials` are retained after the
canonical columns for auditing, but downstream code must not require them.

## Edge-case policy

- Missing optional telemetry is retained as null; the pipeline never performs
  a blanket `dropna()`.
- Required schema changes fail loudly.
- Numeric parse failures become null and are visible in the quality report.
- Unknown boolean encodings fail loudly rather than silently becoming false.
- ICAO24 values are trimmed, lowercased, and validated but never converted to
  integers.
- Callsigns are trimmed but are not treated as flight identifiers.
- Barometric and geometric altitude remain separate.
- Squawk codes remain strings to preserve leading zeroes.
- Coordinates are range-checked. Missing positions and out-of-range positions
  have separate flags.
- Heading is circular. The normalized value uses modulo 360 while an invalid
  source range is still flagged.
- Duplicate `(icao24, timestamp_s)` keys are flagged. Cleaning retains the row
  with the latest `last_contact_s` deterministically.
- Source staleness is represented by `position_age_s` and `contact_age_s` and
  must remain distinct from experimentally simulated telemetry delay.
- Physically suspicious speeds and vertical rates are flagged using generous,
  configurable thresholds rather than deleted during normalization.
- Unknown `on_ground` values remain unknown. They are not treated as airborne.

Position jumps, trajectory gaps, repeated/frozen positions, implied velocity,
longitude wraparound, and projection consistency require adjacent observations.
They belong in trajectory validation rather than row-level normalization.

## Usage

Normalize an archive and create both audit and cleaned outputs:

```bash
uv run normalize-opensky \
  data/raw/states_2022-01-17-07.csv.tar \
  --output data/interim/states_2022-01-17-07.normalized.parquet \
  --clean-output data/processed/states_2022-01-17-07.clean.parquet
```

The command also writes a JSON quality report beside the normalized output.

From Python:

```python
from aircraft_state_estimation.data import (
    clean_state_vectors,
    load_opensky_archive,
    quality_report,
)

normalized = load_opensky_archive("data/raw/example.csv.tar")
cleaned = clean_state_vectors(normalized)
report = quality_report(normalized, cleaned=cleaned)
```

When Trino access is available:

```python
from aircraft_state_estimation.data import normalize_trino_result

raw = trino_client.query("SELECT ... FROM state_vectors_data4 ...")
normalized = normalize_trino_result(raw, query_id="experiment-001")
```

Both normalized frames have the same canonical column prefix and can be passed
to the same downstream code.

## What normalization does not do

Normalization does not define flights, interpolate telemetry, project latitude
and longitude, build fixed-length windows, create train/test partitions, or
inject delay and loss. Those stages require trajectory context and must remain
separate to prevent leakage and accidental interpolation across flights.
