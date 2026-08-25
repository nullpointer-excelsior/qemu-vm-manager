#!/bin/bash

set -euo pipefail
shopt -s extglob

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
ZSHRC_FILE="${HOME}/.zshrc"

if [[ ! -f "$ENV_FILE" ]]; then
    printf 'Env file not found: %s\n' "$ENV_FILE" >&2
    exit 1
fi

touch "$ZSHRC_FILE"

while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "${line##+([[:space:]])}" || "${line##+([[:space:]])}" == \#* ]] && continue

    key="${line%%=*}"
    value="${line#*=}"
    key="${key##+([[:space:]])}"
    key="${key%%+([[:space:]])}"

    [[ "$key" == export\ * ]] && key="${key#export }"

    if [[ ! "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
        printf 'Invalid environment variable: %s\n' "$key" >&2
        continue
    fi

    if grep -qE "^[[:space:]]*(export[[:space:]]+)?${key}=" "$ZSHRC_FILE"; then
        printf '%s is already defined in %s, skipping.\n' "$key" "$ZSHRC_FILE"
        continue
    fi

    printf 'export %s=%s\n' "$key" "$value" >> "$ZSHRC_FILE"
    printf '%s added to %s.\n' "$key" "$ZSHRC_FILE"
done < "$ENV_FILE"
