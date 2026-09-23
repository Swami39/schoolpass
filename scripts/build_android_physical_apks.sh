#!/usr/bin/env bash
# Build installable Android APKs for physical devices on the same Wi‑Fi as this Mac.
# API must listen on all interfaces: see scripts/run_api_lan.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"

detect_lan_ip() {
  ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true
}

LAN_IP="${SCHOOLPASS_LAN_IP:-$(detect_lan_ip)}"
if [[ -z "$LAN_IP" ]]; then
  echo "Could not detect LAN IP. Set SCHOOLPASS_LAN_IP (e.g. 192.168.1.43) and re-run." >&2
  exit 1
fi

API_ORIGIN="${SCHOOLPASS_API_ORIGIN:-http://${LAN_IP}:8000}"
TENANT_ID="${SCHOOLPASS_TENANT_ID:-}"
if [[ -z "$TENANT_ID" && -f "$ROOT/.data/local_demo_credentials.json" ]]; then
  TENANT_ID="$(python3 -c "import json; print(json.load(open('$ROOT/.data/local_demo_credentials.json'))['tenant_id'])")"
fi

OUT_DIR="$ROOT/dist/android-apks"
mkdir -p "$OUT_DIR"

COMMON_DEFINES=(--dart-define="SCHOOLPASS_API_ORIGIN=$API_ORIGIN")
ADMIN_DEFINES=("${COMMON_DEFINES[@]}")
if [[ -n "$TENANT_ID" ]]; then
  ADMIN_DEFINES+=(--dart-define="SCHOOLPASS_TENANT_ID=$TENANT_ID")
fi

echo "Building APKs → $OUT_DIR"
echo "  API origin: $API_ORIGIN"
[[ -n "$TENANT_ID" ]] && echo "  Tenant ID:  $TENANT_ID (admin app only)"

build_one() {
  local dir="$1"
  local name="$2"
  shift 2
  echo ""
  echo "==> $name ($dir)"
  (cd "$ROOT/$dir" && flutter pub get && flutter build apk --release "$@")
  local apk="$ROOT/$dir/build/app/outputs/flutter-apk/app-release.apk"
  cp "$apk" "$OUT_DIR/$name"
  echo "    → $OUT_DIR/$name"
}

build_one apps/mobile/admin_app schoolpass-admin.apk "${ADMIN_DEFINES[@]}"
build_one apps/mobile/parent_app_mobile schoolpass-parent.apk "${COMMON_DEFINES[@]}"
build_one apps/mobile/teacher_app_mobile schoolpass-teacher.apk "${COMMON_DEFINES[@]}"
build_one apps/mobile/attendant_app_mobile schoolpass-attendant.apk "${COMMON_DEFINES[@]}"

echo ""
echo "Done. Install on phone (USB debugging or adb install):"
echo "  adb install -r $OUT_DIR/schoolpass-parent.apk"
echo ""
echo "Before testing, on this Mac:"
echo "  docker compose -f infra/docker/compose.yaml up -d"
echo "  ./scripts/run_api_lan.sh"
echo "Phones must use the same Wi‑Fi. If your Mac IP changes, re-run this script."
echo ""
echo "Demo logins: .data/local_demo_credentials.json (password Demo-Local-Only-2026)"
echo "Bus attendant: schoolpass-attendant.apk (demo.attendant@schoolpass.local)."
