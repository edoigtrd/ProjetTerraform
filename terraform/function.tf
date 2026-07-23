locals {
  function_dir = "${path.module}/../code/function/function"
}

data "archive_file" "function" {
  type        = "zip"
  source_dir  = local.function_dir
  output_path = "${path.module}/function.zip"
  excludes    = ["__pycache__"]
}

resource "scaleway_function_namespace" "hello_world" {
  name        = "function-namespace"
  description = "Namespace for the function"
}

resource "scaleway_function" "hello_world" {
  namespace_id = scaleway_function_namespace.hello_world.id
  name         = "function"
  runtime      = "python312"
  handler      = "handler.handle"
  privacy      = "public"
  min_scale    = 0
  max_scale    = 1
  memory_limit = 128
  timeout      = 10

  zip_file = data.archive_file.function.output_path
  zip_hash = data.archive_file.function.output_sha256
  deploy   = true
}
