#!/usr/bin/env bash
#
# Деплой voyra-weather-services (data-service, tile-service, grid-service).
#
#   sudo ./deploy.sh          — первый деплой или обновление (git pull, зависимости, перезапуск)
#   ./deploy.sh nginx         — напечатать записи для конфигурации nginx
#
# Скрипт идемпотентен: повторный запуск обновляет код и зависимости и перезапускает службы.
# Всё, что можно, переопределяется переменными окружения (см. блок «Настройки»).
#
# Требования: Ubuntu/Debian с systemd, Python 3.12 (+ python3.12-venv), git,
# SSH-ключ пользователя APP_USER с доступом к репозиторию (deploy key).

set -Eeuo pipefail

# ----------------------------------------------------------------------------
# Настройки
# ----------------------------------------------------------------------------
REPO_URL="${REPO_URL:-git@github.com:x3mart/voyra-weather-services.git}"
BRANCH="${BRANCH:-}"                         # пусто = ветка по умолчанию репозитория

APP_USER="${APP_USER:-${SUDO_USER:-x3mart}}" # от этого пользователя работают службы
APP_GROUP="${APP_GROUP:-$APP_USER}"
APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6 || true)"
APP_DIR="${APP_DIR:-${APP_HOME:-/home/$APP_USER}/voyra-weather-services}"

PYTHON_BIN="${PYTHON_BIN:-python3.12}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

WORKERS=1                                    # по одному воркеру на службу

DATA_DIR_NAME="data-service"
TILE_DIR_NAME="tile-service"
GRID_DIR_NAME="grid-service"

DATA_CMD="${DATA_CMD:-main.py}"              # data-service запускается как: python main.py
TILE_APP="${TILE_APP:-main:app}"             # tile-service: uvicorn main:app
GRID_APP="${GRID_APP:-main:app}"             # grid-service: uvicorn main:app

TILE_SOCKET="${TILE_SOCKET:-/run/voyra-tile.sock}"
GRID_SOCKET="${GRID_SOCKET:-/run/voyra-grid.sock}"
NGINX_GROUP="${NGINX_GROUP:-www-data}"       # группа nginx (на RHEL-подобных: nginx)

UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"

# ----------------------------------------------------------------------------
# Утилиты
# ----------------------------------------------------------------------------
log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARN:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

as_user() { sudo -u "$APP_USER" -H "$@"; }

# при первом подключении к github.com принимаем ключ хоста, дальше он проверяется
git_as_user() {
    as_user env GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=accept-new" git "$@"
}

# ----------------------------------------------------------------------------
# Проверки
# ----------------------------------------------------------------------------
check_prereqs() {
    [[ $EUID -eq 0 ]] || die "Запустите через sudo: sudo $0"
    id "$APP_USER" >/dev/null 2>&1 || die "Пользователь $APP_USER не существует (задайте APP_USER=...)"
    getent group "$NGINX_GROUP" >/dev/null || die "Группа $NGINX_GROUP не найдена (задайте NGINX_GROUP=..., для nginx на RHEL это 'nginx')"
    command -v git >/dev/null || die "git не установлен"
    command -v systemctl >/dev/null || die "Нужен systemd"

    if ! command -v "$PYTHON_BIN" >/dev/null; then
        die "$PYTHON_BIN не найден. Ubuntu 24.04: apt install python3.12 python3.12-venv. Для более старых версий нужен PPA deadsnakes."
    fi
    if ! "$PYTHON_BIN" -c 'import ensurepip, venv' 2>/dev/null; then
        log "Устанавливаю python${PYTHON_VERSION}-venv"
        apt-get update -qq && apt-get install -y -qq "python${PYTHON_VERSION}-venv" \
            || die "Не удалось установить python${PYTHON_VERSION}-venv"
    fi
}

# ----------------------------------------------------------------------------
# Репозиторий
# ----------------------------------------------------------------------------
sync_repo() {
    if [[ -d "$APP_DIR/.git" ]]; then
        log "Обновляю репозиторий в $APP_DIR"
        git_as_user -C "$APP_DIR" fetch --prune origin
        [[ -z "$BRANCH" ]] || git_as_user -C "$APP_DIR" checkout "$BRANCH"
        git_as_user -C "$APP_DIR" pull --ff-only
    elif [[ -e "$APP_DIR" ]]; then
        die "$APP_DIR существует, но это не git-репозиторий"
    else
        log "Клонирую $REPO_URL в $APP_DIR"
        as_user mkdir -p "$(dirname "$APP_DIR")"
        local args=()
        [[ -z "$BRANCH" ]] || args+=(--branch "$BRANCH")
        git_as_user clone "${args[@]}" "$REPO_URL" "$APP_DIR" || die \
"Не удалось клонировать репозиторий. Проверьте, что у пользователя $APP_USER есть SSH-ключ
(ssh-keygen -t ed25519) и он добавлен в GitHub как deploy key репозитория."
    fi
}

# ----------------------------------------------------------------------------
# Виртуальные окружения
# ----------------------------------------------------------------------------
setup_venv() {
    local name="$1" dir="$APP_DIR/$1"
    [[ -d "$dir" ]] || die "Нет каталога $dir"
    [[ -f "$dir/requirements.txt" ]] || die "Нет $dir/requirements.txt"

    # окружение другой версии Python пересоздаём
    if [[ -x "$dir/venv/bin/python" ]]; then
        local have
        have="$("$dir/venv/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
        if [[ "$have" != "$PYTHON_VERSION" ]]; then
            warn "$name: venv на Python ${have:-?}, пересоздаю под $PYTHON_VERSION"
            rm -rf "$dir/venv"
        fi
    fi

    log "$name: окружение и зависимости"
    [[ -d "$dir/venv" ]] || as_user "$PYTHON_BIN" -m venv "$dir/venv"

    as_user bash -c '
        set -eo pipefail
        cd "$1"
        source venv/bin/activate
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    ' _ "$dir"
}

check_uvicorn() {
    local name="$1"
    "$APP_DIR/$name/venv/bin/python" -c 'import uvicorn' 2>/dev/null \
        || die "$name: в requirements.txt нет uvicorn, службе нечем запускаться"
}

# ----------------------------------------------------------------------------
# systemd: описание юнитов
# ----------------------------------------------------------------------------
render_data_service() {
cat <<EOF
[Unit]
Description=Voyra data-service (загрузка и подготовка прогнозов)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}/${DATA_DIR_NAME}
Environment=PYTHONUNBUFFERED=1
ExecStart=${APP_DIR}/${DATA_DIR_NAME}/venv/bin/python ${DATA_CMD}
Restart=always
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
}

# $1 имя (tile|grid)  $2 каталог  $3 приложение uvicorn  $4 путь сокета
render_api_service() {
cat <<EOF
[Unit]
Description=Voyra ${1}-service (uvicorn, ${WORKERS} воркер)
Requires=voyra-${1}.socket
After=network.target voyra-${1}.socket

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}/${2}
Environment=PYTHONUNBUFFERED=1
# сокет передаёт systemd (socket activation), файловый дескриптор 3
ExecStart=${APP_DIR}/${2}/venv/bin/uvicorn ${3} --fd 3 --workers ${WORKERS}
Restart=on-failure
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
}

render_api_socket() {
cat <<EOF
[Unit]
Description=Voyra ${1}-service socket

[Socket]
ListenStream=${2}
SocketUser=root
SocketGroup=${NGINX_GROUP}
SocketMode=0660

[Install]
WantedBy=sockets.target
EOF
}

write_units() {
    log "Создаю юниты systemd в $UNIT_DIR"
    render_data_service                                                   > "$UNIT_DIR/voyra-data.service"
    render_api_service tile "$TILE_DIR_NAME" "$TILE_APP" "$TILE_SOCKET"   > "$UNIT_DIR/voyra-tile.service"
    render_api_socket  tile "$TILE_SOCKET"                                > "$UNIT_DIR/voyra-tile.socket"
    render_api_service grid "$GRID_DIR_NAME" "$GRID_APP" "$GRID_SOCKET"   > "$UNIT_DIR/voyra-grid.service"
    render_api_socket  grid "$GRID_SOCKET"                                > "$UNIT_DIR/voyra-grid.socket"
    chmod 644 "$UNIT_DIR"/voyra-*.service "$UNIT_DIR"/voyra-*.socket
}

apply_systemd() {
    log "Запускаю службы"
    systemctl daemon-reload
    systemctl enable voyra-data.service \
                     voyra-tile.socket voyra-tile.service \
                     voyra-grid.socket voyra-grid.service >/dev/null
    systemctl start voyra-tile.socket voyra-grid.socket
    # restart, а не start: при обновлении подхватывается новый код.
    # Сокеты остаются открытыми, поэтому запросы nginx ждут в очереди, а не теряются.
    systemctl restart voyra-data.service voyra-tile.service voyra-grid.service
}

verify() {
    log "Проверяю состояние"
    sleep 3
    local failed=0 unit
    for unit in voyra-data.service voyra-tile.socket voyra-tile.service voyra-grid.socket voyra-grid.service; do
        if systemctl is-active --quiet "$unit"; then
            printf '  %-24s active\n' "$unit"
        else
            printf '  %-24s \033[1;31mFAILED\033[0m  (journalctl -u %s -n 50 --no-pager)\n' "$unit" "$unit"
            failed=1
        fi
    done
    return "$failed"
}

# ----------------------------------------------------------------------------
# nginx
# ----------------------------------------------------------------------------
print_nginx() {
cat <<EOF
# ---------------------------------------------------------------------------
# 1) контекст http { } — например, /etc/nginx/conf.d/voyra-weather.conf
# ---------------------------------------------------------------------------
upstream voyra_tile {
    server unix:${TILE_SOCKET};
    keepalive 16;
}

upstream voyra_grid {
    server unix:${GRID_SOCKET};
    keepalive 16;
}

# ---------------------------------------------------------------------------
# 2) внутри server { } вашего домена
# ---------------------------------------------------------------------------
# тайлы:  GET /tiles/{layer}/{z}/{x}/{y}.png
location /tiles/ {
    proxy_pass http://voyra_tile;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 30s;
}

# бинарные сетки и точки: поправьте префикс под реальные маршруты grid-service
location /grid/ {
    proxy_pass http://voyra_grid;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 30s;

    # сетки int16 хорошо сжимаются
    gzip on;
    gzip_types application/octet-stream;
    gzip_min_length 1024;
}

# после правки: sudo nginx -t && sudo systemctl reload nginx
EOF
}

# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
main() {
    case "${1:-deploy}" in
        nginx)  print_nginx; return 0 ;;
        deploy) ;;
        *)      die "Неизвестная команда '$1'. Использование: $0 [deploy|nginx]" ;;
    esac

    check_prereqs
    sync_repo

    local d
    for d in "$DATA_DIR_NAME" "$TILE_DIR_NAME" "$GRID_DIR_NAME"; do
        setup_venv "$d"
    done
    check_uvicorn "$TILE_DIR_NAME"
    check_uvicorn "$GRID_DIR_NAME"

    write_units
    apply_systemd

    if verify; then
        log "Готово. Записи для nginx: $0 nginx"
        echo "  Логи: journalctl -u voyra-data -u voyra-tile -u voyra-grid -f"
    else
        die "Часть служб не запустилась, см. сообщения выше"
    fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
