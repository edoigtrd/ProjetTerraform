terraform {
  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = ">= 2.43.0"
    }
    null = {
      source  = "hashicorp/null"
      version = ">= 3.0.0"
    }
  }
}

provider "scaleway" {
  region     = "fr-par"
  project_id = var.project_id
}

resource "scaleway_sdb_sql_database" "main" {
  name    = "my-serverless-db"
  min_cpu = 0
  max_cpu = 8
}

resource "scaleway_iam_application" "db_app" {
  name = "my-serverless-db-app"
}

resource "scaleway_iam_policy" "db_policy" {
  name           = "my-serverless-db-policy"
  application_id = scaleway_iam_application.db_app.id

  rule {
    project_ids          = [scaleway_sdb_sql_database.main.project_id]
    permission_set_names = ["ServerlessSQLDatabaseReadWrite"]
  }
}

resource "scaleway_iam_api_key" "db_key" {
  application_id = scaleway_iam_application.db_app.id
}

locals {
  database_url = "postgres://${scaleway_iam_api_key.db_key.access_key}:${scaleway_iam_api_key.db_key.secret_key}@${replace(scaleway_sdb_sql_database.main.endpoint, "postgres://", "")}"
}

