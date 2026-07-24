#!/bin/sh
set -eu

BASE_URL=${BASE_URL:-http://localhost:5173}
CURL_CONNECT_TIMEOUT=${CURL_CONNECT_TIMEOUT:-5}
CURL_MAX_TIME=${CURL_MAX_TIME:-20}
POLL_TIMEOUT=${POLL_TIMEOUT:-120}
POLL_INTERVAL=${POLL_INTERVAL:-2}
COOKIE_JAR=$(mktemp)
SOURCE_FILE=$(mktemp)
EMAIL="smoke-$(date +%s)-$$@example.test"
PASSWORD="smoke-password-$$"
PROJECT_ID=""
SIMULATION_ID=""

cleanup() {
  if [ -n "$PROJECT_ID" ]; then
    request -X DELETE "$BASE_URL/backend/api/v1/projects/$PROJECT_ID" >/dev/null 2>&1 || true
  fi
  request -X POST "$BASE_URL/backend/api/auth/logout" >/dev/null 2>&1 || true
  rm -f "$COOKIE_JAR" "$SOURCE_FILE"
}
trap cleanup EXIT INT TERM

request() {
  curl --fail-with-body --silent --show-error \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" --max-time "$CURL_MAX_TIME" \
    --cookie "$COOKIE_JAR" --cookie-jar "$COOKIE_JAR" "$@"
}

json_value() {
  python3 -c 'import json,sys; value=json.load(sys.stdin); print(value'"$1"')'
}

poll_stage() {
  stage=$1
  deadline=$(( $(date +%s) + POLL_TIMEOUT ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    snapshot=$(request "$BASE_URL/backend/api/simulations/$SIMULATION_ID")
    status=$(printf '%s' "$snapshot" | json_value "['stages']['$stage']['status']")
    case "$status" in
      completed) return 0 ;;
      failed|cancelled) printf '%s\n' "smoke: $stage ended with $status" >&2; return 1 ;;
    esac
    sleep "$POLL_INTERVAL"
  done
  printf '%s\n' "smoke: $stage timed out after ${POLL_TIMEOUT}s" >&2
  return 1
}

request "$BASE_URL/" | python3 -c 'import sys; assert "<html" in sys.stdin.read().lower()'
request "$BASE_URL/backend/health" | python3 -c 'import json,sys; assert json.load(sys.stdin)["status"] == "ok"'

request -H 'Content-Type: application/json' -d "{\"name\":\"Production Smoke\",\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  "$BASE_URL/backend/api/auth/register" >/dev/null
request -X POST "$BASE_URL/backend/api/auth/logout" >/dev/null
request -H 'Content-Type: application/json' -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  "$BASE_URL/backend/api/auth/login" >/dev/null
request "$BASE_URL/backend/api/auth/me" | python3 -c 'import json,sys; assert json.load(sys.stdin)["user"]["email"] == sys.argv[1]' "$EMAIL"

printf '%s\n' 'Akses layanan harus adil. Tarif terjangkau dievaluasi setiap bulan.' > "$SOURCE_FILE"
created=$(request -F 'project_name=Production Smoke' -F 'institution=CI' -F 'objective=Validate grounded policy workflow' \
  -F "files=@$SOURCE_FILE;filename=smoke.md;type=text/markdown" "$BASE_URL/backend/api/projects")
PROJECT_ID=$(printf '%s' "$created" | json_value "['id']")
SIMULATION_ID=$(printf '%s' "$created" | json_value "['simulation_id']")

for stage in graph environment simulation report; do
  payload='{}'
  [ "$stage" = environment ] && payload='{"rounds":3}'
  request -H 'Content-Type: application/json' -d "$payload" \
    "$BASE_URL/backend/api/simulations/$SIMULATION_ID/stages/$stage/start" >/dev/null
  poll_stage "$stage"
done

report=$(request "$BASE_URL/backend/api/reports/$SIMULATION_ID")
citations=$(request "$BASE_URL/backend/api/simulations/$SIMULATION_ID/citations")
printf '%s\n%s\n' "$report" "$citations" | python3 -c '
import json, sys
report, citation_response = [json.loads(line) for line in sys.stdin]
known = {
    value
    for item in citation_response["citations"]
    for value in (item.get("source_id"), item.get("chunk_id"))
    if value
}
sections = report.get("sections", [])
assert sections, "report has no sections"
refs = [citation for section in sections for citation in section.get("citations", [])]
assert refs, "report has no citations"
assert all((citation.get("source_id") or citation.get("chunk_id")) in known for citation in refs), "invalid report citation"
'

printf '%s\n' "smoke: full-stack workflow passed ($SIMULATION_ID)"
