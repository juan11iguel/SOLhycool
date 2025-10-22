#!/bin/bash

set -euo pipefail

echo "🚀 Starting SOLhycool Development Environment Setup..."

# -----------------------------------------------------------------------------
# Conda setup for SOLhycool project
# -----------------------------------------------------------------------------
: "${CONDA_ENV_NAME:=conda-env}"


# Accept conda Terms of Service first
echo "Accepting conda Terms of Service..."
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || true
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || true

echo "📦 Checking conda environment '${CONDA_ENV_NAME}'..."
if ! conda env list | grep -q "^${CONDA_ENV_NAME}\b"; then
    echo "📥 Creating conda environment '${CONDA_ENV_NAME}' from environment.yml..."
    conda env create -n "${CONDA_ENV_NAME}" -f /workspaces/SOLhycool/environment.yml
    echo "✅ Conda environment '${CONDA_ENV_NAME}' created."
else
    echo "🔄 Updating conda environment '${CONDA_ENV_NAME}'..."
    conda env update -n "${CONDA_ENV_NAME}" -f /workspaces/SOLhycool/environment.yml --prune
    echo "✅ Conda environment '${CONDA_ENV_NAME}' updated."
fi

echo "🧹 Cleaning conda cache..."
conda clean -afy

# Activate conda env for project use
# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_NAME}"

echo "🐍 Python version in conda: $(python --version)"

echo "🔍 Checking editable SOLhycool packages..."
python - <<'PYCODE'
import importlib

packages = [
    "solhycool_modeling",
    "solhycool_optimization",
    "solhycool_simulation",
    "solhycool_visualization",
    "solhycool_deployment",
]

for pkg in packages:
    try:
        mod = importlib.import_module(pkg)
        print(f"✓ {pkg}: {mod.__file__}")
    except ImportError as e:
        print(f"✗ {pkg} missing: {e}")
PYCODE


# -----------------------------------------------------------------------------
# uv setup for Airflow (completely separate from conda)
# -----------------------------------------------------------------------------
: "${AIRFLOW_VERSION:=3.0.6}"
: "${AIRFLOW_HOME:=${HOME}/airflow}"
: "${PYTHON_VERSION:=3.12}"   # Default if not set

if ! command -v uv &>/dev/null; then
    echo "⚡ Installing uv..."
    pip install --user uv
fi

echo "📥 Installing Python ${PYTHON_VERSION} via uv for Airflow..."
uv python install "${PYTHON_VERSION}"

# Create isolated virtualenv for airflow
AIRFLOW_VENV="${AIRFLOW_HOME}/.venv"
mkdir -p "${AIRFLOW_HOME}"
if [ ! -d "${AIRFLOW_VENV}" ]; then
    echo "📦 Creating isolated uv venv for Airflow..."
    uv venv "${AIRFLOW_VENV}" --python "${PYTHON_VERSION}"
fi

echo "To work with Airflow, activate its environment explicitly:"
echo "    source \"${AIRFLOW_VENV}/bin/activate\""

# Install Airflow (in venv, not global) if not already installed
# shellcheck disable=SC1091
source "${AIRFLOW_VENV}/bin/activate"

INSTALLED_VERSION="$(airflow version 2>/dev/null || echo '')"
if [[ "${INSTALLED_VERSION}" != *"${AIRFLOW_VERSION}"* ]]; then
    CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
    echo "📥 Installing Apache Airflow ${AIRFLOW_VERSION} with uv..."
    uv pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"
fi

echo "✅ Airflow installed in isolated uv environment."
echo "🌬️ Airflow version: $(airflow version)"
echo "AIRFLOW_HOME=${AIRFLOW_HOME}"
echo "Webserver port: ${AIRFLOW__WEBSERVER__WEB_SERVER_PORT:-8080}"

# Explicit activation required for Airflow usage
echo "👉 Run this before starting Airflow:"
echo "    source \"${AIRFLOW_VENV}/bin/activate\""
echo "    airflow standalone"
echo "🚀 Development environment setup complete!"