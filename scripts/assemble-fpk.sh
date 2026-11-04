#!/usr/bin/env bash
# Assemble fpk/app binaries from build outputs + rustdesk-api release, then fnpack build.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FPK="${ROOT}/fpk"
DIST="${ROOT}/dist"
API_VER="${API_VER:-v2.7}"
BIN_DIR="${BIN_DIR:-${ROOT}/target/x86_64-unknown-linux-musl/release}"

mkdir -p "${DIST}" "${FPK}/app/bin" "${FPK}/app/resources" "${FPK}/app/conf/admin"

need() {
	[ -x "$1" ] || { echo "missing binary: $1" >&2; exit 1; }
}

need "${BIN_DIR}/hbbs"
need "${BIN_DIR}/hbbr"

cp -f "${BIN_DIR}/hbbs" "${FPK}/app/bin/hbbs"
cp -f "${BIN_DIR}/hbbr" "${FPK}/app/bin/hbbr"
chmod 755 "${FPK}/app/bin/hbbs" "${FPK}/app/bin/hbbr"

API_TGZ="${ROOT}/third_party/linux-amd64.tar.gz"
if [ ! -f "${API_TGZ}" ]; then
	mkdir -p "${ROOT}/third_party"
	gh release download "${API_VER}" -R lejianwen/rustdesk-api -p 'linux-amd64.tar.gz' -D "${ROOT}/third_party"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
tar -xzf "${API_TGZ}" -C "${TMP}"
API_ROOT="${TMP}/release"
[ -x "${API_ROOT}/apimain" ] || { echo "apimain not found in api tarball" >&2; exit 1; }

cp -f "${API_ROOT}/apimain" "${FPK}/app/bin/rustdesk-api"
chmod 755 "${FPK}/app/bin/rustdesk-api"
rm -rf "${FPK}/app/resources"
cp -a "${API_ROOT}/resources" "${FPK}/app/resources"
# Keep our fnOS-tuned config; only take hello.html if we don't have one.
if [ ! -f "${FPK}/app/conf/admin/hello.html" ] && [ -f "${API_ROOT}/conf/admin/hello.html" ]; then
	cp -f "${API_ROOT}/conf/admin/hello.html" "${FPK}/app/conf/admin/hello.html"
fi

chmod 755 "${FPK}/cmd/"*

FNPACK="${FNPACK:-fnpack}"
if ! command -v "${FNPACK}" >/dev/null 2>&1; then
	if [ -x /tmp/fnpack ]; then
		FNPACK=/tmp/fnpack
	else
		echo "fnpack not found; download from https://static2.fnnas.com/fnpack/" >&2
		exit 1
	fi
fi

(
	cd "${FPK}"
	"${FNPACK}" build
)

shopt -s nullglob
for f in "${FPK}"/*.fpk; do
	cp -f "$f" "${DIST}/"
	echo "built: ${DIST}/$(basename "$f")"
done
