#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOUNT_SCRIPT_SOURCE="${SCRIPT_DIR}/mount-shared.sh"
SERVICE_SOURCE="${SCRIPT_DIR}/mount-shared.service"
REMOTE_DIRECTORY="/tmp/mount-shared-installer"
SSH_OPTIONS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

usage() {
    printf 'Usage: %s -i <host> -p <port> -c <user>:<password>\n' "$(basename "$0")" >&2
    exit 1
}

PORT=""
CREDENTIALS=""
SSH_HOST=""

while getopts ":p:c:i:" option; do
    case "$option" in
        p) PORT="$OPTARG" ;;
        c) CREDENTIALS="$OPTARG" ;;
        i) SSH_HOST="$OPTARG" ;;
        *) usage ;;
    esac
done

if [[ -z "$SSH_HOST" || -z "$PORT" || -z "$CREDENTIALS" || "$CREDENTIALS" != *:* ]]; then
    usage
fi

VM_USER="${CREDENTIALS%%:*}"
VM_PASSWORD="${CREDENTIALS#*:}"

for source_file in "$MOUNT_SCRIPT_SOURCE" "$SERVICE_SOURCE"; do
    if [[ ! -f "$source_file" ]]; then
        printf 'Required file not found: %s\n' "$source_file" >&2
        exit 1
    fi
done

if ! command -v sshpass >/dev/null 2>&1; then
    printf 'sshpass is required. Install it with: brew install hudochenkov/sshpass/sshpass\n' >&2
    exit 1
fi

ssh_run() {
    sshpass -p "$VM_PASSWORD" ssh -p "$PORT" "${SSH_OPTIONS[@]}" "${VM_USER}@${SSH_HOST}" "$@"
}

scp_run() {
    sshpass -p "$VM_PASSWORD" scp -P "$PORT" "${SSH_OPTIONS[@]}" "$@"
}

printf -v quoted_password '%q' "$VM_PASSWORD"

run_step() {
    local description="$1"
    shift
    printf '\n==> %s\n' "$description"
    "$@"
}

sudo_run() {
    local command="$1"
    ssh_run "printf '%s\\n' $quoted_password | sudo -S -p '' $command"
}

printf 'Installing mount-shared.service on %s@%s:%s\n' "$VM_USER" "$SSH_HOST" "$PORT"
run_step "Checking SSH connection" ssh_run "printf 'SSH connection successful.\\n'"
run_step "Checking remote sudo access" sudo_run "true"
run_step "Creating temporary directory" ssh_run "rm -rf '$REMOTE_DIRECTORY' && mkdir -p '$REMOTE_DIRECTORY'"
run_step "Uploading service files" scp_run "$MOUNT_SCRIPT_SOURCE" "$SERVICE_SOURCE" "${VM_USER}@${SSH_HOST}:${REMOTE_DIRECTORY}/"
run_step "Installing mount script" sudo_run "install -v -m 0755 '$REMOTE_DIRECTORY/mount-shared.sh' /usr/local/bin/mount-shared.sh"
run_step "Installing systemd service" sudo_run "install -v -m 0644 '$REMOTE_DIRECTORY/mount-shared.service' /etc/systemd/system/mount-shared.service"
run_step "Reloading systemd" sudo_run "systemctl daemon-reload"
run_step "Enabling and starting service" sudo_run "systemctl enable --now mount-shared.service"
run_step "Verifying installed files" ssh_run "ls -l /usr/local/bin/mount-shared.sh /etc/systemd/system/mount-shared.service"
run_step "Checking service status" ssh_run "systemctl --no-pager --full status mount-shared.service"
run_step "Showing service logs" ssh_run "journalctl --no-pager -u mount-shared.service -n 50"
run_step "Removing temporary files" ssh_run "rm -rf '$REMOTE_DIRECTORY'"

printf '\nInstalled and enabled mount-shared.service on %s.\n' "$SSH_HOST"
