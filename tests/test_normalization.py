from __future__ import annotations

import gzip
import io
import tarfile

import pandas as pd
import pytest

from aircraft_state_estimation.data import (
    NormalizationConfig,
    clean_state_vectors,
    load_opensky_archive,
    normalize_state_vectors,
    normalize_trino_result,
    quality_report,
)


def raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": [100.0, 100.0, 200.0, 300.0],
            "icao24": [" ABC123 ", "abc123", "invalid", "def456"],
            "lat": [44.0, 44.1, 95.0, 45.0],
            "lon": [-68.0, -68.1, -68.0, -69.0],
            "velocity": [200.0, 210.0, -1.0, 500.0],
            "heading": [359.0, 361.0, 90.0, -1.0],
            "vertrate": [2.0, 3.0, 101.0, 0.0],
            "callsign": [" TEST1 ", "TEST1", None, ""],
            "onground": [False, "false", 0, True],
            "alert": [False, False, False, False],
            "spi": [False, False, False, False],
            "squawk": ["0123", "0123", None, "7700"],
            "baroaltitude": [1000.0, 1100.0, None, 0.0],
            "geoaltitude": [1010.0, 1110.0, None, 0.0],
            "lastposupdate": [99.0, 99.0, 180.0, 301.0],
            "lastcontact": [99.0, 98.0, 180.0, 300.0],
        }
    )


def test_normalization_preserves_rows_and_flags_edge_cases() -> None:
    normalized = normalize_state_vectors(raw_frame(), source="test")

    assert len(normalized) == 4
    assert normalized.loc[0, "icao24"] == "abc123"
    assert normalized.loc[0, "callsign"] == "TEST1"
    assert normalized.loc[1, "heading_deg"] == pytest.approx(1.0)
    assert bool(normalized.loc[1, "flag_invalid_heading"])
    assert bool(normalized.loc[2, "flag_invalid_coordinates"])
    assert bool(normalized.loc[2, "flag_negative_speed"])
    assert bool(normalized.loc[2, "flag_stale_contact"])
    assert bool(normalized.loc[3, "flag_excessive_ground_speed"])
    assert bool(normalized.loc[3, "flag_future_position_update"])
    assert normalized["flag_duplicate_aircraft_timestamp"].tolist()[:2] == [
        True,
        True,
    ]
    assert normalized.loc[0, "squawk"] == "0123"


def test_cleaning_is_explicit_and_deterministic() -> None:
    normalized = normalize_state_vectors(raw_frame(), source="test")
    cleaned = clean_state_vectors(normalized)

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["icao24"] == "abc123"
    assert cleaned.iloc[0]["last_contact_s"] == pytest.approx(99.0)


def test_archive_and_trino_share_canonical_prefix(tmp_path) -> None:
    csv_bytes = raw_frame().iloc[:1].to_csv(index=False).encode()
    compressed = gzip.compress(csv_bytes)
    archive_path = tmp_path / "sample.csv.tar"

    with tarfile.open(archive_path, mode="w") as archive:
        member = tarfile.TarInfo("nested/sample.csv.gz")
        member.size = len(compressed)
        archive.addfile(member, io.BytesIO(compressed))

    archive = load_opensky_archive(archive_path)
    trino = normalize_trino_result(raw_frame().iloc[:1], query_id="query-1")

    assert archive.columns.tolist() == trino.columns.tolist()
    assert archive.loc[0, "source"] == "opensky_public_archive"
    assert archive.loc[0, "source_member"] == "nested/sample.csv.gz"
    assert trino.loc[0, "source"] == "opensky_trino"
    assert trino.loc[0, "source_file"] == "query-1"


def test_quality_report_is_json_compatible() -> None:
    normalized = normalize_state_vectors(raw_frame(), source="test")
    cleaned = clean_state_vectors(normalized)
    report = quality_report(normalized, cleaned=cleaned)

    assert report["input_rows"] == 4
    assert report["cleaned_rows"] == 1
    assert report["quality_flag_counts"]["flag_invalid_icao24"] == 1
    assert report["configuration"] == NormalizationConfig().__dict__


def test_missing_required_columns_fail_loudly() -> None:
    with pytest.raises(ValueError, match="Missing required"):
        normalize_state_vectors(pd.DataFrame({"time": [1]}), source="test")


def test_unknown_boolean_encoding_fails_loudly() -> None:
    frame = raw_frame().iloc[:1].copy()
    frame["onground"] = "maybe"

    with pytest.raises(ValueError, match="Unrecognized boolean"):
        normalize_state_vectors(frame, source="test")
