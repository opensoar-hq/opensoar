#!/usr/bin/env bash
# Helm chart validation tests for the OpenSOAR chart.
#
# Runs `helm lint` plus a series of `helm template` assertions to confirm that
# the chart renders the expected Kubernetes manifests with and without the
# optional postgres/redis subcharts, with ingress toggled on/off, with AI
# provider secrets, and with alternative image tags.
#
# Usage: bash scripts/test-helm.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CHART_DIR="$REPO_ROOT/helm/opensoar"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  ok  $*"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL $*" >&2; }

assert_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if grep -qE "$pattern" "$file"; then
    pass "$label"
  else
    fail "$label (pattern not found: $pattern)"
  fi
}

assert_not_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if grep -qE "$pattern" "$file"; then
    fail "$label (pattern unexpectedly present: $pattern)"
  else
    pass "$label"
  fi
}

section() {
  echo
  echo "== $* =="
}

section "helm lint"
helm lint "$CHART_DIR"
pass "chart lints clean"

section "default render"
DEFAULT="$TMPDIR/default.yaml"
helm template opensoar "$CHART_DIR" > "$DEFAULT"
assert_contains "$DEFAULT" 'kind: Deployment' "renders Deployment resources"
assert_contains "$DEFAULT" 'kind: Service' "renders Service resources"
assert_contains "$DEFAULT" 'kind: Job' "renders migrate Job"
assert_contains "$DEFAULT" 'helm.sh/hook.*pre-install,pre-upgrade' "migrate Job uses pre-install/pre-upgrade hook"
assert_contains "$DEFAULT" 'app.kubernetes.io/component: api' "api component labeled"
assert_contains "$DEFAULT" 'app.kubernetes.io/component: worker' "worker component labeled"
assert_contains "$DEFAULT" 'app.kubernetes.io/component: ui' "ui component labeled"
assert_contains "$DEFAULT" 'app.kubernetes.io/component: migrate' "migrate component labeled"
assert_contains "$DEFAULT" 'name: JWT_SECRET' "api env includes JWT_SECRET"
assert_contains "$DEFAULT" 'name: API_KEY_SECRET' "api env includes API_KEY_SECRET"
assert_contains "$DEFAULT" 'name: DATABASE_URL' "api env includes DATABASE_URL"
assert_contains "$DEFAULT" 'name: REDIS_URL' "api env includes REDIS_URL"
assert_contains "$DEFAULT" 'name: PLAYBOOK_DIRS' "api env includes PLAYBOOK_DIRS"
assert_contains "$DEFAULT" 'name: ANTHROPIC_API_KEY' "api env includes ANTHROPIC_API_KEY"
assert_contains "$DEFAULT" 'name: OPENAI_API_KEY' "api env includes OPENAI_API_KEY"
assert_contains "$DEFAULT" 'name: OLLAMA_URL' "api env includes OLLAMA_URL"
# Postgres + Redis subcharts default to enabled.
assert_contains "$DEFAULT" 'name: postgres' "postgres rendered when enabled"
assert_contains "$DEFAULT" 'name: redis' "redis rendered when enabled"
# Ingress defaults to disabled.
assert_not_contains "$DEFAULT" 'kind: Ingress' "ingress disabled by default"

section "pre-install hook ordering"
# Secret must install before the migrate Job so the Job's secretKeyRefs resolve.
if grep -F '"helm.sh/hook-weight": "-10"' "$DEFAULT" > /dev/null; then
  pass "secret annotated as pre-install hook with weight -10"
else
  fail "secret missing pre-install hook annotation"
fi
# Postgres (Service + StatefulSet) must install before the migrate Job.
if [ "$(grep -cF '"helm.sh/hook-weight": "-5"' "$DEFAULT")" -ge 2 ]; then
  pass "postgres Service + StatefulSet annotated as pre-install hooks with weight -5"
else
  fail "postgres missing pre-install hook annotations"
fi
# Migrate Job runs last in the hook chain.
if grep -F '"helm.sh/hook-weight": "10"' "$DEFAULT" > /dev/null; then
  pass "migrate Job annotated with positive hook weight"
else
  fail "migrate Job missing positive hook weight"
fi
# Migrate Job has a wait-for-postgres initContainer so pre-install tolerates
# a subchart Postgres that is still coming up.
if grep -q 'name: wait-for-postgres' "$DEFAULT"; then
  pass "migrate Job waits for postgres via initContainer"
else
  fail "migrate Job missing wait-for-postgres initContainer"
fi

section "subcharts disabled"
EXTERN="$TMPDIR/external.yaml"
helm template opensoar "$CHART_DIR" \
  --set postgres.enabled=false \
  --set redis.enabled=false \
  > "$EXTERN"
assert_not_contains "$EXTERN" 'kind: StatefulSet' "postgres StatefulSet omitted when disabled"
assert_not_contains "$EXTERN" 'app.kubernetes.io/component: postgres' "postgres labels omitted when disabled"
assert_not_contains "$EXTERN" 'app.kubernetes.io/component: redis' "redis labels omitted when disabled"
# Core app resources still render.
assert_contains "$EXTERN" 'app.kubernetes.io/component: api' "api still rendered when subcharts disabled"
assert_contains "$EXTERN" 'app.kubernetes.io/component: worker' "worker still rendered when subcharts disabled"

section "ingress enabled + host override"
INGRESS="$TMPDIR/ingress.yaml"
helm template opensoar "$CHART_DIR" \
  --set ui.ingress.enabled=true \
  --set ui.ingress.host=soar.example.com \
  --set ui.ingress.className=nginx \
  > "$INGRESS"
assert_contains "$INGRESS" 'kind: Ingress' "ingress rendered when enabled"
assert_contains "$INGRESS" 'host: soar.example.com' "ingress host override honoured"
assert_contains "$INGRESS" 'ingressClassName: nginx' "ingress className override honoured"

section "image tag override"
IMAGES="$TMPDIR/images.yaml"
helm template opensoar "$CHART_DIR" \
  --set images.api.tag=v9.9.9 \
  --set images.worker.tag=v9.9.9 \
  --set images.migrate.tag=v9.9.9 \
  --set images.ui.tag=v9.9.9 \
  > "$IMAGES"
assert_contains "$IMAGES" 'opensoar-core-api:v9.9.9' "api image tag override honoured"
assert_contains "$IMAGES" 'opensoar-core-worker:v9.9.9' "worker image tag override honoured"
assert_contains "$IMAGES" 'opensoar-core-migrate:v9.9.9' "migrate image tag override honoured"
assert_contains "$IMAGES" 'opensoar-core-ui:v9.9.9' "ui image tag override honoured"

section "AI provider secrets populated"
AI="$TMPDIR/ai.yaml"
helm template opensoar "$CHART_DIR" \
  --set secrets.anthropicApiKey=sk-ant-test \
  --set secrets.openaiApiKey=sk-openai-test \
  --set secrets.ollamaUrl=http://ollama:11434 \
  > "$AI"
assert_contains "$AI" 'anthropic-api-key' "secret stores anthropic key"
assert_contains "$AI" 'openai-api-key' "secret stores openai key"
assert_contains "$AI" 'ollama-url' "secret stores ollama url"

section "summary"
echo "Passed: $PASS"
echo "Failed: $FAIL"
if [ "$FAIL" -ne 0 ]; then
  exit 1
fi
