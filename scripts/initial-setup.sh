#!/bin/bash

set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
    printf 'Run this script as root.\n' >&2
    exit 1
fi

USERNAME="${1:-${SUDO_USER:-}}"

if [[ -z "$USERNAME" || "$USERNAME" == "root" ]]; then
    printf 'Usage: %s <username>\n' "$0" >&2
    exit 1
fi

if ! id "$USERNAME" >/dev/null 2>&1; then
    printf 'User not found: %s\n' "$USERNAME" >&2
    exit 1
fi

apt-get update
apt-get install --yes sudo
usermod --append --groups sudo "$USERNAME"

printf 'Sudo access granted to %s. Log out and log in again to apply it.\n' "$USERNAME"
