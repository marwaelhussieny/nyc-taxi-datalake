"""
Shared PyIceberg catalog connection, used by all three medallion layers.

Uses AWS Glue Data Catalog as the Iceberg catalog (no separate metastore to
run) and S3 as the underlying storage. Credentials come from the standard
AWS credential chain (aws configure / environment variables) - never
hardcoded here.
"""
from __future__ import annotations

import os

from pyiceberg.catalog import load_catalog
from pyiceberg.catalog.glue import GlueCatalog

GLUE_DATABASE = os.environ.get("GLUE_DATABASE_NAME", "nyc_taxi_lakehouse")
BUCKET = os.environ.get("LAKE_BUCKET_NAME")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def get_catalog() -> GlueCatalog:
    if not BUCKET:
        raise RuntimeError(
            "LAKE_BUCKET_NAME environment variable is not set. "
            "Set it to the bucket name from 'terraform output bucket_name'."
        )
    return load_catalog(
        "glue",
        **{
            "type": "glue",
            "client.region": AWS_REGION,
        },
    )


def table_location(layer: str, table_name: str) -> str:
    """s3 path for a given medallion layer, e.g. table_location('bronze', 'yellow_trips')"""
    return f"s3://{BUCKET}/{layer}/{table_name}"
