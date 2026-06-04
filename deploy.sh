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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUDO=()
DOCKER_CMD=(docker)
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
    "${DOCKER_CMD[@]}" compose "$@"
}

compose_display() {
    if [ "${DOCKER_CMD[0]}" = "sudo" ]; then
        printf 'sudo docker compose'
    else
        printf 'docker compose'
    fi
}

ensure_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        if prompt_yes_no "Docker is not installed. Install Docker Engine and Compose plugin now? This requires sudo and network access." "y"; then
            install_docker_engine
        else
            log_error "Docker is required for deployment."
            exit 1
        fi
    fi

    configure_docker_command

    if ! compose_cmd version >/dev/null 2>&1; then
        if prompt_yes_no "Docker Compose plugin is not available. Install/repair Docker packages now?" "y"; then
            install_docker_engine
            configure_docker_command
        fi
    fi

    if ! compose_cmd version >/dev/null 2>&1; then
        log_error "Docker Compose plugin is required. Please install it and run this script again."
        exit 1
    fi

    log_info "Docker: $(docker_cmd --version)"
    log_info "Compose: $(compose_cmd version)"
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
        read -r -s -p "Admin password (at least 8 chars; leave blank to auto-generate): " password
        echo ""

        if [ -z "$password" ]; then
            password="$(random_hex 12)"
            GENERATED_ADMIN_PASSWORD="$password"
            log_info "Generated a strong admin password and saved it to .env."
            printf -v "$__resultvar" '%s' "$password"
            return
        fi

        if [ "${#password}" -lt 8 ]; then
            log_warn "Password must be at least 8 characters."
            continue
        fi

        read -r -s -p "Confirm admin password: " confirm
        echo ""
        if [ "$password" != "$confirm" ]; then
            log_warn "Passwords do not match."
            continue
        fi

        printf -v "$__resultvar" '%s' "$password"
        return
    done
}

run_initial_admin_wizard() {
    local admin_name admin_email admin_password
    local current_name current_email

    log_step "Initial admin setup..."
    current_name="$(env_get DK_PHOTO_ADMIN_NAME "Administrator")"
    current_email="$(env_get DK_PHOTO_ADMIN_EMAIL "admin@example.com")"

    prompt_required_value admin_name "Admin display name" "$current_name"
    prompt_email admin_email "$current_email"
    prompt_password admin_password

    env_set DK_PHOTO_ADMIN_NAME "$admin_name"
    env_set DK_PHOTO_ADMIN_EMAIL "$admin_email"
    env_set DK_PHOTO_ADMIN_PASSWORD "$admin_password"

    if [ "$admin_email" = "admin@example.com" ]; then
        log_warn "Admin email is still admin@example.com. This is acceptable for local testing, but not recommended for production."
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

# -----------------------------------------------------------
# 1. Check prerequisites
# -----------------------------------------------------------
log_step "Checking prerequisites..."
cd "$SCRIPT_DIR"
log_info "Project directory: $SCRIPT_DIR"

ensure_docker
ensure_command curl curl

# -----------------------------------------------------------
# 2. Create .env if not exists
# -----------------------------------------------------------
log_step "Setting up environment configuration..."

if [ ! -f ".env" ]; then
    if [ ! -f ".env.example" ]; then
        log_error ".env.example not found. Cannot create default configuration."
        exit 1
    fi

    cp .env.example .env
    ENV_CREATED=1
    log_info "Created .env from .env.example."
else
    log_info ".env file already exists."
fi

PHOTOS_PATH="$(env_get PHOTOS_PATH "./photos")"
APP_DATA_PATH="$(env_get APP_DATA_PATH "./data")"
FRONTEND_BIND="$(env_get FRONTEND_BIND "0.0.0.0")"
FRONTEND_PORT="$(env_get FRONTEND_PORT "8080")"
BACKEND_BIND="$(env_get BACKEND_BIND "127.0.0.1")"
BACKEND_PORT="$(env_get BACKEND_PORT "8000")"

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
    log_info "Existing database detected: ${APP_DATA_PATH}/dk_photo.sqlite3"
    log_info "Initial admin settings in .env will not overwrite existing users."

    if is_default_admin_password; then
        log_warn "DK_PHOTO_ADMIN_PASSWORD is still the default value in .env."
        if ! prompt_yes_no "Confirm that the existing admin password has already been changed in the app and continue?" "n"; then
            log_error "Aborted. Please change the admin password or reset the database before deploying."
            exit 1
        fi
    fi
fi

if [ "$GENERATED_SECRET_KEY" -eq 1 ]; then
    log_warn "Existing login sessions will be invalidated if this was an existing deployment."
fi

if [ "${PHOTOS_PATH:0:1}" != "/" ]; then
    log_warn "PHOTOS_PATH is relative (${PHOTOS_PATH}). This is fine for quick testing; use an absolute path for production."
fi

# -----------------------------------------------------------
# 3. Create data directories
# -----------------------------------------------------------
log_step "Creating data directories..."

mkdir -p "$APP_DATA_PATH"
log_info "Data directory ready: $APP_DATA_PATH"

if [ ! -d "$PHOTOS_PATH" ]; then
    mkdir -p "$PHOTOS_PATH"
    log_warn "Photos directory created: $PHOTOS_PATH"
    log_warn "Place your media files here, or update PHOTOS_PATH in .env."
else
    photo_count="$(find "$PHOTOS_PATH" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" -o -iname "*.gif" -o -iname "*.mp4" -o -iname "*.mov" -o -iname "*.webm" -o -iname "*.avi" -o -iname "*.mkv" \) 2>/dev/null | wc -l || true)"
    photo_count="$(trim "$photo_count")"
    log_info "Photos directory ready: $PHOTOS_PATH (found $photo_count media files)"
fi

# -----------------------------------------------------------
# 4. Stop existing containers
# -----------------------------------------------------------
log_step "Stopping existing containers (if any)..."

if compose_cmd ps --quiet 2>/dev/null | grep -q .; then
    compose_cmd down
    log_info "Existing containers stopped."
else
    log_info "No running containers found."
fi

# -----------------------------------------------------------
# 5. Check host ports after stopping our own containers
# -----------------------------------------------------------
log_step "Checking host ports..."

resolve_port FRONTEND_PORT frontend "$FRONTEND_BIND" FRONTEND_PORT "$FRONTEND_PORT"
resolve_port BACKEND_PORT backend "$BACKEND_BIND" BACKEND_PORT "$BACKEND_PORT" "$FRONTEND_PORT" frontend
log_info "Frontend API requests use the Docker network proxy http://backend:8000, so changing BACKEND_PORT only affects direct host access."

# -----------------------------------------------------------
# 6. Build and start
# -----------------------------------------------------------
log_step "Building and starting services..."

compose_cmd up -d --build

# -----------------------------------------------------------
# 7. Wait for services to be healthy
# -----------------------------------------------------------
log_step "Waiting for services to be ready..."

MAX_WAIT=60
WAITED=0
while [ "$WAITED" -lt "$MAX_WAIT" ]; do
    if curl -sf "http://localhost:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
        log_info "Backend health check passed."
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done

if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    log_warn "Backend did not become healthy within ${MAX_WAIT}s. Check logs: $(compose_display) logs backend"
fi

# -----------------------------------------------------------
# 8. Show status
# -----------------------------------------------------------
log_step "Deployment complete!"

echo ""
compose_cmd ps
echo ""

admin_name="$(env_get DK_PHOTO_ADMIN_NAME "Administrator")"
admin_email="$(env_get DK_PHOTO_ADMIN_EMAIL "admin@example.com")"

log_info "DK Photo is now running!"
echo ""
echo "  Frontend (local):   http://localhost:${FRONTEND_PORT}"
if [ "$FRONTEND_BIND" = "0.0.0.0" ]; then
    echo "  Frontend (server):  http://<server-ip>:${FRONTEND_PORT}"
fi
echo "  Backend (local):    http://localhost:${BACKEND_PORT}"
echo "  API Docs (local):   http://localhost:${BACKEND_PORT}/docs"
echo ""
echo "Admin account:"
echo "  Name:   ${admin_name}"
echo "  Email:  ${admin_email}"
if [ -n "$GENERATED_ADMIN_PASSWORD" ]; then
    echo "  Password: ${GENERATED_ADMIN_PASSWORD}"
    echo "  The generated password is also stored in .env."
else
    echo "  Password: the value you entered during setup, or the existing value in .env."
fi
echo ""
echo "Useful commands:"
echo "  $(compose_display) ps              # View service status"
echo "  $(compose_display) logs -f         # Follow all logs"
echo "  $(compose_display) logs -f backend # Follow backend logs"
echo "  $(compose_display) restart         # Restart services"
echo "  $(compose_display) down            # Stop and remove containers"
echo "  $(compose_display) up -d --build   # Rebuild and restart"
echo ""
log_info "Log in with the admin account shown above."
