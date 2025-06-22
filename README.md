# SOLhycool

Combined cooling solutions...

![](./data/assets/facility_diagram_simple.png)
![](./modeling/assets/combined_cooler_pilot_plant.png)

## Getting started

### Development environment

The repository contains a [Dockerfile](../Dockerfile.base) and a [devcontainer configuration](../.devcontainer/devcontainer.json) to set up a development environment with all the necessary dependencies. 

#### Starting the devcontainer

Open (clone) the repository with VSCode and `CTRL+SHIFT+P` to open the command palette and select `devcontainers: Reopen in Container`.

#### Setting up the development environment from within the container

Once inside the container, set up a new conda environment with the necessary dependencies:

```bash
conda init zsh
```

Create and install dependencies using the `environment.yml` file:

```bash
conda env create -f environment.yml
```

Activate the environment:

```bash
conda activate conda-env
```

## Project structure

```bash
.
├── README.md
├── modeling
├── optimization
└── simulation
```
The project is divided into three main folders: `modeling`, `optimization`, and `simulation`. Each folder contains the respective code and data for each part of the project.
