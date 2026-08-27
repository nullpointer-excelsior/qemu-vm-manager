#!/bin/bash

if ! command -v opencode >/dev/null 2>&1; then
  curl -fsSL https://opencode.ai/install | bash
fi

repository_parent="$HOME/Repositories/personal"
repository_path="$repository_parent/ai-prompt-resources"

cd "$repository_parent" || exit 1

if [ ! -d "$repository_path" ]; then
  git clone git@github-personal.com:nullpointer-excelsior/ai-prompt-resources.git
fi

cd "$repository_path" || exit 1

./scripts/install-agents.sh 

python3 opencode_setup.py permissions full -g
