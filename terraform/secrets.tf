resource "scaleway_secret" "bsky_app_password" {
  name = "load-data-bsky-app-password"
}

resource "scaleway_secret_version" "bsky_app_password" {
  secret_id = scaleway_secret.bsky_app_password.id
  data      = var.bsky_app_password
}

resource "scaleway_secret" "openai_api_key" {
  name = "load-data-openai-api-key"
}

resource "scaleway_secret_version" "openai_api_key" {
  secret_id = scaleway_secret.openai_api_key.id
  data      = var.openai_api_key
}

resource "scaleway_secret" "database_url" {
  name = "load-data-database-url"
}

resource "scaleway_secret_version" "database_url" {
  secret_id = scaleway_secret.database_url.id
  data      = local.database_url
}
