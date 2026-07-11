content = open('README.md', encoding='utf-8').read()
section = """## Evidence

Screenshots proving this runs against real, live infrastructure with real NYC TLC data (3M+ trip records), not just written but never executed:

| | |
|---|---|
| ![Terraform apply](docs/screenshots/01-terraform-apply-success.png) | terraform apply provisioning the S3 bucket and Glue database |
| ![S3 bucket](docs/screenshots/02-s3-bucket-medallion-layers.png) | Bronze/silver/gold prefixes in the real S3 bucket |
| ![Glue Data Catalog](docs/screenshots/03-glue-data-catalog.png) | All 3 Iceberg tables registered in AWS Glue |
| ![Pipeline run and tests](docs/screenshots/04-pipeline-run-and-tests.png) | Full bronze/silver/gold run (3,066,766 rows ingested, cleaned to 3,065,620, aggregated to 6,813 zone-day rows) plus the full pytest suite passing |
| ![Dagster loaded](docs/screenshots/05-dagster-code-location-loaded.png) | Dagster successfully loading the asset definitions |
| ![Dagster asset graph](docs/screenshots/06-dagster-asset-graph.png) | bronze to silver to gold pipeline in Dagster, with monthly schedule |
| ![Trino query results](docs/screenshots/07-trino-query-results.png) | Real SQL query against the gold layer via Trino |

"""
content = content.replace("## Dataset", section + "## Dataset")
open('README.md', 'w', encoding='utf-8').write(content)
print("README updated successfully")