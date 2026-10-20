#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
PROJECT_DIR="$PWD"
ENV_FILE="$PROJECT_DIR/deploy/.env"
SUCCESS_FILE="$PROJECT_DIR/deploy/.installed"
export COMPOSE_PARALLEL_LIMIT=1

fail() { printf '部署停止：%s\n' "$*" >&2; exit 1; }
config_value() { sed -n "s/^$1=//p" "$ENV_FILE"; }
compose() { docker compose --project-name ai-rag-demo --env-file "$ENV_FILE" -f "$PROJECT_DIR/compose.yaml" "$@"; }

if [[ "${1:-}" == "--check" && $# == 1 ]]; then
    command -v docker >/dev/null || fail "需要 Docker CLI 才能检查 Compose。"
    [[ -f "$ENV_FILE" ]] || ENV_FILE="$PROJECT_DIR/deploy/.env.example"
    compose config --quiet
    printf 'Compose 配置检查通过。\n'
    exit 0
fi
[[ $# == 0 ]] || fail "用法：bash deploy.sh [--check]"
[[ "$(uname -s)" == Linux ]] || fail "部署脚本只在 Linux 服务器上运行；本机可用 --check 检查配置。"
if [[ "$EUID" != 0 ]]; then
    command -v sudo >/dev/null || fail "请使用 root 执行。"
    exec sudo bash "$PROJECT_DIR/deploy.sh"
fi
command -v flock >/dev/null || fail "缺少 flock，请安装 util-linux。"
exec 9> "$PROJECT_DIR/deploy/.deploy.lock"
flock -n 9 || fail "另一个部署进程正在运行。"
trap 'printf "部署失败，已有数据不会自动删除。检查：sudo docker compose --env-file deploy/.env logs --tail=60\n" >&2' ERR

install_docker() {
    [[ -r /etc/os-release ]] || fail "无法识别系统。"
    . /etc/os-release
    case "$ID" in ubuntu|debian) ;; *) fail "自动安装仅支持 Ubuntu/Debian；其他系统请先安装 Docker Engine 和 Compose 插件。" ;; esac
    for package in docker.io docker-compose docker-compose-v2 podman-docker containerd runc; do
        if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
            fail "发现已有 $package，不自动卸载；请先处理与 Docker 官方软件包的冲突。"
        fi
    done
    apt-get update
    apt-get install -y ca-certificates curl openssl
    install -m 0755 -d /etc/apt/keyrings
    source "$PROJECT_DIR/deploy/docker-repository.sh"
    configure_docker_repository "$ID" "${UBUNTU_CODENAME:-$VERSION_CODENAME}" \
        "$(dpkg --print-architecture)" /etc/apt/keyrings/docker.asc /etc/apt/sources.list.d/docker.sources
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
    install_docker
fi
docker compose version >/dev/null || fail "Docker 已安装但缺少 Compose 插件，请先安装 docker-compose-plugin。"
if ! command -v openssl >/dev/null || ! command -v curl >/dev/null; then
    command -v apt-get >/dev/null || fail "请先安装 openssl 和 curl。"
    apt-get update
    apt-get install -y openssl curl
fi
if ! docker info >/dev/null 2>&1; then
    systemctl enable --now docker
fi
docker info >/dev/null

# A lost credentials file must never silently produce new passwords for old volumes.
first_install=true
[[ ! -f "$SUCCESS_FILE" ]] || first_install=false
if [[ ! -e "$ENV_FILE" ]]; then
    existing_volumes="$(docker volume ls --filter label=com.docker.compose.project=ai-rag-demo -q)"
    [[ -z "$existing_volumes" ]] || fail "已有本项目数据卷但 deploy/.env 丢失，请恢复原配置，禁止重新生成凭据。"
    umask 077
    {
        printf 'HTTP_BIND=0.0.0.0\nHTTP_PORT=80\n'
        for key in MYSQL_ROOT_PASSWORD MYSQL_PASSWORD POSTGRES_PASSWORD JWT_SECRET DEMO_PASSWORD; do
            printf '%s=%s\n' "$key" "$(openssl rand -hex 16)"
        done
    } > "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"
for key in MYSQL_ROOT_PASSWORD MYSQL_PASSWORD POSTGRES_PASSWORD JWT_SECRET DEMO_PASSWORD; do
    value="$(config_value "$key")"
    [[ "$value" =~ ^[a-f0-9]{32}$ ]] || fail "$key 必须为 32 位小写十六进制值，请保留生成的凭据。"
done
port="$(config_value HTTP_PORT)"
[[ "$port" =~ ^[0-9]{1,5}$ ]] && ((10#$port >= 1 && 10#$port <= 65535)) || fail "HTTP_PORT 不合法。"
umask 077
mkdir -p deploy/secrets
chmod 700 deploy/secrets
password="$(config_value DEMO_PASSWORD)"
auth_hash="$(printf '%s\n' "$password" | openssl passwd -apr1 -stdin)"
# Nginx workers need read access to this file inside the read-only mount.
printf 'demo:%s\n' "$auth_hash" > deploy/secrets/demo.htpasswd
chmod 644 deploy/secrets/demo.htpasswd
compose config --quiet

printf '正在串行构建镜像，首次运行需要下载依赖……\n'
compose build backend
compose build web
printf '正在启动服务并等待数据库初始化……\n'
compose up -d --wait --wait-timeout 900

# Exercise the proxy on every run; only check the generated login on first install.
curl --fail --silent --show-error --max-time 30 --user "demo:$password" \
    "http://127.0.0.1:$port/api/" | compose exec -T backend python -c \
    'import json,sys; assert json.load(sys.stdin).get("code")=="200", "接口验收失败"'
if "$first_install"; then
response="$(curl --fail --silent --show-error --max-time 30 \
    --user "demo:$password" -H 'Content-Type: application/json' \
    --data "{\"username\":\"admin\",\"password\":\"$password\"}" \
    "http://127.0.0.1:$port/api/login")"
printf '%s' "$response" | compose exec -T backend python -c \
    'import json,sys; r=json.load(sys.stdin); assert r.get("code")=="200" and r.get("data",{}).get("token"), "登录验收失败，请检查数据库凭据和日志"'
fi
compose ps
printf 'Deployment and initial login verified.\n' > "$SUCCESS_FILE"
printf '\n部署与接口检查完成。\n访问：http://服务器公网IP:%s\n浏览器访问账号：demo\n应用登录账号：admin\n访问密码与应用初始密码：%s\n如果曾修改应用密码，请使用修改后的密码登录。\n凭据保存在 deploy/.env，请妥善保管。\n请在云服务器安全组放行 TCP %s，优先限制访问来源 IP。\n进入模型配置页面填写自己的 API Key，才能调用真实模型。\n' "$port" "$password" "$port"
