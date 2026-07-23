locals {
  function_dir       = "${path.module}/../code/function/function"
  function_build_dir = "${path.module}/../code/function/build"

  # Rebuild the vendored dependencies whenever the function's source changes.
  function_hash = sha256(join("", [
    for f in sort(fileset(local.function_dir, "**")) : filesha256("${local.function_dir}/${f}")
  ]))
}

# The function needs psycopg2-binary (a compiled C extension), so its
# dependencies must be installed against the same runtime image Scaleway
# will execute the function in, then bundled alongside the source - the
# zip can't just be the source_dir as-is.
resource "null_resource" "function_deps" {
  triggers = {
    hash = local.function_hash
  }

  provisioner "local-exec" {
    environment = {
      SOURCE_DIR = local.function_dir
      BUILD_DIR  = local.function_build_dir
    }
    command = <<-EOT
      set -e
      rm -rf "$BUILD_DIR"
      mkdir -p "$BUILD_DIR"
      cp "$SOURCE_DIR"/*.py "$SOURCE_DIR"/requirements.txt "$BUILD_DIR"/

      docker run --rm \
        --user "$(id -u):$(id -g)" \
        -v "$BUILD_DIR":/home/app/function \
        --workdir /home/app/function \
        rg.fr-par.scw.cloud/scwfunctionsruntimes-public/python-dep:3.12 \
        pip3 install --upgrade -r requirements.txt --no-cache-dir --target .
    EOT
  }
}

data "archive_file" "function" {
  type        = "zip"
  source_dir  = local.function_build_dir
  output_path = "${path.module}/function.zip"
  excludes    = ["__pycache__"]

  depends_on = [null_resource.function_deps]
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
  memory_limit = 256
  timeout      = 10

  secret_environment_variables = {
    DATABASE_URL = local.database_url
  }

  zip_file = data.archive_file.function.output_path
  zip_hash = data.archive_file.function.output_sha256
  deploy   = true
}
