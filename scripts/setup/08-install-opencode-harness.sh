#!/bin/bash

if ! command -v opencode >/dev/null 2>&1; then
  curl -fsSL https://opencode.ai/install | bash
fi

export AI_PROMPT_REPOSITORY="/mnt/opencodeharness"
export OPENCODE_HARNESS="/mnt/opencodeharness"
export OPENCODE_CONFIG="$HOME/.config/opencode"

cd "$OPENCODE_HARNESS"
./scripts/install-cli-tools.sh
python3 opencode_setup.py profile install -g shared
python3 opencode_setup.py profile install -g agent-development
python3 opencode_setup.py profile install -g main-harness
python3 opencode_setup.py profile install -g artifacts-workflow

# Agent instructions
mkdir -p "$OPENCODE_CONFIG/instructions"
# cp "opencode/AGENTS.md" "$OPENCODE_CONFIG/"
python3 scripts/generate-system-bash.py > "$OPENCODE_CONFIG/instructions/system-bash.md"

python3 opencode_setup.py configure
python3 opencode_setup.py permissions -g full

echo -e "\n\033[0;32mOpenCode root config installed:\033[0m\n"
batcat --paging=never --style=plain,header,grid "$OPENCODE_CONFIG/opencode.json"
echo -e "\n\033[0;32mGlobal configuration:\033[0m\n"
lsd --tree --group-dirs=first --ignore-glob node_modules --ignore-glob package.json --ignore-glob bun.lock "$OPENCODE_CONFIG"
