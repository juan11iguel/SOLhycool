# syntax = devthefuture/dockerfile-x

INCLUDE ./Dockerfile.base

# Copy the rest of the project
COPY . .

# Create conda environment
RUN conda env create -f environment.yml && conda clean -afy

# Set default conda environment
ENV PATH="/miniconda3/envs/${CONDA_ENV_NAME}/bin:$PATH"
SHELL ["/bin/bash", "-c"]

# Test the conda environment
RUN which python
RUN airflow version
# RUN conda run -n "$CONDA_ENV_NAME" python -c "import sys; print('Python version:', sys.version)"
# RUN conda run -n "$CONDA_ENV_NAME" airflow version