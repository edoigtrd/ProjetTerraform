#!/usr/bin/env bash
# Generic build/package script for a Scaleway Serverless Function (Python runtime).
#
# Layout expected next to this script:
#   function/
#     handler.py
#     requirements.txt
#
# Usage:
#   ./package.sh                builds ./function.zip
#   ./package.sh --deploy       builds, then runs `scw function deploy`
#                                (requires FUNCTION_NAME and NAMESPACE_ID)
#
#   FUNCTION_NAME=my-func NAMESPACE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
#     ./package.sh --deploy
set -euo pipefail

DEPLOY=false
if [[ "${1:-}" == "--deploy" ]]; then
  DEPLOY=true
fi

PYTHON_VERSION="${PYTHON_VERSION:-3.11}"   # match your function's runtime
IMAGE="rg.fr-par.scw.cloud/scwfunctionsruntimes-public/python-dep:${PYTHON_VERSION}"

cd function

# Dependencies are installed into their own subfolder so cleanup between
# rebuilds never touches source files. Remove it via a throwaway root
# container rather than `rm -rf` on the host: the build image writes as
# root, and some manylinux wheels ship read-only directories that a
# non-root/non-owner `rm` can't touch either.
docker run --rm \
  -v "$(pwd)":/home/app/function \
  --workdir /home/app/function \
  "$IMAGE" \
  rm -rf package

docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$(pwd)":/home/app/function \
  --workdir /home/app/function \
  "$IMAGE" \
  pip3 install --upgrade -r requirements.txt --no-cache-dir --target ./package

rm -f ../function.zip
zip ../function.zip handler.py http_event.py requirements.txt
(cd package && zip -r ../../function.zip . -x '__pycache__/*' -x '*.dist-info/*')

cd ..

if $DEPLOY; then
  : "${FUNCTION_NAME:?Set FUNCTION_NAME to deploy, e.g. FUNCTION_NAME=my-func ./package.sh --deploy}"
  : "${NAMESPACE_ID:?Set NAMESPACE_ID to deploy, e.g. NAMESPACE_ID=xxxx ./package.sh --deploy}"

  scw function deploy \
    name="$FUNCTION_NAME" \
    namespace-id="$NAMESPACE_ID" \
    runtime="python${PYTHON_VERSION//./}" \
    zip-file=./function.zip
fi
