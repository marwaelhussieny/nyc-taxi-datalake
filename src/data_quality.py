"""
Data quality gate, run after the silver transform and before gold aggregation.
Same fail-loud, named-check pattern as the real estate project - a list of
independent checks, each producing pass/fail with a specific reason.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pyarrow as pa
import pyarrow.compute as pc

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


class DataQualityError(Exception):
    pass


def _check_row_count(table: pa.Table, minimum: int = 1000) -> CheckResult:
    passed = table.num_rows >= minimum
    return CheckResult("row_count_minimum", passed, f"expected >= {minimum}, got {table.num_rows}")


def _check_no_negative_duration(table: pa.Table) -> CheckResult:
    negative = pc.sum(pc.less(table["trip_duration_minutes"], 0)).as_py() or 0
    return CheckResult("no_negative_duration", negative == 0, f"{negative} rows with negative duration")


def _check_pickup_location_not_null(table: pa.Table) -> CheckResult:
    nulls = table["pulocationid"].null_count
    return CheckResult("pickup_location_not_null", nulls == 0, f"{nulls} rows with null pickup location")


def _check_duration_under_24h(table: pa.Table) -> CheckResult:
    over = pc.sum(pc.greater(table["trip_duration_minutes"], 24 * 60)).as_py() or 0
    return CheckResult("duration_under_24h", over == 0, f"{over} rows exceeding 24h trip duration")


CHECKS = [
    _check_row_count,
    _check_no_negative_duration,
    _check_pickup_location_not_null,
    _check_duration_under_24h,
]


def run_data_quality_checks(table: pa.Table) -> list[CheckResult]:
    results = [check(table) for check in CHECKS]
    for r in results:
        level = logging.INFO if r.passed else logging.ERROR
        logger.log(level, "[%s] %s - %s", "PASS" if r.passed else "FAIL", r.name, r.detail)

    failed = [r for r in results if not r.passed]
    if failed:
        raise DataQualityError(f"Failed checks: {', '.join(r.name for r in failed)}")
    return results
