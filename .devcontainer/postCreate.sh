#!/usr/bin/env bash
set -euo pipefail

# Initialize conda for zsh, accept channel ToS non-interactively, and create the env.
conda init zsh
conda tos accept -c https://repo.anaconda.com/pkgs/main -c https://repo.anaconda.com/pkgs/r
conda env create -f environment.yml -y

# Ensure every new zsh shell auto-activates the project environment.
if ! grep -q "SOLHYCOOL_AUTO_ACTIVATE" ~/.zshrc; then
  cat >> ~/.zshrc <<'EOF'

# SOLHYCOOL_AUTO_ACTIVATE
source /miniconda3/etc/profile.d/conda.sh
conda activate conda-env
EOF
fi
