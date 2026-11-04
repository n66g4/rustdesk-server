#!/bin/bash
# Config panel API. CGI has no TRIM_*; use fixed /var/apps paths.
# cmd/ is sibling of target/, not under target/.
exec 2>>/var/apps/rustdesk-server/var/cgi.log

json_escape() {
	printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/	/\\t/g' | tr -d '\r\n'
}

json_ok() {
	echo "Content-Type: application/json; charset=utf-8"
	echo ""
	echo "$1"
}

json_err() {
	echo "Content-Type: application/json; charset=utf-8"
	echo ""
	printf '{"success":false,"message":"%s"}\n' "$(json_escape "$1")"
}

APP_NAME="rustdesk-server"
APP_BASE="/var/apps/${APP_NAME}"
APP_DIR="${APP_BASE}/target"
CONF_DIR="${APP_BASE}/etc"
DATA_DIR="${APP_BASE}/var"
CMD_DIR="${APP_BASE}/cmd"
WIZARD_FILE="${CONF_DIR}/wizard.conf"
CFG_FILE="${CONF_DIR}/config.yaml"
PUB_FILE="${DATA_DIR}/data/id_ed25519.pub"

export TRIM_APPDEST="${APP_DIR}"
export TRIM_PKGETC="${CONF_DIR}"
export TRIM_PKGVAR="${DATA_DIR}"

mkdir -p "${DATA_DIR}" "${CONF_DIR}" 2>/dev/null || true

if [ -f "${CMD_DIR}/_common" ]; then
	# shellcheck source=/dev/null
	. "${CMD_DIR}/_common"
	# Re-assert paths in case _common left blanks when TRIM was empty before export.
	APP_DIR="${TRIM_APPDEST}"
	CONF_DIR="${TRIM_PKGETC}"
	DATA_DIR="${TRIM_PKGVAR}"
	WIZARD_FILE="${CONF_DIR}/wizard.conf"
	CFG_FILE="${CONF_DIR}/config.yaml"
	PUB_FILE="${DATA_DIR}/data/id_ed25519.pub"
fi

log() {
	echo "$(date '+%Y-%m-%d %H:%M:%S') [api.cgi] $*" >> "${DATA_DIR}/cgi.log" 2>/dev/null || true
}

# Log-friendly API URL: scheme://host:port (empty host → 127.0.0.1)
fmt_api() {
	local scheme=${1:-http}
	local host=${2:-}
	local port=${3:-21114}
	[ -n "${host}" ] || host="127.0.0.1"
	printf '%s://%s:%s' "${scheme}" "${host}" "${port}"
}

read_body() {
	local len="${CONTENT_LENGTH:-0}"
	if [ "${REQUEST_METHOD}" = "POST" ] && [ "${len}" -gt 0 ] 2>/dev/null; then
		dd bs=1 count="${len}" 2>/dev/null || head -c "${len}"
	fi
}

urldecode() {
	local data=${1//+/ }
	local LC_ALL=C
	printf '%b' "${data//%/\\x}"
}

parse_kv() {
	local raw=$1
	[ -n "${raw}" ] || return 0
	local IFS='&'
	# shellcheck disable=SC2086
	set -- ${raw}
	local pair key val
	for pair in "$@"; do
		[ -n "${pair}" ] || continue
		key=${pair%%=*}
		val=${pair#*=}
		[ "${key}" = "${pair}" ] && val=""
		key=$(urldecode "${key}")
		val=$(urldecode "${val}")
		case "${key}" in
			action|host|api_scheme|api_port|hbbs_port|hbbr_port|key|must_login|use_custom_key)
				printf '%s\t%s\n' "${key}" "${val}"
				;;
		esac
	done
}

read_public_key() {
	if [ -s "${PUB_FILE}" ]; then
		tr -d '\r\n' < "${PUB_FILE}"
	fi
}

get_kv() {
	local want=$1
	local def=${2:-}
	local k v
	while IFS=$'\t' read -r k v; do
		if [ "${k}" = "${want}" ]; then
			printf '%s' "${v}"
			return 0
		fi
	done < "${KV_FILE}"
	printf '%s' "${def}"
}

yaml_get() {
	# yaml_get section key  → scalar inside section
	local section=$1
	local key=$2
	local file=${3:-$CFG_FILE}
	[ -f "${file}" ] || return 0
	awk -v section="${section}" -v key="${key}" '
		$0 ~ ("^" section ":") { f=1; next }
		f && /^[^[:space:]#]/ { f=0 }
		f && $0 ~ ("^[[:space:]]*" key ":[[:space:]]*") {
			line=$0
			sub(/^[[:space:]]*[^:]+:[[:space:]]*/, "", line)
			gsub(/^"/, "", line); gsub(/"$/, "", line)
			gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
			print line
			exit
		}
	' "${file}"
}

# Fill wizard_* from wizard.conf; if missing, from config.yaml.
hydrate_config() {
	wizard_host=""
	wizard_api_scheme="http"
	wizard_api_port="21114"
	wizard_hbbs_port="21116"
	wizard_hbbr_port="21117"
	wizard_key=""
	wizard_must_login="N"

	if [ -f "${WIZARD_FILE}" ]; then
		# shellcheck disable=SC1090
		set -a
		# shellcheck source=/dev/null
		. "${WIZARD_FILE}"
		set +a
	else
		# First-run / upgrade: derive from live yaml written by install/start.
		local id_server relay_server api_server api_addr
		id_server=$(yaml_get rustdesk id-server)
		relay_server=$(yaml_get rustdesk relay-server)
		api_server=$(yaml_get rustdesk api-server)
		api_addr=$(yaml_get gin api-addr)

		if [ -n "${id_server}" ]; then
			wizard_host="${id_server%%:*}"
			[ "${wizard_host}" = "127.0.0.1" ] && wizard_host=""
			if [ "${id_server}" != "${id_server#*:}" ]; then
				wizard_hbbs_port="${id_server##*:}"
			fi
		fi
		if [ -n "${relay_server}" ] && [ "${relay_server}" != "${relay_server#*:}" ]; then
			wizard_hbbr_port="${relay_server##*:}"
		fi
		if [ -n "${api_server}" ]; then
			case "${api_server}" in
				https://*) wizard_api_scheme="https" ;;
				http://*) wizard_api_scheme="http" ;;
			esac
			local rest="${api_server#*://}"
			local ap="${rest##*:}"
			ap="${ap%%/*}"
			case "${ap}" in
				*[!0-9]*) ;;
				*) [ -n "${ap}" ] && wizard_api_port="${ap}" ;;
			esac
		fi
		if [ -n "${api_addr}" ] && [ "${api_addr}" != "${api_addr#*:}" ]; then
			local gp="${api_addr##*:}"
			case "${gp}" in
				*[!0-9]*) ;;
				*) wizard_api_port="${gp}" ;;
			esac
		fi
	fi

	wizard_api_scheme="${wizard_api_scheme:-http}"
	wizard_hbbs_port="${wizard_hbbs_port:-21116}"
	wizard_hbbr_port="${wizard_hbbr_port:-21117}"
	wizard_api_port=$((wizard_hbbs_port - 2))
	wizard_must_login="${wizard_must_login:-N}"
	wizard_use_custom_key="${wizard_use_custom_key:-}"

	public_key=$(read_public_key)
	local cfg_key
	cfg_key=$(yaml_get rustdesk key)

	# Prefer explicit wizard custom key; else infer from yaml vs pubkey.
	if [ -z "${wizard_key}" ] && [ -n "${cfg_key}" ] && [ "${cfg_key}" != "${public_key}" ]; then
		wizard_key="${cfg_key}"
	fi
	if [ -z "${wizard_use_custom_key}" ]; then
		if [ -n "${wizard_key}" ] && [ "${wizard_key}" != "${public_key}" ]; then
			wizard_use_custom_key="Y"
		else
			wizard_use_custom_key="N"
			wizard_key=""
		fi
	fi
}

valid_port() {
	local p=$1
	case "${p}" in
		''|*[!0-9]*) return 1 ;;
	esac
	[ "${p}" -ge 1 ] && [ "${p}" -le 65535 ]
}

# Synology-style host check: empty OK; else domain / IPv4 / IPv6; reject host:port.
valid_host() {
	local host=$1
	[ -z "${host}" ] && return 0
	case "${host}" in
		*:*)
			# Allow IPv6; reject host:port (single colon + digits).
			if printf '%s' "${host}" | grep -Eq '^[^:]+:[0-9]+$'; then
				return 1
			fi
			;;
	esac
	printf '%s' "${host}" | grep -Eq \
		'^(([a-zA-Z0-9_-]+\.)+[a-zA-Z]{2,}|((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|([a-fA-F0-9:]+:+)+[a-fA-F0-9]+)$'
}

config_fingerprint() {
	{
		cat "${WIZARD_FILE}" 2>/dev/null || true
		cat "${CFG_FILE}" 2>/dev/null || true
	} | cksum | awk '{print $1" "$2}'
}

api_pids() {
	# Match full path or bare name (argv0 may be basename).
	{
		pgrep -f "${APP_DIR}/bin/rustdesk-api" 2>/dev/null || true
		pgrep -x rustdesk-api 2>/dev/null || true
	} | sort -u | tr '\n' ' '
}

supervisor_alive() {
	local pf="${DATA_DIR}/rustdesk-server.pid"
	[ -f "${pf}" ] || return 1
	local pid
	pid=$(tr -d '[:space:]' < "${pf}")
	[ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null
}

ensure_supervisor() {
	export TRIM_APPDEST TRIM_PKGETC TRIM_PKGVAR
	if supervisor_alive; then
		log "supervisor ok (pid $(tr -d '[:space:]' < "${DATA_DIR}/rustdesk-server.pid"))"
		return 0
	fi
	log "supervisor down → main start"
	if ! "${CMD_DIR}/main" start >> "${DATA_DIR}/cgi.log" 2>&1; then
		log "main start failed"
		return 1
	fi
	supervisor_alive
}

# Synology-style poke + ensure supervisor is up (fnOS CGI cannot rely on appcenter alone).
restart_services() {
	local mark="${DATA_DIR}/config.applied"
	local want
	want=$(config_fingerprint)

	# Force supervisor to treat config as dirty even if values unchanged.
	rm -f "${mark}"

	if ! ensure_supervisor; then
		log "reload aborted: supervisor unavailable"
		return 1
	fi

	local pids
	pids=$(api_pids)
	pids=$(echo "${pids}" | xargs)
	if [ -n "${pids}" ]; then
		log "reload: kill rustdesk-api (pid ${pids})"
		# shellcheck disable=SC2086
		kill -TERM ${pids} 2>/dev/null || true
	else
		log "reload: rustdesk-api not running, wait for supervisor"
	fi

	local i=0
	local applied=""
	while [ "${i}" -lt 45 ]; do
		pids=$(echo "$(api_pids)" | xargs)
		applied=""
		[ -f "${mark}" ] && applied=$(tr -d '\r\n' < "${mark}")
		if [ -n "${pids}" ]; then
			# Prefer fingerprint match; accept api-up if mark lags one cycle.
			if [ "${applied}" = "${want}" ] || [ "${i}" -ge 5 ]; then
				log "reload ok (api pid ${pids}, ${i}s)"
				return 0
			fi
		fi
		# Supervisor died mid-wait — try once more.
		if [ "${i}" -eq 15 ] && ! supervisor_alive; then
			log "reload: supervisor died, restarting"
			ensure_supervisor || true
		fi
		sleep 1
		i=$((i + 1))
	done
	log "reload timeout after ${i}s (fingerprint want=[${want}] applied=[${applied:-none}] api=[${pids:-none}] supervisor=$(supervisor_alive && echo up || echo down))"
	log "---- rustdesk-server.log (tail) ----"
	tail -n 30 "${DATA_DIR}/rustdesk-server.log" >> "${DATA_DIR}/cgi.log" 2>/dev/null || true
	return 1
}

do_get() {
	hydrate_config
	local show_key="${wizard_key}"
	[ "${wizard_use_custom_key}" = "Y" ] || show_key="${public_key}"
	log "load host=${wizard_host:-127.0.0.1} api=$(fmt_api "${wizard_api_scheme}" "${wizard_host}" "${wizard_api_port}") hbbs=${wizard_hbbs_port} hbbr=${wizard_hbbr_port} must_login=${wizard_must_login} custom_key=${wizard_use_custom_key}"
	json_ok "$(printf '{"success":true,"host":"%s","api_scheme":"%s","api_port":"%s","hbbs_port":"%s","hbbr_port":"%s","key":"%s","public_key":"%s","use_custom_key":"%s","must_login":"%s"}' \
		"$(json_escape "${wizard_host}")" \
		"$(json_escape "${wizard_api_scheme}")" \
		"$(json_escape "${wizard_api_port}")" \
		"$(json_escape "${wizard_hbbs_port}")" \
		"$(json_escape "${wizard_hbbr_port}")" \
		"$(json_escape "${show_key}")" \
		"$(json_escape "${public_key}")" \
		"$(json_escape "${wizard_use_custom_key}")" \
		"$(json_escape "${wizard_must_login}")")"
}

do_save() {
	local host api_scheme api_port hbbs_port hbbr_port key must_login use_custom_key
	host=$(get_kv host "")
	api_scheme=$(get_kv api_scheme "http")
	hbbs_port=$(get_kv hbbs_port "21116")
	hbbr_port=$(get_kv hbbr_port "21117")
	key=$(get_kv key "")
	must_login=$(get_kv must_login "N")
	use_custom_key=$(get_kv use_custom_key "N")

	if ! valid_host "${host}"; then
		json_err "请输入有效的域名或 IP 地址（不要带端口）"
		return 0
	fi
	case "${api_scheme}" in
		http|https) ;;
		*) api_scheme=http ;;
	esac
	case "${must_login}" in
		Y|N) ;;
		*) must_login=N ;;
	esac
	case "${use_custom_key}" in
		Y|N) ;;
		*) use_custom_key=N ;;
	esac
	if ! valid_port "${hbbs_port}" || ! valid_port "${hbbr_port}"; then
		json_err "端口无效"
		return 0
	fi
	# API port locked to hbbs-2 (Synology).
	api_port=$((hbbs_port - 2))
	if ! valid_port "${api_port}"; then
		json_err "hbbs 端口过小，无法派生 API 端口 (hbbs−2)"
		return 0
	fi
	if { [ "${hbbs_port}" != "21116" ] || [ "${hbbr_port}" != "21117" ]; } && [ -z "${host}" ]; then
		json_err "使用非默认端口时必须填写域名或 IP"
		return 0
	fi
	if [ "${use_custom_key}" = "Y" ] && [ -z "${key}" ]; then
		json_err "已勾选自定义 KEY，请填写 Key"
		return 0
	fi

	if [ ! -d "${CONF_DIR}" ]; then
		json_err "配置目录不存在: ${CONF_DIR}"
		return 0
	fi

	wizard_host="${host}"
	wizard_api_scheme="${api_scheme}"
	wizard_api_port="${api_port}"
	wizard_hbbs_port="${hbbs_port}"
	wizard_hbbr_port="${hbbr_port}"
	wizard_must_login="${must_login}"
	wizard_use_custom_key="${use_custom_key}"

	local pub
	pub=$(read_public_key)
	if [ "${use_custom_key}" = "Y" ]; then
		wizard_key="${key}"
	else
		wizard_key=""
		key="${pub}"
	fi

	if type seed_package_config >/dev/null 2>&1; then
		seed_package_config
		# Persist use_custom_key alongside other wizard fields.
		mkdir -p "${CONF_DIR}" 2>/dev/null || true
		cat > "${WIZARD_FILE}" <<EOF
wizard_host=${wizard_host}
wizard_api_scheme=${wizard_api_scheme}
wizard_api_port=${wizard_api_port}
wizard_hbbs_port=${wizard_hbbs_port}
wizard_hbbr_port=${wizard_hbbr_port}
wizard_key=${wizard_key}
wizard_use_custom_key=${wizard_use_custom_key}
wizard_must_login=${wizard_must_login}
EOF
		apply_wizard_to_yaml
		# Always write the effective key into yaml (custom or auto pubkey).
		if [ -n "${key}" ]; then
			if type yaml_set_section_key >/dev/null 2>&1; then
				yaml_set_section_key "${CFG_FILE}" "rustdesk" "key" "${key}"
			fi
		fi
	else
		mkdir -p "${CONF_DIR}" "${DATA_DIR}/data" 2>/dev/null || true
		cat > "${WIZARD_FILE}" <<EOF
wizard_host=${wizard_host}
wizard_api_scheme=${wizard_api_scheme}
wizard_api_port=${wizard_api_port}
wizard_hbbs_port=${wizard_hbbs_port}
wizard_hbbr_port=${wizard_hbbr_port}
wizard_key=${wizard_key}
wizard_use_custom_key=${wizard_use_custom_key}
wizard_must_login=${wizard_must_login}
EOF
		if [ ! -f "${CFG_FILE}" ] && [ -f "${APP_DIR}/conf/config.yaml" ]; then
			cp -f "${APP_DIR}/conf/config.yaml" "${CFG_FILE}"
		fi
	fi

	if [ ! -f "${WIZARD_FILE}" ]; then
		json_err "写入 wizard.conf 失败（权限或路径）"
		return 0
	fi

	log "save host=${host:-127.0.0.1} api=$(fmt_api "${api_scheme}" "${host}" "${api_port}") hbbs=${hbbs_port} hbbr=${hbbr_port} must_login=${must_login} custom_key=${use_custom_key}"

	if ! restart_services; then
		json_err "配置已写入，但服务未在时限内重载。请在应用中心停止后再启动一次，详见 ${DATA_DIR}/cgi.log"
		return 0
	fi

	hydrate_config
	local out_key="${wizard_key}"
	[ "${wizard_use_custom_key}" = "Y" ] || out_key="${public_key}"
	json_ok "$(printf '{"success":true,"message":"配置已更新并重启服务。","key":"%s","public_key":"%s","use_custom_key":"%s"}' \
		"$(json_escape "${out_key}")" \
		"$(json_escape "${public_key}")" \
		"$(json_escape "${wizard_use_custom_key}")")"
}

KV_FILE=$(mktemp)
trap 'rm -f "${KV_FILE}"' EXIT

{
	parse_kv "${QUERY_STRING:-}"
	if [ "${REQUEST_METHOD}" = "POST" ]; then
		parse_kv "$(read_body)"
	fi
} > "${KV_FILE}"

ACTION=$(get_kv action "get")
case "${ACTION}" in
	get) do_get ;;
	save) do_save ;;
	*) json_err "unknown action" ;;
esac
