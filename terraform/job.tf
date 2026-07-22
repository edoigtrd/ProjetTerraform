locals {
  load_data_dir   = "${path.module}/../code/load_data"
  load_data_repo  = "${scaleway_registry_namespace.main.endpoint}/load-data"
  load_data_tag   = "latest"
  load_data_image = "${local.load_data_repo}:${local.load_data_tag}"

  # Rebuild/push the image whenever any file in code/load_data changes.
  load_data_hash = sha256(join("", [
    for f in sort(fileset(local.load_data_dir, "**")) : filesha256("${local.load_data_dir}/${f}")
  ]))
}

resource "null_resource" "load_data_image" {
  triggers = {
    hash = local.load_data_hash
  }

  provisioner "local-exec" {
    environment = {
      REGISTRY_PASSWORD = scaleway_iam_api_key.registry_key.secret_key
      REGISTRY_ENDPOINT = scaleway_registry_namespace.main.endpoint
      IMAGE_TAG         = local.load_data_image
      BUILD_DIR         = local.load_data_dir
    }
    command = <<-EOT
      set -e
      echo "$REGISTRY_PASSWORD" | docker login "$${REGISTRY_ENDPOINT%%/*}" -u nologin --password-stdin
      docker build -t "$IMAGE_TAG" "$BUILD_DIR"
      docker push "$IMAGE_TAG"
    EOT
  }

  depends_on = [scaleway_registry_namespace.main, scaleway_iam_api_key.registry_key]
}

resource "scaleway_job_definition" "load_data" {
  name                   = "load-data"
  cpu_limit              = 500
  memory_limit           = 512
  local_storage_capacity = 1000
  image_uri              = local.load_data_image
  timeout                = "10m"

  env = {
    BSKY_APP_NAME       = var.bsky_app_name
    OPENAI_API_ENDPOINT = var.openai_api_endpoint
  }

  secret_reference {
    secret_id   = scaleway_secret.bsky_app_password.id
    environment = "BSKY_APP_PASSWORD"
  }

  secret_reference {
    secret_id   = scaleway_secret.openai_api_key.id
    environment = "OPENAI_API_KEY"
  }

  secret_reference {
    secret_id   = scaleway_secret.database_url.id
    environment = "DATABASE_URL"
  }

  cron {
    schedule = "0 * * * *"
    timezone = "UTC"
  }

  depends_on = [null_resource.load_data_image]
}
