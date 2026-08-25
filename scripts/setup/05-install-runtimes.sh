#!/bin/bash

set -e

# Python
sudo apt install -y python3 python3-pip
echo 'export PATH="/usr/bin:$PATH"' >> ~/.zshrc

curl -LsSf https://astral.sh/uv/install.sh | sh

# Node
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
\. "$HOME/.nvm/nvm.sh"
nvm install 22

# Java
sudo apt install -y openjdk-21-jdk
echo 'export PATH="/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH"' >> ~/.zshrc

sudo apt install -y maven

sudo apt install -y gradle

