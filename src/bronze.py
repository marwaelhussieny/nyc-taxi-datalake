"""
Bronze layer: raw ingestion.

Downloads a month of NYC Yellow Taxi trip data (public Parquet files from
the NYC TLC) and writes it into an Iceberg table almost as-is - only adding
lineage columns (source file, ingested_at). No cleaning, no filtering.
Bronze is a faithful copy of the source, warts and all - that's what makes
it useful as a re-processable foundation for silver/gold.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq
import requests

from catalog import get_catalog, table_location

logger = logging.getLogger(__name__)

TLC_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
NAMESPACE = "nyc_taxi_lakehouse"
BRONZE_TABLE = "bronze_yellow_trips"


def download_month(year: int, month: int, dest_path: str) -> str:
    """Download one month of yellow taxi trip data. Returns the local file path."""
    url = f"{TLC_BASE_URL}/yellow_tripdata_{year:04d}-{month:02d}.parquet"
    logger.info("Downloading %s", url)
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    logger.info("Saved to %s", dest_path)
    return dest_path


def ingest_month(year: int, month: int, local_path: str) -> int:
    """Read a downloaded parquet file, tag it with lineage columns, append to the bronze Iceberg table."""
    table_arrow = pq.read_table(local_path)

    source_file = f"yellow_tripdata_{year:04d}-{month:02d}.parquet"
    n = table_arrow.num_rows
    table_arrow = table_arrow.append_column(
        "source_file", pa.array([source_file] * n, type=pa.string())
    )
    table_arrow = table_arrow.append_column(
        "ingested_at", pa.array([datetime.now(timezone.utc)] * n, type=pa.timestamp("us", tz="UTC"))
    )

    catalog = get_catalog()
    identifier = (NAMESPACE, BRONZE_TABLE)

    if not catalog.table_exists(identifier):
        logger.info("Creating bronze table %s", identifier)
        catalog.create_namespace_if_not_exists(NAMESPACE)
        iceberg_table = catalog.create_table(
            identifier,
            schema=table_arrow.schema,
            location=table_location("bronze", BRONZE_TABLE),
        )
    else:
        iceberg_table = catalog.load_table(identifier)

    iceberg_table.append(table_arrow)
    logger.info("Appended %d rows to bronze.%s (source=%s)", n, BRONZE_TABLE, source_file)
    return n


if __name__ == "__main__":
    import argparse
    import os
    import tempfile

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    args = parser.parse_args()

    tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        download_month(args.year, args.month, tmp_path)
        ingest_month(args.year, args.month, tmp_path)
    finally:
        os.unlink(tmp_path)
