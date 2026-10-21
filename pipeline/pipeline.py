"""Download CSV state-vector files from the public OpenSky archive."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx

BUCKET_URL = "https://s3.opensky-network.org/data-samples"
PUBLIC_DATASET_ROOT = "https://opensky-network.org/datasets/"
CSV_SUFFIXES = (".csv", ".csv.gz", ".csv.bz2", ".csv.zip", ".csv.tar")
S3_NAMESPACE = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


def folder_url_to_prefix(folder_url: str) -> str:
    """Convert an OpenSky browser URL into an S3 object-key prefix."""
    parsed = urlparse(folder_url)
    expected = urlparse(PUBLIC_DATASET_ROOT)

    if (parsed.scheme, parsed.netloc) != (expected.scheme, expected.netloc):
        raise ValueError(
            "folder_url must be below "
            f"{PUBLIC_DATASET_ROOT!r}; received {folder_url!r}"
        )

    root_path = expected.path.rstrip("/") + "/"
    if not parsed.path.startswith(root_path):
        raise ValueError(
            "folder_url must be below "
            f"{PUBLIC_DATASET_ROOT!r}; received {folder_url!r}"
        )

    prefix = parsed.path.removeprefix(root_path).lstrip("/")
    return prefix.rstrip("/") + "/"


def find_csv_urls(folder_url: str, *, timeout: float = 60.0) -> list[str]:
    """Return every CSV object recursively below an OpenSky folder.

    The public folder page is rendered with JavaScript, so scraping its HTML
    does not reveal the files. OpenSky's S3-compatible ListObjectsV2 endpoint
    accepts a prefix and, when no delimiter is supplied, returns objects in all
    descendant directories.
    """
    prefix = folder_url_to_prefix(folder_url)
    continuation_token: str | None = None
    object_keys: list[str] = []

    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        while True:
            params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
            if continuation_token:
                params["continuation-token"] = continuation_token

            response = client.get(BUCKET_URL, params=params)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            object_keys.extend(
                key.text
                for key in root.findall("s3:Contents/s3:Key", S3_NAMESPACE)
                if key.text and key.text.lower().endswith(CSV_SUFFIXES)
            )

            is_truncated = root.findtext(
                "s3:IsTruncated", default="false", namespaces=S3_NAMESPACE
            ).lower() == "true"
            if not is_truncated:
                break

            continuation_token = root.findtext(
                "s3:NextContinuationToken", namespaces=S3_NAMESPACE
            )
            if not continuation_token:
                raise RuntimeError("OpenSky returned a truncated listing without a token")

    return [f"{BUCKET_URL}/{key}" for key in sorted(set(object_keys))]


def download_file(
    url: str,
    output_dir: Path,
    *,
    timeout: float = 300.0,
) -> Path:
    """Stream one object to disk, retaining its filename."""
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / PurePosixPath(urlparse(url).path).name

    if destination.exists():
        print(f"Already downloaded: {destination}")
        return destination

    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with httpx.stream(
            "GET", url, follow_redirects=True, timeout=timeout
        ) as response:
            response.raise_for_status()
            with temporary.open("wb") as file:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    file.write(chunk)
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

    print(f"Downloaded: {destination}")
    return destination


def download_csvs(folder_url: str, output_dir: Path) -> list[Path]:
    """Discover and download all CSV files below ``folder_url``."""
    csv_urls = find_csv_urls(folder_url)
    if not csv_urls:
        prefix = folder_url_to_prefix(folder_url)
        raise RuntimeError(
            f"No CSV or CSV archive objects found below OpenSky prefix {prefix!r}"
        )

    print(f"Found {len(csv_urls)} CSV file(s) below {folder_url}")
    return [download_file(url, output_dir) for url in csv_urls]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download CSV state vectors below an OpenSky folder"
    )
    parser.add_argument(
        "folder_url",
        help=(
            "OpenSky folder, for example "
            "https://opensky-network.org/datasets/states/2022-01-17/07/"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
        help="Download directory (default: data/raw)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    download_csvs(args.folder_url, args.output_dir)


if __name__ == "__main__":
    main()
