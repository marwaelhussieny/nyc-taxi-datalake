"""
Dagster asset definitions for the NYC Taxi medallion lakehouse.

Three assets, one per layer, each depending on the previous:
  bronze_yellow_trips -> silver_yellow_trips -> gold_daily_zone_metrics

Run on a monthly schedule, matching the cadence NYC TLC actually publishes
new data (with their own ~2 month reporting delay).
"""

import sys
from pathlib import Path

import dagster as dg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@dg.asset(group_name="bronze")
def bronze_yellow_trips(context: dg.AssetExecutionContext) -> None:
    """Downloads and ingests the most recent available month of yellow taxi trips."""
    import tempfile
    from datetime import date

    from bronze import download_month, ingest_month

    # TLC publishes with a ~2 month delay - target month before last
    today = date.today()
    target_month = today.month - 2 or 12
    target_year = today.year if today.month > 2 else today.year - 1

    with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
        download_month(target_year, target_month, tmp.name)
        n = ingest_month(target_year, target_month, tmp.name)

    context.add_output_metadata({"rows_ingested": n, "year": target_year, "month": target_month})


@dg.asset(group_name="silver", deps=[bronze_yellow_trips])
def silver_yellow_trips(context: dg.AssetExecutionContext) -> None:
    """Cleans bronze data and runs the data quality gate."""
    from silver import transform_to_silver

    n = transform_to_silver()
    context.add_output_metadata({"rows": n})


@dg.asset(group_name="gold", deps=[silver_yellow_trips])
def gold_daily_zone_metrics(context: dg.AssetExecutionContext) -> None:
    """Builds daily, per-zone business metrics from silver."""
    from gold import build_gold

    n = build_gold()
    context.add_output_metadata({"rows": n})


taxi_lakehouse_assets = [bronze_yellow_trips, silver_yellow_trips, gold_daily_zone_metrics]

monthly_schedule = dg.ScheduleDefinition(
    name="monthly_taxi_ingest",
    cron_schedule="0 6 3 * *",  # 3rd of each month, 6am - gives TLC's own publish delay room to breathe
    job=dg.define_asset_job("taxi_lakehouse_job", selection=taxi_lakehouse_assets),
)

defs = dg.Definitions(
    assets=taxi_lakehouse_assets,
    schedules=[monthly_schedule],
)
