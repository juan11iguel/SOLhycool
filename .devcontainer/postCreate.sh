#!/usr/bin/env bash
set -euo pipefail

# Initialize conda for zsh, accept channel ToS non-interactively
conda init zsh
conda tos accept -c https://repo.anaconda.com/pkgs/main -c https://repo.anaconda.com/pkgs/r

# Remove any stale environment and rebuild from scratch to avoid binary corruption
# (especially important for packages like pygmo with complex native dependencies)
conda remove -n conda-env --all -y 2>/dev/null || true
conda clean -a -y

# Create fresh environment
conda env create -f environment.yml -y

# Ensure every new zsh shell auto-activates the project environment.
if ! grep -q "SOLHYCOOL_AUTO_ACTIVATE" ~/.zshrc; then
  cat >> ~/.zshrc <<'EOF'

# SOLHYCOOL_AUTO_ACTIVATE
source /miniconda3/etc/profile.d/conda.sh
conda activate conda-env
EOF
fi
