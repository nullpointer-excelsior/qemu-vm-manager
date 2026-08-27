#!/bin/bash

# Directories
mkdir -p "$HOME/Repositories"
mkdir -p "$HOME/Workspaces"
mkdir -p "$HOME/Vaults"
mkdir -p "$HOME/Setup"
mkdir -p "$HOME/Public"
mkdir -p "$HOME/.scripts"

# Packages
sudo apt install -y fzf

# Code editors
cd /tmp
wget -O nvim.tar.gz https://github.com/neovim/neovim/releases/latest/download/nvim-linux-arm64.tar.gz
tar -xzf nvim.tar.gz
sudo rm -rf /opt/nvim
sudo mv nvim-linux-arm64 /opt/nvim
sudo ln -sf /opt/nvim/bin/nvim /usr/local/bin/vim
git clone https://github.com/NvChad/starter ~/.config/nvim