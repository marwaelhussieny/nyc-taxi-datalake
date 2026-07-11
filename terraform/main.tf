terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --- S3 bucket holding all three medallion layers as prefixes:
#     s3://<bucket>/bronze/, s3://<bucket>/silver/, s3://<bucket>/gold/
resource "aws_s3_bucket" "lake" {
  bucket = var.bucket_name

  tags = {
    Project     = "nyc-taxi-datalake"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration {
    status = "Disabled" # keep it simple/cheap for a portfolio project
  }
}

resource "aws_s3_bucket_public_access_block" "lake" {
  bucket                  = aws_s3_bucket.lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- Glue Data Catalog database acting as the Iceberg REST/Hive-compatible catalog
resource "aws_glue_catalog_database" "lakehouse" {
  name = var.glue_database_name

  description = "Iceberg catalog for the NYC taxi medallion lakehouse (bronze/silver/gold)"
}

# --- IAM user for programmatic access (PyIceberg/Trino need S3 + Glue permissions)
resource "aws_iam_policy" "lake_access" {
  name        = "nyc-taxi-lakehouse-access"
  description = "Read/write access to the taxi data lake bucket and its Glue catalog"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3BucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.lake.arn,
          "${aws_s3_bucket.lake.arn}/*"
        ]
      },
      {
        Sid    = "GlueCatalogAccess"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:DeleteTable",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartitions",
          "glue:BatchCreatePartition"
        ]
        Resource = [
          "arn:aws:glue:${var.aws_region}:*:catalog",
          "arn:aws:glue:${var.aws_region}:*:database/${var.glue_database_name}",
          "arn:aws:glue:${var.aws_region}:*:table/${var.glue_database_name}/*"
        ]
      }
    ]
  })
}
