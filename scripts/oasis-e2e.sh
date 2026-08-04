#!/bin/sh
set -eu

COMPOSE_FILES="-f compose.yaml -f compose.full.yaml"
BASE_URL=${BASE_URL:-http://127.0.0.1:5173}
KEEP_STACK=${KEEP_STACK:-false}
RESULT_FILE=${OASIS_E2E_RESULT_FILE:-/tmp/rekakebijakan-oasis-e2e-result.json}

if ! docker compose $COMPOSE_FILES config --format json | python3 -c '
import json, sys
environment = json.load(sys.stdin)["services"]["worker"]["environment"]
raise SystemExit(0 if environment.get("LLM_API_KEY") and environment.get("ZEP_API_KEY") else 1)
'; then
  printf '%s\n' "oasis-e2e: LLM_API_KEY and ZEP_API_KEY are required" >&2
  exit 2
fi

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    docker compose $COMPOSE_FILES logs --no-color backend worker >&2 || true
  fi
  if [ "$KEEP_STACK" != true ]; then
    docker compose $COMPOSE_FILES down >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

rm -f "$RESULT_FILE"

OASIS_ENABLED=true DEFAULT_SIMULATION_ENGINE=oasis \
  docker compose $COMPOSE_FILES up --build --detach --wait

RUN_OASIS_E2E=true \
PLAYWRIGHT_BASE_URL="$BASE_URL" \
PLAYWRIGHT_SKIP_WEBSERVER=1 \
OASIS_E2E_RESULT_FILE="$RESULT_FILE" \
  npm --prefix frontend run test:e2e:oasis

if [ ! -s "$RESULT_FILE" ]; then
  printf '%s\n' "oasis-e2e: Playwright did not write a result file" >&2
  exit 1
fi

SIMULATION_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["simulationId"])' "$RESULT_FILE")
case "$SIMULATION_ID" in
  sim_[a-zA-Z0-9]*) ;;
  *) printf '%s\n' "oasis-e2e: invalid simulation ID in result file" >&2; exit 1 ;;
esac
docker compose $COMPOSE_FILES exec -T database \
  psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-rekakebijakan}" -d "${POSTGRES_DB:-rekakebijakan}" \
  -c "SELECT 1 / CASE WHEN count(*) > 0 AND count(DISTINCT platform) = 2 THEN 1 ELSE 0 END AS raw_actions_valid FROM oasis_actions WHERE simulation_id = '$SIMULATION_ID' AND raw_action IS NOT NULL;"

printf '%s\n' "oasis-e2e: steps 1-5 and raw action persistence passed ($SIMULATION_ID)"
