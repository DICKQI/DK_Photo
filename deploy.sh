#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# DK Photo Docker Deployment Script
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "\n${CYAN}==> $*${NC}"; }

SCRIPT_SOURCE="${BASH_SOURCE[0]}"
case "$SCRIPT_SOURCE" in
    */*) SCRIPT_DIR="$(cd -P "${SCRIPT_SOURCE%/*}" && pwd)" ;;
    *) SCRIPT_DIR="$(pwd)" ;;
esac
PHOTOS_OVERRIDE_FILE="docker-compose.photos.yml"
PHOTO_MOUNTS_FILE=".dk-photo-photo-mounts"
SUDO=()
DOCKER_CMD=(docker)
COMPOSE_ARGS=(-f docker-compose.yml)
ENV_CREATED=0
DB_EXISTS=0
GENERATED_ADMIN_PASSWORD=""
GENERATED_SECRET_KEY=0

prompt_yes_no() {
    local prompt="$1"
    local default="${2:-n}"
    local answer suffix

    if [ "$default" = "y" ]; then
        suffix="[Y/n]"
    else
        suffix="[y/N]"
    fi

    while true; do
        read -r -p "$prompt $suffix " answer
        answer="${answer:-$default}"
        case "${answer,,}" in
            y|yes) return 0 ;;
            n|no) return 1 ;;
            *) log_warn "Please enter y or n." ;;
        esac
    done
}

trim() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "$value"
}

strip_env_quotes() {
    local value="$1"
    local first last

    if [ "${#value}" -ge 2 ]; then
        first="${value:0:1}"
        last="${value: -1}"
        if { [ "$first" = '"' ] && [ "$last" = '"' ]; } || { [ "$first" = "'" ] && [ "$last" = "'" ]; }; then
            value="${value:1:${#value}-2}"
        fi
    fi

    value="${value//\\\"/\"}"
    printf '%s' "$value"
}

env_get() {
    local key="$1"
    local default="${2:-}"
    local line value

    line="$(grep -E "^[[:space:]]*${key}=" .env 2>/dev/null | tail -n 1 || true)"
    if [ -z "$line" ]; then
        printf '%s' "$default"
        return
    fi

    value="${line#*=}"
    value="${value%$'\r'}"
    value="$(trim "$value")"
    value="$(strip_env_quotes "$value")"
    printf '%s' "${value:-$default}"
}

quote_env_value() {
    local value="$1"

    if [ -z "$value" ]; then
        printf '""'
        return
    fi

    if [[ "$value" =~ ^[-A-Za-z0-9_./:@%+=,]+$ ]]; then
        printf '%s' "$value"
        return
    fi

    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '"%s"' "$value"
}

env_set() {
    local key="$1"
    local value="$2"
    local encoded tmp found line

    encoded="$(quote_env_value "$value")"
    tmp="$(mktemp)"
    found=0

    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            "$key"=*)
                if [ "$found" -eq 0 ]; then
                    printf '%s=%s\n' "$key" "$encoded" >> "$tmp"
                    found=1
                fi
                ;;
            *)
                printf '%s\n' "$line" >> "$tmp"
                ;;
        esac
    done < .env

    if [ "$found" -eq 0 ]; then
        printf '%s=%s\n' "$key" "$encoded" >> "$tmp"
    fi

    mv "$tmp" .env
}

random_hex() {
    local bytes="$1"

    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex "$bytes"
        return
    fi

    dd if=/dev/urandom bs="$bytes" count=1 2>/dev/null | od -An -tx1 | tr -d ' \n'
}

# 获取服务器局域网 IP 和公网 IP
get_local_ip() {
    local ip=""
    # 优先用 ip route 获取默认网卡 IP
    if command -v ip >/dev/null 2>&1; then
        ip="$(ip -4 route get 1 2>/dev/null | awk '{print $7; exit}' | head -n 1)" || true
    fi
    # 回退：hostname -I
    if [ -z "$ip" ] && command -v hostname >/dev/null 2>&1; then
        ip="$(hostname -I 2>/dev/null | awk '{print $1}')" || true
    fi
    printf '%s' "${ip:-<server-ip>}"
}

# 尝试获取公网 IP（通过外部服务查询）
get_public_ip() {
    local pub_ip=""
    if command -v curl >/dev/null 2>&1; then
        # 多个备用源
        for src in "https://ifconfig.me" "https://api.ipify.org" "https://ipv4.icanhazip.com"; do
            pub_ip="$(curl -s --connect-timeout 3 "$src" 2>/dev/null || true)"
            if [ -n "$pub_ip" ]; then
                break
            fi
        done
    fi
    printf '%s' "${pub_ip}"
}

setup_sudo() {
    if [ "$(id -u)" -eq 0 ]; then
        SUDO=()
        return
    fi

    if ! command -v sudo >/dev/null 2>&1; then
        log_error "sudo is required to install packages or run Docker as an unprivileged user."
        exit 1
    fi
    SUDO=(sudo)
}

is_supported_apt_linux() {
    [ -f /etc/os-release ] || return 1
    # shellcheck disable=SC1091
    . /etc/os-release
    [ "${ID:-}" = "ubuntu" ] || [ "${ID:-}" = "debian" ]
}

install_apt_packages() {
    setup_sudo
    "${SUDO[@]}" apt-get update
    "${SUDO[@]}" apt-get install -y "$@"
}

ensure_command() {
    local command_name="$1"
    local package_name="${2:-$1}"

    if command -v "$command_name" >/dev/null 2>&1; then
        return
    fi

    if is_supported_apt_linux && prompt_yes_no "$command_name is not installed. Install $package_name now?" "y"; then
        install_apt_packages "$package_name"
    fi

    if ! command -v "$command_name" >/dev/null 2>&1; then
        log_error "$command_name is required. Please install it and run this script again."
        exit 1
    fi
}

install_docker_engine() {
    local os_id codename docker_gpg arch

    if ! is_supported_apt_linux; then
        log_error "Automatic Docker installation is only supported on Ubuntu/Debian."
        log_error "Install Docker Engine and the Compose plugin first, then run this script again."
        exit 1
    fi

    # shellcheck disable=SC1091
    . /etc/os-release
    os_id="${ID}"
    codename="${VERSION_CODENAME:-${UBUNTU_CODENAME:-}}"

    if [ -z "$codename" ]; then
        log_error "Cannot determine the Ubuntu/Debian codename for Docker repository setup."
        exit 1
    fi

    setup_sudo
    log_step "Installing Docker Engine and Docker Compose plugin..."

    "${SUDO[@]}" apt-get update
    "${SUDO[@]}" apt-get install -y ca-certificates curl gnupg
    "${SUDO[@]}" install -m 0755 -d /etc/apt/keyrings

    docker_gpg="/tmp/docker-${os_id}.asc"
    curl -fsSL "https://download.docker.com/linux/${os_id}/gpg" -o "$docker_gpg"
    "${SUDO[@]}" gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg "$docker_gpg"
    "${SUDO[@]}" chmod a+r /etc/apt/keyrings/docker.gpg

    arch="$(dpkg --print-architecture)"
    echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${os_id} ${codename} stable" \
        | "${SUDO[@]}" tee /etc/apt/sources.list.d/docker.list >/dev/null

    "${SUDO[@]}" apt-get update
    "${SUDO[@]}" apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    if command -v systemctl >/dev/null 2>&1; then
        "${SUDO[@]}" systemctl enable --now docker >/dev/null 2>&1 || true
    fi
}

configure_docker_command() {
    DOCKER_CMD=(docker)
    if "${DOCKER_CMD[@]}" info >/dev/null 2>&1; then
        return
    fi

    if command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
        DOCKER_CMD=(sudo docker)
        log_info "Using sudo for Docker commands in this run."
        return
    fi

    log_error "Docker is installed but the daemon is not accessible."
    log_error "Start Docker and ensure your user can access it, or run this script with sudo."
    exit 1
}

docker_cmd() {
    "${DOCKER_CMD[@]}" "$@"
}

compose_cmd() {
    "${DOCKER_CMD[@]}" compose "${COMPOSE_ARGS[@]}" "$@"
}

compose_display() {
    if [ "${DOCKER_CMD[0]}" = "sudo" ]; then
        printf 'sudo docker compose'
    else
        printf 'docker compose'
    fi

    printf ' %q' "${COMPOSE_ARGS[@]}"
}

refresh_compose_args() {
    COMPOSE_ARGS=(-f docker-compose.yml)
    if [ -f "$PHOTOS_OVERRIDE_FILE" ]; then
        COMPOSE_ARGS+=(-f "$PHOTOS_OVERRIDE_FILE")
    fi
}

ensure_docker() {
    local compose_version

    if ! command -v docker >/dev/null 2>&1; then
        if prompt_yes_no "Docker is not installed. Install Docker Engine and Compose plugin now? This requires sudo and network access." "y"; then
            install_docker_engine
        else
            log_error "Docker is required for deployment."
            exit 1
        fi
    fi

    configure_docker_command

    if ! "${DOCKER_CMD[@]}" compose version >/dev/null 2>&1; then
        if prompt_yes_no "Docker Compose plugin is not available. Install/repair Docker packages now?" "y"; then
            install_docker_engine
            configure_docker_command
        fi
    fi

    if ! "${DOCKER_CMD[@]}" compose version >/dev/null 2>&1; then
        log_error "Docker Compose plugin is required. Please install it and run this script again."
        exit 1
    fi

    log_info "Docker: $(docker_cmd --version)"
    compose_version="$("${DOCKER_CMD[@]}" compose version)"
    log_info "Compose: $compose_version"
}

prompt_required_value() {
    local __resultvar="$1"
    local label="$2"
    local default="$3"
    local input_value=""

    while true; do
        if [ -n "$default" ]; then
            read -r -p "$label [$default]: " input_value
            input_value="${input_value:-$default}"
        else
            read -r -p "$label: " input_value
        fi

        input_value="$(trim "$input_value")"
        if [ -n "$input_value" ]; then
            printf -v "$__resultvar" '%s' "$input_value"
            return
        fi

        log_warn "$label cannot be empty."
    done
}

prompt_email() {
    local __resultvar="$1"
    local default="$2"
    local value=""

    while true; do
        prompt_required_value value "Admin email" "$default"
        if [[ "$value" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
            printf -v "$__resultvar" '%s' "$value"
            return
        fi
        log_warn "Please enter a valid email address."
    done
}

prompt_password() {
    local __resultvar="$1"
    local password="" confirm=""

    while true; do
        read -r -s -p "管理员密码（至少8位，留空则自动生成强密码）: " password
        echo ""

        if [ -z "$password" ]; then
            password="$(random_hex 12)"
            GENERATED_ADMIN_PASSWORD="$password"
            log_info "已生成强密码并保存到 .env 文件。"
            printf -v "$__resultvar" '%s' "$password"
            return
        fi

        if [ "${#password}" -lt 8 ]; then
            log_warn "密码至少需要 8 位字符，请重新输入。"
            continue
        fi

        read -r -s -p "确认管理员密码: " confirm
        echo ""
        if [ "$password" != "$confirm" ]; then
            log_warn "两次输入的密码不一致，请重新输入。"
            continue
        fi

        printf -v "$__resultvar" '%s' "$password"
        return
    done
}

run_initial_admin_wizard() {
    local admin_name admin_email admin_password
    local current_name current_email

    log_step "初始化管理员账号..."
    current_name="$(env_get DK_PHOTO_ADMIN_NAME "Administrator")"
    current_email="$(env_get DK_PHOTO_ADMIN_EMAIL "admin@example.com")"

    prompt_required_value admin_name "管理员昵称" "$current_name"
    prompt_email admin_email "$current_email"
    prompt_password admin_password

    env_set DK_PHOTO_ADMIN_NAME "$admin_name"
    env_set DK_PHOTO_ADMIN_EMAIL "$admin_email"
    env_set DK_PHOTO_ADMIN_PASSWORD "$admin_password"

    if [ "$admin_email" = "admin@example.com" ]; then
        log_warn "管理员邮箱仍为 admin@example.com，本地测试可以接受，但不建议用于生产环境。"
    fi
}

ensure_secret_key() {
    local current_secret new_secret

    current_secret="$(env_get DK_PHOTO_SECRET_KEY "")"
    if [ -z "$current_secret" ] || [ "$current_secret" = "replace-with-a-long-random-secret" ] || [ "$current_secret" = "dev-only-change-me" ]; then
        new_secret="$(random_hex 32)"
        env_set DK_PHOTO_SECRET_KEY "$new_secret"
        GENERATED_SECRET_KEY=1
        log_info "Generated DK_PHOTO_SECRET_KEY and saved it to .env."
    fi
}

is_default_admin_password() {
    local password
    password="$(env_get DK_PHOTO_ADMIN_PASSWORD "")"
    [ -z "$password" ] || [ "$password" = "change-me-now" ]
}

port_in_use() {
    local port="$1"

    if command -v ss >/dev/null 2>&1; then
        ss -ltn "sport = :${port}" | awk 'NR > 1 { found = 1 } END { exit found ? 0 : 1 }'
        return
    fi

    if command -v lsof >/dev/null 2>&1; then
        lsof -iTCP:"$port" -sTCP:LISTEN -Pn >/dev/null 2>&1
        return
    fi

    return 1
}

is_valid_port() {
    local port="$1"

    [[ "$port" =~ ^[0-9]+$ ]] && [ "$port" -ge 1 ] && [ "$port" -le 65535 ]
}

suggest_available_port() {
    local port="$1"

    if ! is_valid_port "$port"; then
        port=1024
    fi

    while port_in_use "$port"; do
        port=$((port + 1))
        if [ "$port" -gt 65535 ]; then
            log_error "No available port found."
            exit 1
        fi
    done

    printf '%s' "$port"
}

resolve_port() {
    local __resultvar="$1"
    local label="$2"
    local bind="$3"
    local env_key="$4"
    local port="$5"
    local reserved_port="${6:-}"
    local reserved_label="${7:-another service}"
    local input="" suggested

    if [ -z "$port" ]; then
        port="$(suggest_available_port 1024)"
    fi

    while true; do
        if ! is_valid_port "$port"; then
            log_warn "$env_key is not a valid port: $port"
            port="$(suggest_available_port 1024)"
        fi

        if [ -n "$reserved_port" ] && [ "$port" = "$reserved_port" ]; then
            log_warn "$label port ${port} is already reserved for ${reserved_label}."
            suggested="$(suggest_available_port "$((port + 1))")"
            if [ "$suggested" = "$reserved_port" ]; then
                suggested="$(suggest_available_port "$((suggested + 1))")"
            fi
            read -r -p "Enter another host port for ${label} [${suggested}]: " input
            input="${input:-$suggested}"
            input="$(trim "$input")"

            if ! is_valid_port "$input"; then
                log_warn "Please enter a port between 1 and 65535."
                continue
            fi

            port="$input"
            continue
        fi

        if ! port_in_use "$port"; then
            env_set "$env_key" "$port"
            printf -v "$__resultvar" '%s' "$port"
            log_info "$label port available: ${bind}:${port}"
            return
        fi

        suggested="$(suggest_available_port "$((port + 1))")"
        log_warn "$label port ${port} is already in use on the host."
        read -r -p "Enter another host port for ${label} [${suggested}]: " input
        input="${input:-$suggested}"
        input="$(trim "$input")"

        if ! is_valid_port "$input"; then
            log_warn "Please enter a port between 1 and 65535."
            continue
        fi

        port="$input"
    done
}

yaml_quote() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '"%s"' "$value"
}

expand_host_path() {
    local path="$1"

    if [ "$path" = "~" ] || [[ "$path" == "~/"* ]]; then
        path="${HOME}${path:1}"
    fi

    if [ -d "$path" ]; then
        (cd "$path" && pwd -P)
        return
    fi

    printf '%s' "$path"
}

suggest_mount_name() {
    local path="$1"
    local name

    name="$(basename "$path")"
    name="${name:-photos}"
    name="$(printf '%s' "$name" | tr -cs 'A-Za-z0-9_.-' '-' | sed 's/^-*//; s/-*$//; s/--*/-/g')"
    printf '%s' "${name:-photos}"
}

is_valid_mount_name() {
    local name="$1"

    [[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$ ]] && [ "$name" != "." ] && [ "$name" != ".." ]
}

ensure_mounts_file() {
    if [ ! -f "$PHOTO_MOUNTS_FILE" ]; then
        : > "$PHOTO_MOUNTS_FILE"
    fi
}

mount_name_exists() {
    local needle="$1"
    local name host

    [ -f "$PHOTO_MOUNTS_FILE" ] || return 1
    while IFS=$'\t' read -r name host || [ -n "${name}${host}" ]; do
        case "$name" in ""|\#*) continue ;; esac
        [ "$name" = "$needle" ] && return 0
    done < "$PHOTO_MOUNTS_FILE"
    return 1
}

mount_host_exists() {
    local needle="$1"
    local name host

    [ -f "$PHOTO_MOUNTS_FILE" ] || return 1
    while IFS=$'\t' read -r name host || [ -n "${name}${host}" ]; do
        case "$name" in ""|\#*) continue ;; esac
        [ "$host" = "$needle" ] && return 0
    done < "$PHOTO_MOUNTS_FILE"
    return 1
}

unique_mount_name() {
    local base="$1"
    local name index

    name="$base"
    index=2
    while mount_name_exists "$name"; do
        name="${base}-${index}"
        index=$((index + 1))
    done
    printf '%s' "$name"
}

append_photo_mount() {
    local name="$1"
    local host_path="$2"

    ensure_mounts_file
    printf '%s\t%s\n' "$name" "$host_path" >> "$PHOTO_MOUNTS_FILE"
}

count_photo_mounts() {
    local count=0
    local name host

    [ -f "$PHOTO_MOUNTS_FILE" ] || {
        printf '0'
        return
    }

    while IFS=$'\t' read -r name host || [ -n "${name}${host}" ]; do
        case "$name" in ""|\#*) continue ;; esac
        [ -n "$host" ] || continue
        count=$((count + 1))
    done < "$PHOTO_MOUNTS_FILE"

    printf '%s' "$count"
}

generate_photos_override() {
    local tmp name host target

    tmp="$(mktemp)"
    {
        printf '# This file is generated by deploy.sh. Do not edit it by hand.\n'
        printf '# Use: bash deploy.sh photos\n'
        printf 'services:\n'
    } > "$tmp"

    if [ "$(count_photo_mounts)" -eq 0 ]; then
        printf '  backend: {}\n' >> "$tmp"
    else
        {
            printf '  backend:\n'
            printf '    volumes:\n'
        } >> "$tmp"
        while IFS=$'\t' read -r name host || [ -n "${name}${host}" ]; do
            case "$name" in ""|\#*) continue ;; esac
            [ -n "$host" ] || continue
            target="/photos/${name}"
            {
                printf '      - type: bind\n'
                printf '        source: %s\n' "$(yaml_quote "$host")"
                printf '        target: %s\n' "$(yaml_quote "$target")"
                printf '        read_only: true\n'
            } >> "$tmp"
        done < "$PHOTO_MOUNTS_FILE"
    fi

    mv "$tmp" "$PHOTOS_OVERRIDE_FILE"
    refresh_compose_args
}

migrate_legacy_photos_path() {
    local legacy_path name default_name

    [ -f ".env" ] || return 0
    legacy_path="$(env_get PHOTOS_PATH "")"
    legacy_path="$(trim "$legacy_path")"
    [ -n "$legacy_path" ] || return 0

    legacy_path="$(expand_host_path "$legacy_path")"
    if [ ! -d "$legacy_path" ]; then
        log_warn "旧 PHOTOS_PATH 指向的目录不存在，未迁移: $legacy_path"
        return 0
    fi

    if mount_host_exists "$legacy_path"; then
        return 0
    fi

    default_name="$(suggest_mount_name "$legacy_path")"
    if [ "$default_name" = "photos" ]; then
        default_name="default"
    fi
    name="$(unique_mount_name "$default_name")"
    append_photo_mount "$name" "$legacy_path"
    log_warn "已将旧 PHOTOS_PATH 迁移为照片挂载: ${legacy_path} -> /photos/${name}"
}

list_photo_mounts() {
    local name host status
    local index=1

    log_step "当前照片目录挂载"
    if [ "$(count_photo_mounts)" -eq 0 ]; then
        log_info "尚未配置照片目录。容器内 /photos 会存在，但暂时没有外部目录。"
        return
    fi

    while IFS=$'\t' read -r name host || [ -n "${name}${host}" ]; do
        case "$name" in ""|\#*) continue ;; esac
        [ -n "$host" ] || continue
        if [ -d "$host" ] && [ -r "$host" ]; then
            status="目录可读"
        elif [ -d "$host" ]; then
            status="目录存在，但当前用户不可读"
        else
            status="不存在或不是目录"
        fi
        printf '  %s) %s -> /photos/%s (%s)\n' "$index" "$host" "$name" "$status"
        index=$((index + 1))
    done < "$PHOTO_MOUNTS_FILE"
}

add_photo_mount() {
    local host_path default_name mount_name input

    log_step "添加照片目录挂载"
    prompt_required_value host_path "宿主机照片目录" ""
    host_path="$(expand_host_path "$(trim "$host_path")")"

    if [ ! -d "$host_path" ]; then
        log_warn "目录不存在: $host_path"
        if prompt_yes_no "是否创建这个目录?" "n"; then
            mkdir -p "$host_path"
        else
            log_error "已取消添加。"
            return
        fi
    fi

    if [ ! -r "$host_path" ]; then
        log_warn "当前用户无法读取此目录，Docker 容器也可能无法读取: $host_path"
    fi

    if mount_host_exists "$host_path"; then
        log_warn "这个宿主机目录已经在挂载清单中。"
        return
    fi

    default_name="$(unique_mount_name "$(suggest_mount_name "$host_path")")"
    while true; do
        read -r -p "容器内显示名称 [/photos/${default_name}]: " input
        mount_name="$(trim "${input:-$default_name}")"

        if ! is_valid_mount_name "$mount_name"; then
            log_warn "名称只能使用英文字母、数字、点、下划线和短横线，并且最长 64 个字符。"
            continue
        fi
        if mount_name_exists "$mount_name"; then
            log_warn "/photos/${mount_name} 已存在，请换一个名称。"
            continue
        fi
        break
    done

    append_photo_mount "$mount_name" "$host_path"
    generate_photos_override
    log_info "已添加: ${host_path} -> /photos/${mount_name}"
    log_info "在 DK Photo 管理后台添加图库时，请选择容器内路径 /photos/${mount_name}。"
}

delete_photo_mount() {
    local name host target tmp found line_name line_host

    log_step "删除照片目录挂载"
    if [ "$(count_photo_mounts)" -eq 0 ]; then
        log_info "当前没有可删除的照片目录挂载。"
        return
    fi

    list_photo_mounts
    prompt_required_value target "要删除的容器内显示名称（例如 family）" ""
    target="$(trim "$target")"

    tmp="$(mktemp)"
    found=0
    while IFS=$'\t' read -r line_name line_host || [ -n "${line_name}${line_host}" ]; do
        case "$line_name" in
            ""|\#*)
                printf '%s\t%s\n' "$line_name" "$line_host" >> "$tmp"
                continue
                ;;
        esac
        if [ "$line_name" = "$target" ]; then
            found=1
            name="$line_name"
            host="$line_host"
            continue
        fi
        printf '%s\t%s\n' "$line_name" "$line_host" >> "$tmp"
    done < "$PHOTO_MOUNTS_FILE"

    if [ "$found" -eq 0 ]; then
        mv "$tmp" "$PHOTO_MOUNTS_FILE"
        log_warn "未找到 /photos/${target}。"
        return
    fi

    if prompt_yes_no "确认移除挂载 ${host} -> /photos/${name}? 原始文件不会被删除。" "n"; then
        mv "$tmp" "$PHOTO_MOUNTS_FILE"
        generate_photos_override
        log_info "已移除 /photos/${name}。"
    else
        rm -f "$tmp"
        log_info "已取消删除。"
    fi
}

check_photo_mounts() {
    local name host
    local has_problem=0

    log_step "检查照片目录"
    if [ "$(count_photo_mounts)" -eq 0 ]; then
        log_info "尚未配置照片目录。"
        return
    fi

    while IFS=$'\t' read -r name host || [ -n "${name}${host}" ]; do
        case "$name" in ""|\#*) continue ;; esac
        [ -n "$host" ] || continue
        if [ ! -d "$host" ]; then
            log_warn "/photos/${name}: 宿主机目录不存在: $host"
            has_problem=1
            continue
        fi
        if [ ! -r "$host" ]; then
            log_warn "/photos/${name}: 当前用户无法读取: $host"
            has_problem=1
            continue
        fi
        log_info "/photos/${name}: $host（目录可读）"
    done < "$PHOTO_MOUNTS_FILE"

    if [ "$has_problem" -eq 0 ]; then
        log_info "照片目录检查完成。"
    fi
}

apply_photo_mounts() {
    generate_photos_override
    ensure_docker

    log_step "应用照片目录挂载"
    if compose_cmd ps --quiet 2>/dev/null | grep -q .; then
        compose_cmd up -d
        log_info "已应用挂载配置。"
    else
        log_warn "当前没有运行中的 DK Photo 容器。下次初始化/更新部署时会自动应用挂载。"
    fi

    log_info "所有外部目录都会显示在容器内 /photos 下。"
}

manage_photo_mounts() {
    local choice

    cd "$SCRIPT_DIR"
    refresh_compose_args
    ensure_mounts_file
    if [ -f ".env" ]; then
        migrate_legacy_photos_path
    else
        log_warn "未检测到 .env。建议先运行初始化部署；也可以先维护挂载清单，部署时会自动应用。"
    fi
    generate_photos_override

    while true; do
        echo ""
        echo "照片目录挂载管理"
        echo "1) 添加目录"
        echo "2) 删除目录"
        echo "3) 列出目录"
        echo "4) 检查目录"
        echo "5) 应用并重启容器"
        echo "0) 返回"
        read -r -p "请选择 [1-5,0]: " choice
        case "$choice" in
            1) add_photo_mount ;;
            2) delete_photo_mount ;;
            3) list_photo_mounts ;;
            4) check_photo_mounts ;;
            5) apply_photo_mounts ;;
            0) return ;;
            *) log_warn "请输入 0-5。" ;;
        esac
    done
}

show_current_config() {
    local frontend_port backend_port app_data_path

    cd "$SCRIPT_DIR"
    refresh_compose_args
    echo ""
    log_step "当前配置"
    if [ -f ".env" ]; then
        frontend_port="$(env_get FRONTEND_PORT "8080")"
        backend_port="$(env_get BACKEND_PORT "8000")"
        app_data_path="$(env_get APP_DATA_PATH "./data")"
        echo "  数据目录:       ${app_data_path}"
        echo "  前端端口:       ${frontend_port}"
        echo "  后端端口:       ${backend_port}"
    else
        log_warn ".env 尚未创建。"
    fi
    echo "  Compose 命令:   $(compose_display)"
    list_photo_mounts
}

show_main_menu() {
    local choice

    while true; do
        echo ""
        echo "DK Photo 部署脚本"
        echo "1) 初始化/更新部署"
        echo "2) 管理照片目录挂载"
        echo "3) 查看当前配置"
        echo "0) 退出"
        read -r -p "请选择 [1-3,0]: " choice

        case "$choice" in
            1) run_deploy; return ;;
            2) manage_photo_mounts ;;
            3) show_current_config ;;
            0) exit 0 ;;
            *) log_warn "请输入 0-3。" ;;
        esac
    done
}

show_usage() {
    printf '%s\n' \
        "Usage: bash deploy.sh [command]" \
        "" \
        "Commands:" \
        "  deploy    初始化/更新部署" \
        "  photos    管理照片目录挂载" \
        "  config    查看当前配置" \
        "  help      显示帮助" \
        "" \
        "不带 command 运行时会显示交互菜单。"
}

run_deploy() {
ENV_CREATED=0
DB_EXISTS=0
GENERATED_ADMIN_PASSWORD=""
GENERATED_SECRET_KEY=0

# -----------------------------------------------------------
# 1. 检查前置依赖 (Check prerequisites)
# -----------------------------------------------------------
log_step "检查前置依赖..."
cd "$SCRIPT_DIR"
log_info "Project directory: $SCRIPT_DIR"
refresh_compose_args

ensure_docker
ensure_command curl curl

# -----------------------------------------------------------
# 2. 创建 .env 配置文件 (Create .env if not exists)
# -----------------------------------------------------------
log_step "配置环境变量..."

if [ ! -f ".env" ]; then
    if [ ! -f ".env.example" ]; then
        log_error ".env.example not found. Cannot create default configuration."
        exit 1
    fi

    cp .env.example .env
    ENV_CREATED=1
    log_info "已从 .env.example 创建 .env 配置文件。"
else
    log_info ".env 文件已存在。"
fi

APP_DATA_PATH="$(env_get APP_DATA_PATH "./data")"
FRONTEND_BIND="$(env_get FRONTEND_BIND "0.0.0.0")"
FRONTEND_PORT="$(env_get FRONTEND_PORT "8080")"
BACKEND_BIND="$(env_get BACKEND_BIND "127.0.0.1")"
BACKEND_PORT="$(env_get BACKEND_PORT "8000")"

ensure_mounts_file
migrate_legacy_photos_path
generate_photos_override

if [ -f "${APP_DATA_PATH}/dk_photo.sqlite3" ]; then
    DB_EXISTS=1
fi

ensure_secret_key

if [ "$DB_EXISTS" -eq 0 ]; then
    if [ "$ENV_CREATED" -eq 1 ] || is_default_admin_password; then
        run_initial_admin_wizard
    elif prompt_yes_no "Database has not been initialized yet. Reconfigure initial admin account?" "n"; then
        run_initial_admin_wizard
    fi
else
    log_info "检测到已有数据库: ${APP_DATA_PATH}/dk_photo.sqlite3"
    log_info ".env 中的管理员配置不会覆盖已有账号。"

    if is_default_admin_password; then
        log_warn ".env 中的 DK_PHOTO_ADMIN_PASSWORD 仍为默认值。"
        if ! prompt_yes_no "Confirm that the existing admin password has already been changed in the app and continue?" "n"; then
            log_error "已中止。请修改管理员密码或重置数据库后再部署。"
            exit 1
        fi
    fi
fi

if [ "$GENERATED_SECRET_KEY" -eq 1 ]; then
    log_warn "密钥已更新，已有登录会话将失效。"
fi

# -----------------------------------------------------------
# 3. 创建数据目录 (Create data directories)
# -----------------------------------------------------------
log_step "创建数据目录..."

mkdir -p "$APP_DATA_PATH"
log_info "数据目录就绪: $APP_DATA_PATH"

if [ "$(count_photo_mounts)" -eq 0 ]; then
    log_warn "尚未配置外部照片目录。部署完成后可运行 bash deploy.sh photos 添加目录。"
else
    check_photo_mounts
fi

# -----------------------------------------------------------
# 4. 停止已有容器 (Stop existing containers)
# -----------------------------------------------------------
log_step "停止已有容器（如有）..."

if compose_cmd ps --quiet 2>/dev/null | grep -q .; then
    compose_cmd down
    log_info "已有容器已停止。"
else
    log_info "没有运行中的容器。"
fi

# -----------------------------------------------------------
# 5. 检查宿主机端口占用 (Check host ports)
# -----------------------------------------------------------
log_step "检查端口占用..."

resolve_port FRONTEND_PORT frontend "$FRONTEND_BIND" FRONTEND_PORT "$FRONTEND_PORT"
resolve_port BACKEND_PORT backend "$BACKEND_BIND" BACKEND_PORT "$BACKEND_PORT" "$FRONTEND_PORT" frontend
log_info "前端通过 Docker 内部网络代理到 backend:8000，修改 BACKEND_PORT 仅影响宿主机直接访问后端。"

# -----------------------------------------------------------
# 6. 构建并启动服务 (Build and start)
# -----------------------------------------------------------
log_step "构建并启动服务..."

compose_cmd up -d --build

# -----------------------------------------------------------
# 7. 等待服务就绪 (Wait for services to be ready)
# -----------------------------------------------------------
log_step "等待服务就绪..."

MAX_WAIT=60
WAITED=0
while [ "$WAITED" -lt "$MAX_WAIT" ]; do
    if curl -sf "http://localhost:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
        log_info "后端健康检查通过。"
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done

if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    log_warn "后端在 ${MAX_WAIT}s 内未就绪，请检查日志: $(compose_display) logs backend"
fi

# -----------------------------------------------------------
# 8. 展示部署结果 (Show status / 访问地址)
# -----------------------------------------------------------
log_step "部署完成！"

echo ""
compose_cmd ps
echo ""

admin_name="$(env_get DK_PHOTO_ADMIN_NAME "Administrator")"
admin_email="$(env_get DK_PHOTO_ADMIN_EMAIL "admin@example.com")"

# 获取局域网和公网 IP
LOCAL_IP="$(get_local_ip)"
PUBLIC_IP="$(get_public_ip)"

log_info "DK Photo 已成功启动！"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📸 访问相册页面"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  本机访问:    http://localhost:${FRONTEND_PORT}"
echo "  局域网访问:  http://${LOCAL_IP}:${FRONTEND_PORT}"
if [ -n "$PUBLIC_IP" ]; then
    echo "  公网访问:    http://${PUBLIC_IP}:${FRONTEND_PORT}"
else
    echo "  公网访问:    （未能获取公网 IP，请检查网络）"
fi
echo ""
echo "  后端 API:    http://localhost:${BACKEND_PORT}"
echo "  API 文档:    http://localhost:${BACKEND_PORT}/docs"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  👤 管理员账号"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  昵称:  ${admin_name}"
echo "  邮箱:  ${admin_email}"
if [ -n "$GENERATED_ADMIN_PASSWORD" ]; then
    echo "  密码:  ${GENERATED_ADMIN_PASSWORD}（已存入 .env）"
else
    echo "  密码:  部署时填写的密码（已存入 .env）"
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📋 常用命令"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  $(compose_display) ps              # 查看服务状态"
echo "  $(compose_display) logs -f         # 查看全部日志"
echo "  $(compose_display) logs -f backend # 查看后端日志"
echo "  $(compose_display) restart         # 重启服务"
echo "  $(compose_display) down            # 停止并删除容器"
echo "  $(compose_display) up -d --build   # 重建并启动"
echo ""
log_info "使用上方显示的管理员账号登录相册。"

# 公网访问提示
if [ -n "$PUBLIC_IP" ]; then
    log_warn "如果通过公网访问，请确保路由器已配置端口转发 ${FRONTEND_PORT}，且防火墙已放行。"
fi
}

main() {
    cd "$SCRIPT_DIR"
    refresh_compose_args

    case "${1:-}" in
        "")
            show_main_menu
            ;;
        deploy|init|up)
            run_deploy
            ;;
        photos|mounts)
            manage_photo_mounts
            ;;
        config|status)
            show_current_config
            ;;
        help|-h|--help)
            show_usage
            ;;
        *)
            log_error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
