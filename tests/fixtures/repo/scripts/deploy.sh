#!/usr/bin/env bash
set -Eeuo pipefail

# shellcheck should flag the unquoted variable below (SC2086).
namespace=$1
kubectl get pods -n $namespace
