output "bucket_name" {
  value = aws_s3_bucket.lake.id
}

output "bronze_path" {
  value = "s3://${aws_s3_bucket.lake.id}/bronze/"
}

output "silver_path" {
  value = "s3://${aws_s3_bucket.lake.id}/silver/"
}

output "gold_path" {
  value = "s3://${aws_s3_bucket.lake.id}/gold/"
}

output "glue_database_name" {
  value = aws_glue_catalog_database.lakehouse.name
}

output "least_privilege_policy_arn" {
  description = "Optional: attach this to a scoped-down IAM user instead of using AdministratorAccess"
  value       = aws_iam_policy.lake_access.arn
}
