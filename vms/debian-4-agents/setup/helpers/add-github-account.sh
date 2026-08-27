#!/usr/bin/env bash

set -euo pipefail

readonly SSH_DIRECTORY="$HOME/.ssh"
readonly SSH_CONFIG_FILE="$SSH_DIRECTORY/config"

print_usage() {
  printf 'Uso: %s <directorio-de-repositorios> <nombre-de-cuenta>\n' "$(basename "$0")"
  printf 'Ejemplo: %s "$HOME/Proyectos" mi-cuenta\n' "$(basename "$0")"
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

configure_ssh_host() {
  local host_name="$1"
  local private_key_file="$2"

  if [[ -f "$SSH_CONFIG_FILE" ]] && grep -Fqx "Host $host_name" "$SSH_CONFIG_FILE"; then
    fail "Ya existe la configuración SSH para '$host_name' en $SSH_CONFIG_FILE."
  fi

  touch "$SSH_CONFIG_FILE"
  chmod 600 "$SSH_CONFIG_FILE"

  {
    printf '\nHost %s\n' "$host_name"
    printf '  HostName github.com\n'
    printf '  User git\n'
    printf '  IdentityFile %s\n' "$private_key_file"
    printf '  IdentitiesOnly yes\n'
  } >> "$SSH_CONFIG_FILE"
}

main() {
  [[ $# -eq 2 ]] || {
    print_usage >&2
    exit 1
  }

  local repositories_directory="$1"
  local account_name="$2"
  local private_key_file
  local public_key_file
  local host_name

  require_command ssh-keygen
  require_command git
  validate_account_name "$account_name"

  private_key_file="$SSH_DIRECTORY/github_$account_name"
  public_key_file="${private_key_file}.pub"
  host_name="github-$account_name"

  [[ ! -e "$private_key_file" && ! -e "$public_key_file" ]] || fail "Ya existe una clave para '$account_name': $private_key_file"

  mkdir -p "$SSH_DIRECTORY" "${repositories_directory%/}"
  chmod 700 "$SSH_DIRECTORY"

  printf 'Se creará una clave SSH para %s. Introduce una frase de contraseña cuando se solicite.\n' "$account_name"
  ssh-keygen -t ed25519 -f "$private_key_file" -C "$account_name@github" 
  configure_ssh_host "$host_name" "$private_key_file"

  printf '\nConfiguración creada.\n'
  printf '1. Copia la siguiente clave pública y añádela en GitHub: Settings > SSH and GPG keys > New SSH key.\n\n'
  printf '%s\n\n' "$(<"$public_key_file")"
  printf '2. Verifica la conexión con:\n'
  printf '   ssh -T git@%s\n\n' "$host_name"
  printf '3. Clona repositorios de esta cuenta con:\n'
  printf '   git clone git@%s:ORGANIZACION_O_USUARIO/REPOSITORIO.git "%s/REPOSITORIO"\n' "$host_name" "${repositories_directory%/}"
}

main "$@"
