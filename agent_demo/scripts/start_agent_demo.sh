#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-9091}"
PYTHON_BIN="${PYTHON_BIN:-python}"
UVICORN_APP="${UVICORN_APP:-main:app}"
ENABLE_TUNNEL="${ENABLE_TUNNEL:-true}"
TUNNEL_PROTOCOL="${TUNNEL_PROTOCOL:-http2}"
LOG_DIR="${LOG_DIR:-$APP_DIR/logs}"
PID_DIR="${PID_DIR:-$APP_DIR/.run}"

APP_LOG="$LOG_DIR/agent_demo.log"
TUNNEL_LOG="$LOG_DIR/cloudflared.log"
APP_PID="$PID_DIR/agent_demo.pid"
TUNNEL_PID="$PID_DIR/cloudflared.pid"

mkdir -p "$LOG_DIR" "$PID_DIR"

is_running() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file")"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

start_app() {
  if is_running "$APP_PID"; then
    echo "Agent demo already running pid=$(cat "$APP_PID")"
    return
  fi

  cd "$APP_DIR"
  nohup "$PYTHON_BIN" -m uvicorn "$UVICORN_APP" \
    --app-dir src \
    --host "$HOST" \
    --port "$PORT" \
    >>"$APP_LOG" 2>&1 &
  echo $! > "$APP_PID"
  echo "Agent demo started pid=$(cat "$APP_PID") log=$APP_LOG"
}

start_tunnel() {
  if [[ "$ENABLE_TUNNEL" != "true" ]]; then
    echo "Cloudflare tunnel disabled. Set ENABLE_TUNNEL=true to enable."
    return
  fi

  if is_running "$TUNNEL_PID"; then
    echo "Cloudflare tunnel already running pid=$(cat "$TUNNEL_PID")"
    return
  fi

  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared not found. Install it first or run with ENABLE_TUNNEL=false."
    return 1
  fi

  nohup cloudflared tunnel \
    --protocol "$TUNNEL_PROTOCOL" \
    --url "http://127.0.0.1:$PORT" \
    >>"$TUNNEL_LOG" 2>&1 &
  echo $! > "$TUNNEL_PID"
  echo "Cloudflare tunnel started pid=$(cat "$TUNNEL_PID") log=$TUNNEL_LOG"
  print_webhook_url_with_retry
}

stop_pid() {
  local name="$1"
  local pid_file="$2"
  if ! is_running "$pid_file"; then
    echo "$name is not running"
    rm -f "$pid_file"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  kill "$pid"
  rm -f "$pid_file"
  echo "$name stopped pid=$pid"
}

status() {
  if is_running "$APP_PID"; then
    echo "Agent demo: running pid=$(cat "$APP_PID")"
  else
    echo "Agent demo: stopped"
  fi

  if is_running "$TUNNEL_PID"; then
    echo "Cloudflare tunnel: running pid=$(cat "$TUNNEL_PID")"
    print_webhook_url
  else
    echo "Cloudflare tunnel: stopped"
  fi
}

current_tunnel_url() {
  [[ -f "$TUNNEL_LOG" ]] || return 1
  grep -Eo 'https://[^ ]+trycloudflare.com' "$TUNNEL_LOG" | tail -1
}

print_webhook_url() {
  local tunnel_url
  tunnel_url="$(current_tunnel_url || true)"
  if [[ -z "$tunnel_url" ]]; then
    echo "Tunnel URL not found yet. Check log: $TUNNEL_LOG"
    return 1
  fi

  echo "Tunnel URL: $tunnel_url"
  echo "Chatwoot Agent Bot URL:"
  echo "$tunnel_url/webhook/chatwoot"
}

print_webhook_url_with_retry() {
  local attempt
  for attempt in {1..12}; do
    if print_webhook_url >/tmp/agent_demo_webhook_url.$$ 2>/dev/null; then
      cat /tmp/agent_demo_webhook_url.$$
      rm -f /tmp/agent_demo_webhook_url.$$
      return 0
    fi
    sleep 1
  done
  rm -f /tmp/agent_demo_webhook_url.$$
  echo "Tunnel URL is not ready yet. Run this later:"
  echo "  $0 url"
}

case "${1:-start}" in
  start)
    start_app
    start_tunnel
    ;;
  stop)
    stop_pid "Cloudflare tunnel" "$TUNNEL_PID"
    stop_pid "Agent demo" "$APP_PID"
    ;;
  restart)
    "$0" stop
    "$0" start
    ;;
  status)
    status
    ;;
  url)
    print_webhook_url
    ;;
  logs)
    tail -f "$APP_LOG" "$TUNNEL_LOG"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|url|logs}"
    exit 1
    ;;
esac
