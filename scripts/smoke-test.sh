#!/usr/bin/env bash
# Smoke test deploy: gọi các endpoint trên một backend ĐANG CHẠY.
# Dùng:  BACKEND_URL=http://localhost:8000 ./scripts/smoke-test.sh
set -euo pipefail

BASE="${BACKEND_URL:-http://localhost:8000}"

check() {
  local name="$1" path="$2" expect="$3"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$BASE$path")
  if [[ "$code" == "$expect" ]]; then
    echo "PASS  $name ($BASE$path → $code)"
  else
    echo "FAIL  $name ($BASE$path → $code, mong đợi $expect)" >&2
    exit 1
  fi
}

echo "Smoke test → $BASE"
check "health"             "/api/health"            200
check "products list"      "/api/products?limit=5"  200
check "admin chặn vô danh" "/api/admin/stats"       401

# product detail: lấy id đầu tiên từ chính danh sách (catalog có thể trống trên CI)
first_id=$(curl -s --max-time 15 "$BASE/api/products?limit=1" | python3 -c "import json,sys; items=json.load(sys.stdin)['items']; print(items[0]['id'] if items else '')" 2>/dev/null || true)
if [[ -n "$first_id" ]]; then
  check "product detail" "/api/products/$first_id" 200
  echo "SMOKE OK ✅ (detail test trên $first_id)"
else
  echo "SMOKE OK ✅ (catalog trống — bỏ qua detail)"
fi
