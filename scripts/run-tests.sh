#!/usr/bin/env bash
# Chạy toàn bộ automation test: lint + unit + integration (+ system nếu --system).
# Dùng:  ./scripts/run-tests.sh [--system]
#   --system: boot server thật + gọi OpenRouter thật (~2 phút, cần key trong .env)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/backend/.venv/bin/python"
[[ -x $PY ]] || PY=$(command -v python3)

fail=0
run() {
  local name="$1"; shift
  echo
  echo "=== $name ==="
  if "$@"; then
    echo "--- OK: $name"
  else
    echo "--- FAIL: $name" >&2
    fail=1
  fi
}

run "ruff lint" bash -c "cd backend && $PY -m ruff check ."
run "backend unit + integration (offline)" bash -c "cd backend && $PY -m pytest -q"

if [[ "${1:-}" == "--system" ]]; then
  run "backend system (live OpenRouter)" bash -c "cd backend && $PY -m pytest tests/system -m system -q"
else
  echo
  echo "=== backend system: BỎ QUA (thêm --system để chạy với OpenRouter thật) ==="
fi

if [[ -d frontend/node_modules ]]; then
  run "frontend typecheck" bash -c "cd frontend && npm run lint"
  run "frontend vitest" bash -c "cd frontend && npm test"
else
  echo "frontend/node_modules chưa có — bỏ qua gate FE (chạy npm install trước)" >&2
  fail=1
fi

echo
if [[ $fail -eq 0 ]]; then
  echo "TẤT CẢ TEST PASS ✅"
else
  echo "CÓ BÀI FAIL ❌" >&2
  exit 1
fi
