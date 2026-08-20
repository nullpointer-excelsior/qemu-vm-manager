#!/bin/bash

set -e

run_sudo() {
    if [[ -n "${VM_PASS:-}" ]]; then
        printf '%s\n' "$VM_PASS" | sudo -S "$@" 2>/dev/null
    else
        sudo "$@"
    fi
}

run_sudo apt install -y python3 python3-pip
echo 'export PATH="/usr/bin:$PATH"' >> ~/.zshrc

# Download and install nvm:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
# in lieu of restarting the shell
\. "$HOME/.nvm/nvm.sh"
# Download and install Node.js:
nvm install 22
# Verify the Node.js version:
node -v # Should print "v22.16.0".
nvm current # Should print "v22.16.0".
# Verify npm version:
npm -v # Should print "10.9.2".

run_sudo apt install -y openjdk-21-jdk
echo 'export PATH="/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH"' >> ~/.zshrc

run_sudo apt install -y maven

run_sudo apt install -y gradle

curl -LsSf https://astral.sh/uv/install.sh | sh
