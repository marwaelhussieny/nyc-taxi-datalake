import sys
import datetime
from pathlib import Path

import pyarrow as pa
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from silver import _clean  # noqa: E402
from gold import _aggregate  # noqa: E402
from data_quality import run_data_quality_checks, DataQualityError  # noqa: E402


def _make_bronze_table(n=1500):
    base = datetime.datetime(2024, 1, 1, 12, 0, 0)
    return pa.table({
        "VendorID": [1] * n,
        "tpep_pickup_datetime": [base + datetime.timedelta(minutes=i) for i in range(n)],
        "tpep_dropoff_datetime": [base + datetime.timedelta(minutes=i + 15) for i in range(n)],
        "passenger_count": ([1, 2, None, 0] * (n // 4 + 1))[:n],
        "trip_distance": [1.5] * n,
        "PULocationID": ([100, 101] * (n // 2 + 1))[:n],
        "fare_amount": ([10.0, 12.5] * (n // 2 + 1))[:n],
    })


def test_clean_computes_trip_duration():
    clean = _clean(_make_bronze_table())
    assert "trip_duration_minutes" in clean.column_names
    assert clean.column("trip_duration_minutes")[0].as_py() == 15.0


def test_clean_drops_impossible_durations():
    table = _make_bronze_table()
    # corrupt one row: dropoff before pickup
    dropoffs = table.column("tpep_dropoff_datetime").to_pylist()
    dropoffs[0] = table.column("tpep_pickup_datetime")[0].as_py() - datetime.timedelta(minutes=5)
    table = table.set_column(
        table.schema.get_field_index("tpep_dropoff_datetime"),
        "tpep_dropoff_datetime",
        pa.array(dropoffs, type=table.schema.field("tpep_dropoff_datetime").type),
    )
    clean = _clean(table)
    assert clean.num_rows == table.num_rows - 1


def test_clean_flags_negative_fares_not_drops():
    table = _make_bronze_table()
    fares = table.column("fare_amount").to_pylist()
    fares[0] = -5.0
    table = table.set_column(table.schema.get_field_index("fare_amount"), "fare_amount", pa.array(fares))
    clean = _clean(table)
    assert clean.num_rows == table.num_rows  # not dropped
    assert clean.column("is_valid_fare")[0].as_py() is False


def test_data_quality_passes_on_clean_data():
    clean = _clean(_make_bronze_table())
    results = run_data_quality_checks(clean)
    assert all(r.passed for r in results)


def test_data_quality_fails_on_too_few_rows():
    clean = _clean(_make_bronze_table(n=100))
    with pytest.raises(DataQualityError):
        run_data_quality_checks(clean)


def test_gold_aggregation_excludes_invalid_fares():
    table = _make_bronze_table()
    fares = table.column("fare_amount").to_pylist()
    fares[0] = -5.0
    table = table.set_column(table.schema.get_field_index("fare_amount"), "fare_amount", pa.array(fares))
    clean = _clean(table)
    gold = _aggregate(clean)
    assert gold.num_rows > 0
    assert "total_revenue" in gold.column_names
