#!/usr/bin/env bash

set -euo pipefail

readonly SSH_DIRECTORY="$HOME/.ssh"
readonly SSH_CONFIG_FILE="$SSH_DIRECTORY/config"

print_usage() {
  printf 'Uso: %s <nombre-de-cuenta>\n' "$(basename "$0")"
  printf 'Ejemplo: %s mi-cuenta\n' "$(basename "$0")"
}

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Se requiere el comando '$1'."
}

validate_account_name() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9-]*$ ]] || fail 'El nombre de cuenta solo puede contener letras, números y guiones, y no puede comenzar con un guion.'
}

remove_ssh_host() {
  local host_name="$1"
  local temporary_file

  [[ -f "$SSH_CONFIG_FILE" ]] || return

  temporary_file="$(mktemp)"
  python3 - "$SSH_CONFIG_FILE" "$temporary_file" "$host_name" <<'PYTHON'
import sys
from pathlib import Path

source_file = Path(sys.argv[1])
target_file = Path(sys.argv[2])
host_name = sys.argv[3]
lines = source_file.read_text().splitlines(keepends=True)
result = []
index = 0

while index < len(lines):
    if lines[index].strip() == f"Host {host_name}":
        index += 1
        while index < len(lines) and not lines[index].lstrip().startswith("Host "):
            index += 1
        continue
    result.append(lines[index])
    index += 1

target_file.write_text("".join(result))
PYTHON
  chmod 600 "$temporary_file"
  mv "$temporary_file" "$SSH_CONFIG_FILE"
}

confirm_removal() {
  local answer

  printf 'Esta acción eliminará las claves SSH y la configuración de la cuenta.\n'
  read -r -p 'Escribe el nombre de la cuenta para confirmar: ' answer
  [[ "$answer" == "$1" ]] || fail 'Confirmación no válida. No se eliminó nada.'
}

main() {
  [[ $# -eq 1 ]] || {
    print_usage >&2
    exit 1
  }

  local account_name="$1"
  local private_key_file
  local public_key_file
  local host_name

  require_command python3
  validate_account_name "$account_name"

  private_key_file="$SSH_DIRECTORY/github_$account_name"
  public_key_file="${private_key_file}.pub"
  host_name="github-$account_name"

  confirm_removal "$account_name"

  rm -f "$private_key_file" "$public_key_file"
  remove_ssh_host "$host_name"

  printf 'La cuenta local "%s" se eliminó correctamente.\n' "$account_name"
  printf 'Los repositorios locales no se eliminaron.\n'
  printf 'También elimina la clave pública correspondiente desde GitHub: Settings > SSH and GPG keys.\n'
}

main "$@"
