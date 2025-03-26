from pathlib import Path
import itertools
from collections import deque
from dataclasses import asdict
import json
import hjson
import numpy as np
import pandas as pd
from loguru import logger
import pygmo as pg

from solhycool_modeling import OperationPoint, EnvironmentVariables
from solhycool_optimization.utils.evaluation import optimize, evaluate_global_algos
from solhycool_optimization.utils import CustomEncoder
from solhycool_optimization.visualization import plot_algo_comparison
from solhycool_visualization.diagrams import WascopStateVisualizer
from solhycool_visualization.operation import plot_results
from solhycool_optimization.utils.evaluation import optimize, evaluate_global_algos_parallel_support

# Visualization packages
from phd_visualizations.optimization import plot_obj_scape_comp_1d
from phd_visualizations import save_figure
from solhycool_optimization.problems.horizon import CombinedCoolerProblem as Problem
system_id = "cc_horizon"

logger.disable("phd_visualizations")

# Paths
data_path: Path = Path("../../data")
env_path: Path = data_path / "datasets/environment_data_20220101_20241231.h5"
base_output_path: Path = Path("../notebooks/algo_comparison")
# Constants
Vavail0 = 1 # m³, Set a value so that at midday the more expensive source will be used


def main():
    
    # Load environemental data
    # Experimental data
    df_env_exp = pd.read_csv(Path("../../modeling/assets/data.csv"), )

    # Load environment into EnvironmentVariables for the episode
    df_env = pd.read_hdf(env_path)

    selected_date_str: str = "20220103" 
    df_day = df_env.loc[selected_date_str]

    output_path = base_output_path / selected_date_str
    if not output_path.exists():
        output_path.mkdir(parents=True)
        
    # Load results from static optimization
    df_results_static = pd.read_csv(output_path / f"cc_static_results.csv", index_col=0, parse_dates=True)

    env_vars = EnvironmentVariables.from_dataframe(df_day)
    env_vars.Vavail = [float(Vavail0)] * len(env_vars.Tamb)
    env_vars.Pw_s2 = env_vars.Pe * 2 * 1e-2 # Alternative source incurs in a cost similar to electricity

    # display(env_vars)
    problem = Problem(env_vars=env_vars)
    
    results = evaluate_global_algos_parallel_support(
        problem=problem,
        n_trials=1,
        max_n_obj_fun_evals=10_000,
        algo_ids=["sea"],
        use_cstr=[True],
        pop_size=[100, 500],
        log_verbosity=[1],
        wrapper_algo_iters=50,
        pop0=[np.concatenate([df_results_static[var_id].values for var_id in problem.dec_var_ids])],
        parallel=True,
    )
    
if __name__ == "__main__":
    main()