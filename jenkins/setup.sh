#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p .secrets
for name in admin-password webhook-secret; do
  if [ ! -s ".secrets/$name" ]; then
    openssl rand -hex 32 > ".secrets/$name"
  fi
done
docker compose up -d --build
echo 'Jenkins: http://localhost:8080/job/jenkinsJob/'
echo 'Username: admin; password is in .secrets/admin-password'
