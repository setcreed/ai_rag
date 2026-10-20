#!/usr/bin/env bash

# Stage downloads beside their destinations so interrupted downloads are never installed.
# Existing configuration is reused only when it matches the official configuration.
configure_docker_repository() (
    set -Eeuo pipefail
    distro="$1" suite="$2" architecture="$3" key_file="$4" source_file="$5"
    key_temp="$(mktemp "${key_file}.XXXXXX")"
    source_temp=''
    trap 'rm -f -- "$key_temp" ${source_temp:+"$source_temp"}' EXIT
    source_temp="$(mktemp "${source_file}.XXXXXX")"
    curl --fail --silent --show-error --location --connect-timeout 15 --max-time 120 \
        "https://download.docker.com/linux/$distro/gpg" -o "$key_temp"
    [[ -s "$key_temp" ]] || { printf 'Docker 官方密钥下载为空。\n' >&2; exit 1; }
    cat > "$source_temp" <<EOF
Types: deb
URIs: https://download.docker.com/linux/$distro
Suites: $suite
Components: stable
Architectures: $architecture
Signed-By: $key_file
EOF
    for destination in "$key_file" "$source_file"; do
        staged="$key_temp"
        [[ "$destination" != "$source_file" ]] || staged="$source_temp"
        if [[ -e "$destination" ]] && ! cmp -s "$destination" "$staged"; then
            printf '已有 Docker 配置与预期不一致，保留原文件，请手动核对：%s\n' "$destination" >&2
            exit 1
        fi
    done
    chmod 644 "$key_temp" "$source_temp"
    [[ -e "$key_file" ]] || mv -- "$key_temp" "$key_file"
    [[ -e "$source_file" ]] || mv -- "$source_temp" "$source_file"
)
