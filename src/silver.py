"""
Silver layer: cleaned, conformed trip records.

Reads the bronze Iceberg table, applies real-world data quality handling
specific to this dataset, and writes a clean, typed Iceberg table.

Known issues in NYC TLC data handled here:
- A meaningful fraction of trips have negative fares/tips (refunds/corrections
  in the source system) - these are flagged, not silently dropped.
- passenger_count is sometimes 0 or null (vendor reporting gaps).
- trip_distance of 0 with nonzero fare happens for flat-rate trips (e.g.
  airport trips) - not necessarily bad data, so not dropped outright.
- Trips with dropoff before pickup, or spanning more than 24 hours, are
  almost certainly bad timestamps and are excluded, with the count logged.
"""
from __future__ import annotations

import logging

import pyarrow as pa
import pyarrow.compute as pc

from catalog import get_catalog, table_location
from data_quality import run_data_quality_checks

logger = logging.getLogger(__name__)

NAMESPACE = "nyc_taxi_lakehouse"
BRONZE_TABLE = "bronze_yellow_trips"
SILVER_TABLE = "silver_yellow_trips"


def _clean(table: pa.Table) -> pa.Table:
    n_before = table.num_rows

    table = table.rename_columns([c.lower() for c in table.column_names])

    duration_seconds = pc.subtract(
        pc.cast(table["tpep_dropoff_datetime"], pa.int64()),
        pc.cast(table["tpep_pickup_datetime"], pa.int64()),
    )
    duration_minutes = pc.divide(pc.cast(duration_seconds, pa.float64()), 60_000_000.0)
    table = table.append_column("trip_duration_minutes", duration_minutes)

    valid_duration = pc.and_(
        pc.greater(table["trip_duration_minutes"], 0),
        pc.less_equal(table["trip_duration_minutes"], 24 * 60),
    )
    table = table.filter(valid_duration)

    is_valid_fare = pc.greater_equal(table["fare_amount"], 0)
    table = table.append_column("is_valid_fare", is_valid_fare)

    passenger_count_clean = pc.fill_null(table["passenger_count"], 0)
    table = table.set_column(
        table.schema.get_field_index("passenger_count"), "passenger_count", passenger_count_clean
    )

    n_after = table.num_rows
    logger.info(
        "Silver clean: %d -> %d rows (%d dropped for invalid duration)",
        n_before, n_after, n_before - n_after,
    )
    return table


def transform_to_silver() -> int:
    catalog = get_catalog()
    bronze = catalog.load_table((NAMESPACE, BRONZE_TABLE))
    bronze_arrow = bronze.scan().to_arrow()

    clean = _clean(bronze_arrow)
    run_data_quality_checks(clean)  # raises DataQualityError on failure, stops the pipeline

    identifier = (NAMESPACE, SILVER_TABLE)
    if not catalog.table_exists(identifier):
        logger.info("Creating silver table %s", identifier)
        iceberg_table = catalog.create_table(
            identifier,
            schema=clean.schema,
            location=table_location("silver", SILVER_TABLE),
        )
    else:
        iceberg_table = catalog.load_table(identifier)
        iceberg_table.delete(delete_filter="true")

    iceberg_table.append(clean)
    logger.info("Silver table now has %d rows", clean.num_rows)
    return clean.num_rows


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    transform_to_silver()
