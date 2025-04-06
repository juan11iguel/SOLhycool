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

And then activate it using the name specified in the `environment.yml` file (this is done automatically for new sessions):

```bash
conda activate conda-env
```

To update the environment after changing the `environment.yml`:
```bash
conda env update -f environment.yml
```

## Run simulations in the background

container_name = `festive_hypatia`

- Combined cooler horizon optimization. Path selection. Algorithm comparison:
```bash
docker exec -d festive_hypatia bash -c "source /miniconda3/bin/activate conda-env && python /workspaces/SOLhycool/optimization/scripts/algo_comparison_cc_horizon.py > /workspaces/SOLhycool/optimization/results/output.log 2>&1"
```

- Combined cooler horizon optimization. Pareto front generation:
```bash
docker exec -d festive_hypatia bash -c "source /miniconda3/bin/activate conda-env && python /workspaces/SOLhycool/optimization/scripts/cc_horizon_optimization.py --values_per_decision_variable 12 --repeat_for_each_month --date_str 20220101 --n_parallel_evals 20 > /workspaces/SOLhycool/optimization/results/output.log 2>&1"
```

To check the logs:
```bash
docker exec -it festive_hypatia tail -f /workspaces/SOLhycool/optimization/results/output.log
```