#!/bin/bash
# Serve the desktop config panel (static files under www/).
# Hardcode install path — CGI $0 / TRIM_* are unreliable.
exec 2>>/var/apps/rustdesk-server/var/cgi.log

BASE="/var/apps/rustdesk-server/target/ui/www"
mkdir -p /var/apps/rustdesk-server/var 2>/dev/null || true

URI_NO_QUERY="${REQUEST_URI%%\?*}"
REL_PATH="/"
case "${URI_NO_QUERY}" in
	*index.cgi*)
		REL_PATH="${URI_NO_QUERY#*index.cgi}"
		;;
esac
[ -z "${REL_PATH}" ] || [ "${REL_PATH}" = "/" ] && REL_PATH="/index.html"

case "${REL_PATH}" in
	*..*)
		echo "Status: 400 Bad Request"
		echo "Content-Type: text/plain; charset=utf-8"
		echo ""
		echo "Bad Request"
		exit 0
		;;
esac

FILE="${BASE}${REL_PATH}"
if [ ! -f "${FILE}" ]; then
	echo "Status: 404 Not Found"
	echo "Content-Type: text/plain; charset=utf-8"
	echo ""
	echo "Not Found: ${REL_PATH}"
	exit 0
fi

case "${FILE##*.}" in
	html) mime="text/html; charset=utf-8" ;;
	css) mime="text/css; charset=utf-8" ;;
	js) mime="application/javascript; charset=utf-8" ;;
	png) mime="image/png" ;;
	*) mime="application/octet-stream" ;;
esac

echo "Content-Type: ${mime}"
echo ""
cat "${FILE}"
