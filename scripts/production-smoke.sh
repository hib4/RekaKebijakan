#!/bin/sh
set -eu

BASE_URL=${BASE_URL:-http://localhost:5173}
CURL_CONNECT_TIMEOUT=${CURL_CONNECT_TIMEOUT:-5}
CURL_MAX_TIME=${CURL_MAX_TIME:-20}
POLL_TIMEOUT=${POLL_TIMEOUT:-120}
POLL_INTERVAL=${POLL_INTERVAL:-2}
SIMULATION_ENGINE=${SIMULATION_ENGINE:-deterministic}
MAX_PROFILE_COUNT=${MAX_PROFILE_COUNT:-5}
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

start_stage() {
  stage=$1
  payload=$2
  snapshot=$(request "$BASE_URL/backend/api/simulations/$SIMULATION_ID")
  status=$(printf '%s' "$snapshot" | json_value "['stages']['$stage']['status']")
  case "$status" in
    completed) return 0 ;;
    queued|processing|running) ;;
    ready)
      request -H 'Content-Type: application/json' -d "$payload" \
        "$BASE_URL/backend/api/simulations/$SIMULATION_ID/stages/$stage/start" >/dev/null
      ;;
    *) printf '%s\n' "smoke: $stage cannot start from $status" >&2; return 1 ;;
  esac
  poll_stage "$stage"
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

start_stage graph '{}'
start_stage environment "{\"rounds\":3,\"engine\":\"$SIMULATION_ENGINE\",\"max_rounds\":3,\"max_profile_count\":$MAX_PROFILE_COUNT,\"parallel_profile_count\":3,\"use_llm_for_profiles\":false}"
start_stage simulation "{\"engine\":\"$SIMULATION_ENGINE\",\"max_rounds\":3,\"enable_graph_memory_update\":true}"
start_stage report '{}'

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

answer=$(request -H 'Content-Type: application/json' \
  -d '{"tool":"report","question":"Apa risiko utama kebijakan ini dan tindakan mitigasi yang didukung oleh bukti?"}' \
  "$BASE_URL/backend/api/simulations/$SIMULATION_ID/interactions")
messages=$(request "$BASE_URL/backend/api/interactions/$SIMULATION_ID/messages")
printf '%s\n%s\n' "$answer" "$messages" | python3 -c '
import json, sys
answer, history = [json.loads(line) for line in sys.stdin]
assert answer["role"] == "assistant"
assert answer["tool"] == "report"
assert answer["text"].strip(), "interaction returned an empty answer"
messages = history["messages"]
assert len(messages) >= 2
assert messages[-2]["role"] == "user"
assert messages[-1]["id"] == answer["id"]
'

if [ "$SIMULATION_ENGINE" = oasis ]; then
  environment=$(request "$BASE_URL/backend/api/simulations/$SIMULATION_ID/environment")
  oasis_status=$(request "$BASE_URL/backend/api/simulations/$SIMULATION_ID/oasis/status")
  runtime_graph=$(request "$BASE_URL/backend/api/simulations/$SIMULATION_ID/runtime-graph")
  events=$(request "$BASE_URL/backend/api/runs/$SIMULATION_ID/events")
  printf '%s\n%s\n%s\n%s\n%s\n' "$environment" "$oasis_status" "$runtime_graph" "$events" "$report" | python3 -c '
import json, sys
environment, status, graph, events, report = [json.loads(line) for line in sys.stdin]
config = environment["config"]
assert config["engine"] == "oasis"
assert config["generated_by"] == "oasis-direct"
assert 0 < environment["persona_count"] <= int(sys.argv[1])
assert all(persona["id"].startswith("oasis-") for persona in environment["personas"])
assert status["enabled"] is True
assert status["mapping_status"] == "completed"
assert status["zep_graph_id"] and status["external_simulation_id"]
runtime = status["runtime"]
assert runtime["runner_status"] == "completed"
assert runtime["twitter_completed"] is True
assert runtime["reddit_completed"] is True
assert status["total_actions"] > 0
assert {"twitter", "reddit"}.issubset(status["platform_counts"])
assert graph["available"] is True
assert graph["graph_id"] == status["zep_graph_id"]
assert events["event_count"] > 0
assert all(event["id"].startswith("oasis-event-") for event in events["events"])
assert all(event["persona_id"].startswith("oasis-") for event in events["events"])
assert report["generated_by"] == "rekakebijakan-oasis-report-agent"
' "$MAX_PROFILE_COUNT"
fi

printf '%s\n' "smoke: full-stack workflow including interaction passed ($SIMULATION_ID, $SIMULATION_ENGINE)"
