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

- Combined cooler horizon optimization. Pareto front generation:
```bash
docker exec -d festive_hypatia bash -c "source /miniconda3/bin/activate conda-env && python /workspaces/SOLhycool/optimization/scripts/cc_horizon_pareto_generation.py --values_per_decision_variable 12 --repeat_for_each_month --date_str 20220101 --n_parallel_evals 20 > /workspaces/SOLhycool/optimization/results/output.log 2>&1"
```

- Combined cooler horizon optimization. Path selection. Algorithm comparison:
```bash
docker exec -d festive_hypatia bash -c "source /miniconda3/bin/activate conda-env && python /workspaces/SOLhycool/optimization/scripts/algo_comparison_cc_horizon.py > /workspaces/SOLhycool/optimization/results/output.log 2>&1"
```

To check the logs:
```bash
docker exec -it festive_hypatia tail -f /workspaces/SOLhycool/optimization/results/output.log
```

## Reproducing results

### Static optimization

To reproduce the results, for the static variants run the notebooks directly:

- [Static DC](notebooks/dc_optimization.ipynb)
- [Static WCT](notebooks/wct_optimization.ipynb)
- [Static CC](notebooks/cc_static_optimization.ipynb)

Different algorithms are compared in the [algorithm comparison notebook](notebooks/static_problems_algo_comparison.ipynb) for the DC and WCT problems. For the CC it's integrated in its development notebook.

### Horizon optimization

For the horizon optimization, two scripts need to be run in sequence:

1. [Pareto front generation](scripts/cc_horizon_pareto_generation.py) to generate Pareto fronts for several days of the year.
2. [Path selection](scripts/cc_horizon_algo_comparison.py) solves the path selection problem with different algorithms and different parameters for each.
3. [Results analysis notebook](notebooks/cc_horizon_combinatoria.ipynb)

Two other notebooks are available for the failed attempts to solve the horizon problem just by extending the static ones with more variables:

- [First attempt](notebooks/cc_horizon_optimization.ipynb)
- [Bayesian optimization approach](notebooks/cc_horizon_bayesian_optimization.ipynb). Looked promising, failed miserably in the end. Would not be able to solve even the static problem.