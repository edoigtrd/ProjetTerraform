resource "scaleway_registry_namespace" "main" {
  name        = "load-data-registry"
  description = "Container registry for the load_data job image"
  is_public   = false
}

resource "scaleway_iam_application" "registry_app" {
  name = "load-data-registry-app"
}

resource "scaleway_iam_policy" "registry_policy" {
  name           = "load-data-registry-policy"
  application_id = scaleway_iam_application.registry_app.id

  rule {
    project_ids          = [var.project_id]
    permission_set_names = ["ContainerRegistryFullAccess"]
  }
}

resource "scaleway_iam_api_key" "registry_key" {
  application_id = scaleway_iam_application.registry_app.id
}
