#!/usr/bin/env bash
# Build the API and web images, load them into kind, and exercise ingest + ask.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLUSTER="${KIND_CLUSTER:-agentops}"
API_PORT="${API_PORT:-18000}"
WEB_PORT="${WEB_PORT:-13000}"

cleanup() {
  if [[ -n "${API_PF:-}" ]]; then kill "$API_PF" 2>/dev/null || true; fi
  if [[ -n "${WEB_PF:-}" ]]; then kill "$WEB_PF" 2>/dev/null || true; fi
  kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true
kind create cluster --name "$CLUSTER"

docker build -t agentops-mcp:local "$ROOT"
docker build -t agentops-web:local "$ROOT/web"
for image in redis:7-alpine mongo:7 rabbitmq:3-alpine agentops-mcp:local agentops-web:local; do
  if [[ "$image" != *":local" ]]; then
    docker pull "$image"
  fi
  kind load docker-image "$image" --name "$CLUSTER"
done

kubectl apply -k "$ROOT/k8s"

dump_cluster() {
  kubectl -n agentops get pods -o wide >&2 || true
  kubectl -n agentops logs deploy/api --tail=80 >&2 || true
  kubectl -n agentops describe pods >&2 || true
  kubectl -n agentops get events --sort-by=.lastTimestamp >&2 || true
}

rollout() {
  local name="$1"
  local timeout="$2"
  if ! kubectl -n agentops rollout status "deploy/$name" --timeout="$timeout"; then
    echo "rollout failed: $name" >&2
    dump_cluster
    return 1
  fi
}

rollout redis 300s
rollout mongo 300s
rollout rabbitmq 300s
rollout api 300s
rollout worker 300s
rollout web 300s

kubectl -n agentops port-forward svc/api "$API_PORT:8000" >/tmp/kind-api-pf.log 2>&1 &
API_PF=$!
kubectl -n agentops port-forward svc/web "$WEB_PORT:3000" >/tmp/kind-web-pf.log 2>&1 &
WEB_PF=$!

for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:$API_PORT/health" >/dev/null; then
    break
  fi
  sleep 1
done

curl -fsS -X POST "http://127.0.0.1:$API_PORT/docs" \
  -H 'content-type: application/json' \
  -d '{"id":"d1","text":"refund policy is 30 days"}'
echo

found=0
for _ in $(seq 1 40); do
  body="$(curl -fsS -X POST "http://127.0.0.1:$API_PORT/ask" \
    -H 'content-type: application/json' \
    -d '{"question":"refund policy"}')"
  if python3 -c 'import json,sys; body=json.loads(sys.argv[1]); raise SystemExit(0 if body.get("answer") and body["answer"][0]["id"]=="d1" else 1)' "$body"; then
    found=1
    echo "$body"
    break
  fi
  sleep 2
done
if [[ "$found" != 1 ]]; then
  echo "document was not searchable" >&2
  kubectl -n agentops logs deploy/worker >&2 || true
  kubectl -n agentops logs deploy/api >&2 || true
  exit 1
fi

calc="$(curl -fsS -X POST "http://127.0.0.1:$WEB_PORT/api/ask" \
  -H 'content-type: application/json' \
  -d '{"question":"2*(3+4)"}')"
echo "$calc"
python3 -c 'import json,sys; body=json.loads(sys.argv[1]); assert body["answer"]==14 and body["tool"]=="calculator"' "$calc"
echo "kind smoke ok"
