variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "S3 bucket name for the data lake (must be globally unique - include your name/initials)"
  type        = string
}

variable "glue_database_name" {
  description = "Glue Data Catalog database name for the Iceberg tables"
  type        = string
  default     = "nyc_taxi_lakehouse"
}

variable "environment" {
  description = "Environment tag"
  type        = string
  default     = "portfolio"
}
