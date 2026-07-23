locals {
  dashboard_dir   = "${path.module}/../code/dashboard"
  dashboard_repo  = "${scaleway_registry_namespace.main.endpoint}/dashboard"
  dashboard_tag   = "latest"
  dashboard_image = "${local.dashboard_repo}:${local.dashboard_tag}"

  # Rebuild/push the image whenever any file in code/dashboard changes.
  dashboard_hash = sha256(join("", [
    for f in sort(fileset(local.dashboard_dir, "**")) : filesha256("${local.dashboard_dir}/${f}")
  ]))
}

resource "null_resource" "dashboard_image" {
  triggers = {
    hash = local.dashboard_hash
  }

  provisioner "local-exec" {
    environment = {
      REGISTRY_PASSWORD = scaleway_iam_api_key.registry_key.secret_key
      REGISTRY_ENDPOINT = scaleway_registry_namespace.main.endpoint
      IMAGE_TAG         = local.dashboard_image
      BUILD_DIR         = local.dashboard_dir
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

resource "scaleway_container_namespace" "dashboard" {
  name        = "dashboard-namespace"
  description = "Namespace for the Streamlit dashboard"
}

resource "scaleway_container" "dashboard" {
  namespace_id       = scaleway_container_namespace.dashboard.id
  name               = "dashboard"
  image              = local.dashboard_image
  registry_sha256    = local.dashboard_hash
  port               = 8080
  cpu_limit          = 280
  memory_limit_bytes = 536870912 # 512 MiB
  min_scale          = 0
  max_scale          = 1
  privacy            = "public"

  environment_variables = {
    FUNCTION_URL = "https://${scaleway_function.hello_world.domain_name}"
  }

  depends_on = [null_resource.dashboard_image]
}
