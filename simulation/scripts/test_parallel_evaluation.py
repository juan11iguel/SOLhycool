import copy
import multiprocessing
from pathlib import Path
from dataclasses import asdict
import numpy as np
import pandas as pd
from loguru import logger
import datetime

import combined_cooler_model

from solhycool_modeling import EnvironmentVariables
from solhycool_optimization.problems.static import DcProblem as Problem
from solhycool_optimization.utils.evaluation import optimize


logger.disable("phd_visualizations")

data_path: Path = Path("../data")
env_path: Path = data_path / "datasets/environment_data_20220101_20241231.h5"
base_output_path: Path = Path("../results")

# cc_model = combined_cooler_model.initialize()

def optimize_wrapper(problem) -> dict:
    operation_points, _, _, fitness_list = optimize(
        problem, extra_outputs=True, max_iter=300, use_mbh=True, 
        algo_id="compass_search", n_trials=2, log_verbosity=1,
        initial_pop_size=50
    )
    best_idx = np.argmin(fitness_list[:, 0])
    
    return asdict(operation_points[best_idx])

def process_entry(args) -> tuple[pd.DatetimeIndex, dict]:
    idx, dt, ds = args
    print(f"Iteration {idx+1} out of {len(df_)}: {dt}")
    env_vars = EnvironmentVariables.from_series(ds)
    env_vars.Q = env_vars.Q / 2
    env_vars.mv = env_vars.mv / 2
    
    problem = Problem(env_vars=env_vars, debug_mode=False)
    
    print(copy.deepcopy(problem))
    
    result = optimize_wrapper(problem)
    
    return dt, result

if __name__ == "__main__":
    df_env = pd.read_hdf(env_path)

    selected_date_str: str = "20220103" 
    df_ = df_env.loc[selected_date_str]

    output_path = base_output_path / selected_date_str
    if not output_path.exists():
        output_path.mkdir(parents=True)
    
    results: list[dict] = []

    with multiprocessing.Pool() as pool:
        results = pool.map(process_entry, [(idx, dt, ds) for idx, (dt, ds) in enumerate(df_.iterrows())])
    # results = [process_entry((idx, dt, ds)) for idx, (dt, ds) in enumerate(df_.iterrows())]

    df_results = pd.DataFrame([r[1] for r in results], index=[r[0] for r in results])
    df_results.to_csv(output_path / "dc_preliminary_results.csv")
    logger.info(f"Results saved in {output_path}")
    df_results
