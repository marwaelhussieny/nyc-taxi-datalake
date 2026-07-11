"""
Gold layer: business-ready aggregates.

Builds a daily grain, pickup-zone-level summary table from silver -
the kind of table a dashboard or analyst would actually query directly,
rather than scanning millions of trip-level rows every time.
"""
from __future__ import annotations

import logging

import pyarrow as pa
import pyarrow.compute as pc

from catalog import get_catalog, table_location

logger = logging.getLogger(__name__)

NAMESPACE = "nyc_taxi_lakehouse"
SILVER_TABLE = "silver_yellow_trips"
GOLD_TABLE = "gold_daily_zone_metrics"


def _aggregate(table: pa.Table) -> pa.Table:
    # Only include arm's-length, non-negative fares in revenue aggregates
    table = table.filter(pc.field("is_valid_fare"))

    pickup_date = pc.cast(table["tpep_pickup_datetime"], pa.date32())
    table = table.append_column("pickup_date", pickup_date)

    grouped = table.group_by(["pickup_date", "pulocationid"]).aggregate([
        ("fare_amount", "sum"),
        ("fare_amount", "mean"),
        ("trip_distance", "mean"),
        ("trip_duration_minutes", "mean"),
        ("passenger_count", "sum"),
        ("pickup_date", "count"),
    ])

    grouped = grouped.rename_columns([
        "pickup_date", "pulocationid",
        "total_revenue", "avg_fare", "avg_trip_distance",
        "avg_trip_duration_minutes", "total_passengers", "trip_count",
    ])

    logger.info("Gold aggregation produced %d zone-day rows", grouped.num_rows)
    return grouped


def build_gold() -> int:
    catalog = get_catalog()
    silver = catalog.load_table((NAMESPACE, SILVER_TABLE))
    silver_arrow = silver.scan().to_arrow()

    gold = _aggregate(silver_arrow)

    identifier = (NAMESPACE, GOLD_TABLE)
    if not catalog.table_exists(identifier):
        logger.info("Creating gold table %s", identifier)
        iceberg_table = catalog.create_table(
            identifier,
            schema=gold.schema,
            location=table_location("gold", GOLD_TABLE),
        )
    else:
        iceberg_table = catalog.load_table(identifier)
        iceberg_table.delete(delete_filter="true")

    iceberg_table.append(gold)
    logger.info("Gold table now has %d rows", gold.num_rows)
    return gold.num_rows


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_gold()
