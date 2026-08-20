#!/bin/bash

set -e

run_sudo() {
    if [[ -n "${VM_PASS:-}" ]]; then
        printf '%s\n' "$VM_PASS" | sudo -S "$@" 2>/dev/null
    else
        sudo "$@"
    fi
}

run_sudo apt update
run_sudo apt upgrade -y

run_sudo apt install -y curl git

run_sudo apt install -y fzf
echo "source /usr/share/doc/fzf/examples/key-bindings.bash" >> ~/.bashrc

run_sudo apt install -y ripgrep

run_sudo apt install -y wget

run_sudo apt install -y lsd

run_sudo apt install -y bat
echo 'alias bat="batcat"' >> ~/.bashrc

run_sudo apt install -y ffmpeg

run_sudo apt install -y htop

run_sudo apt install -y jq

# yq is not packaged in Debian repos; install the official binary release
run_sudo curl -L https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -o /usr/local/bin/yq && run_sudo chmod +x /usr/local/bin/yq

# --- NVIM ---
run_sudo apt install -y neovim
git clone https://github.com/NvChad/starter ~/.config/nvim
