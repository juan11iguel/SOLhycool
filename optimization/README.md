# SOLhycool - optimization

This folder contains related code to the daily operation optimization of different 
cooling alternatives: DC, WCT and DC-WCT using the library [pygmo](https://github.com/esa/pygmo2/).


## Getting Started

The repository contains a [Dockerfile](../Dockerfile.base) and a [devcontainer configuration](../.devcontainer/devcontainer.json) to set up a development environment with all the necessary dependencies. 

### Starting the devcontainer

Open (clone) the repository with VSCode and `CTRL+SHIFT+P` to open the command palette and select `devcontainers: Reopen in Container`.

### Setting up the development environment from within the container

Once inside the container, set up a new conda environment with the necessary dependencies:

```bash
conda init zsh
```

Create and install dependencies using the `environment.yml` file:

```bash
conda env create -f environment.yml
```

And then activate it using the name specified in the `environment.yml` file:

```bash
conda activate conda-env
```