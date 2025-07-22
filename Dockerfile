# syntax = devthefuture/dockerfile-x
INCLUDE ./Dockerfile.base

# Copy the project packages
COPY . /tmp/
# Create conda environment
RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r && \
conda env create -f /tmp/environment-prod.yml && \
conda clean -afy
# Clean up the temporary files
RUN rm -rf /tmp/*

# Test the conda environment
# Set default conda environment
ENV PATH="/miniconda3/envs/${CONDA_ENV_NAME}/bin:$PATH"
SHELL ["/bin/bash", "-c"]
RUN which python
RUN airflow version
# RUN conda run -n "$CONDA_ENV_NAME" python -c "import sys; print('Python version:', sys.version)"
# RUN conda run -n "$CONDA_ENV_NAME" airflow version
