# import os
# MR = "/home/patomareao/MATLAB/R2024b"
# os.environ['LD_LIBRARY_PATH'] = f"{MR}/runtime/glnxa64:\
# {MR}/bin/glnxa64:\
# {MR}/sys/os/glnxa64:\
# {MR}/extern/bin/glnxa64:\
# /lib/x86_64-linux-gnu:"

import copy
from typing import Literal
from pathlib import Path
from collections import deque
from dataclasses import asdict
import numpy as np
import pandas as pd
from loguru import logger
import pygmo as pg
import datetime
import time
import multiprocessing

from solhycool_modeling import EnvironmentVariables, OperationPoint
from solhycool_optimization.utils.evaluation import optimize
from solhycool_evaluation.utils.serialization import export_evaluation_results

logger.disable("phd_visualizations")

# Paths
# Assuming the working directory is the package root (project_fld/simulation/)
base_path = Path("/workspaces/SOLhycool")

data_path: Path = base_path / "data"
env_path: Path = data_path / "datasets/environment_data_20220101_20241231.h5"
base_output_path: Path = base_path / "simulation/results"
date_span: tuple[str, str] = ("20220101", "20221231")#"20221233")
date_span_str: str = f"{date_span[0]}_{date_span[1]}"

# Parameters
problem_id: Literal["dc", "wct", "cc"] = "dc"
save_algo_logs: bool = False
params_per_problem: dict = {
    "dc": {
        "algo_params": dict( # algo_params should probaly by a nested field, to allow to have other general params such as reduce_load
            initial_pop_size = 400,
            log_verbosity = 5,
            algo_id = "sea",
            use_mbh = False,
            use_cstrs = True,
            n_trials = 1,
            wrapper_algo_iters = 10,
            max_iter = 80,
        ),
        "reduce_load": True
    },
}
params = params_per_problem[problem_id]

# Import problem definition based on problem_id
if problem_id == "dc":
    from solhycool_optimization.problems.static import DryCoolerProblem as Problem
elif problem_id == "wct":
    from solhycool_optimization.problems.static import WetCoolerProblem as Problem
elif problem_id == "cc":
    from solhycool_optimization.problems.static import CombinedCoolerProblem as Problem
else:
    raise ValueError(f"Invalid problem_id: {problem_id}")

# if algo_id == "mbh":
#     assert inner_algo_id is not None, "If wrapper algorithm is used, a inner_algo_id needs to be specified"
np.set_printoptions(precision=2)
metadata: dict = {
    "date_span": date_span,
    "problem_id": problem_id,
    **params,
    # "initial_pop_size": initial_pop_size,
    # "algo_id": algo_id,
    # "algo_params": algo_params,
}
file_id = f"eval_at_{datetime.datetime.now():%Y%m%dT%H%M}"

output_path = base_output_path / date_span_str
if not output_path.exists():
    output_path.mkdir(parents=True)
   
start_date = datetime.datetime.strptime(date_span[0], "%Y%m%d").replace(hour=0, minute=0, second=0)
end_date = datetime.datetime.strptime(date_span[1], "%Y%m%d").replace(hour=23, minute=0, second=0)

def process_entry(args) -> tuple[pd.DatetimeIndex, OperationPoint]:
    x, dt, ds = args

    logger.info(f"Evaluting {dt}")
    
    env_vars = EnvironmentVariables.from_series(ds)
    if reduce_load:
        env_vars.reduce_load(0.5)
    
    # print(x)
    result = Problem(env_vars=env_vars).evaluate(x)
    
    logger.info(f"Completed evaluation for {dt}")
    return dt, result

def simulate(df_env: pd.DataFrame, solutions: list[np.ndarray[float]], df: pd.DataFrame = None, parallel: bool = True) -> pd.DataFrame:
    
    assert len(df_env) == len(solutions), "The number of solutions must match the dimension of the environment"
    
    if parallel:
        with multiprocessing.Pool() as pool:
            results = pool.map(process_entry, [(x, dt, ds) for x, (dt, ds) in zip(solutions, df_env.iterrows())])
    else:
        results = [process_entry((x, dt, ds)) for x, (dt, ds) in zip(solutions, df_env.iterrows())]
    
    df_ = pd.DataFrame([asdict(r[1]) for r in results], index=[r[0] for r in results])
    
    # ops = []
    # for idx, (dt, ds) in enumerate(df_env.iterrows()):
    #     env_vars = EnvironmentVariables.from_series(ds)
    #     env_vars.Q = env_vars.Q/2
    #     env_vars.mv = env_vars.mv / 2
        
    #     ops.append( Problem(env_vars=env_vars).evaluate(solutions[idx]) )
    
    # df_ = pd.DataFrame([asdict(op) for op in ops], index=df_env.index)
    
    if df is None:
        df = df_
    else:
        df = pd.concat([df, df_])    
    return df

def main() -> None:
   
    # 1. Setup environment
    df_env = pd.read_hdf(env_path).loc[date_span[0]:date_span[1]]
    
    current_month = start_date.month
    results_dict: dict = {}
    df_sim: pd.DataFrame = None
    df_opt: pd.DataFrame = None
    n_days = (end_date-start_date).days + 1
    pop0: list[list[float]] = deque(maxlen=10)
    for n_day, single_date in enumerate(pd.date_range(start=start_date, end=end_date, freq='D', tz='UTC')):
        date_str = single_date.strftime("%Y%m%d")
        
        logger.info(f"[{n_day:03d}/{n_days:03d}] Evaluating {date_str}")
        
        start_time = time.time()
        # 2. Solve problems for the day
        results: list[dict] = []
        x_list = []
        fitness_list = []
        df_day = df_env.loc[date_str]
        for idx, (dt, ds) in enumerate(df_day.iterrows()):
            logger.info(f"Step {idx+1} out of {len(df_day)}: {dt}") # | Water available: {Vavail:.2f} m³
    
            # Initialize environment
            env_vars = EnvironmentVariables.from_series(ds)
            if reduce_load:
                env_vars.reduce_load(0.5) # With only one component we can only get to half of the nominal power
            # env_vars.Vavail = Vavail
            # env_vars.Pw_s2 = env_vars.Pe * 2 * 1e-2 # Alternative source incurs in a cost similar to electricity
            # logger.info(f"{env_vars=}")
            # Initialize problem
            problem = Problem(env_vars=env_vars)
            
            # Evaluate
            operation_points, _, pop_list, fitness_list_, _ = optimize(
                problem, 
                **params,
                # log_verbosity = 10,
                # use_cstrs=True, 
                # algo_id="sea", 
                # n_trials = 1, 
                # initial_pop_size=params["initial_pop_size"], 
                # wrapper_algo_iters=params["wrapper_algo_iters"], 
                # max_iter=params["max_iter"],
                evaluate_global_with_local=True,
                extra_outputs=True, 
                pop0 = pop0 if len(pop0)>0 else None,
            )
            best_idx = np.argmin(fitness_list_[:,0])
            results.append(
                asdict(operation_points[best_idx])
            )
            
            # Update environment
            # Vavail = env_vars.update_available_water(operation_points[0].Cw_s1)
            
            # Store best (maxlen) decision vectors so they can be introduced in the next step
            pop0.append(pop_list[best_idx].champion_x)
            x_list.append(pop_list[best_idx].champion_x)
            fitness_list.append(fitness_list_[best_idx])
        
        evaluation_time = int(time.time() - start_time)
        logger.info(f"[{n_day:03d}/{n_days:03d}] Completed evolution for {date_str}! Took {evaluation_time:.0f} seconds") 
        
        results_dict[date_str] = {
            # "x0": [pop.champion_x for pop in pop0],
            # "fitness0": [pop.champion_f for pop in pop0],
            "x": x_list,
            "fitness": fitness_list,
            "evaluation_time_secjk": evaluation_time,
        }
            
        # Here we are assuming that the simulation environment is the same as the optimization environment
        # Which is true for static optimization, should not be the case when long prediction horizons are used
        df_sim = pd.DataFrame(results, index=df_env.loc[date_str].index)
        
        
        # 7. Process results

        # 8. Export results. Once per month
        # if (single_date + pd.Timedelta(days=1)).month != current_month or single_date == end_date:
        #     current_month = (single_date + pd.Timedelta(days=1)).month
        export_evaluation_results(
            results_dict=results_dict,
            metadata=metadata,
            df_opt=df_opt,
            df_sim=df_sim,
            algo_logs=None,
            algo_table_ids=[f"{date_str}T{hour:02d}" for hour in range(24)],
            output_path=output_path,
            file_id = file_id,
            fitness_history=None
        )
        results_dict = {}
        df_sim = None
            
if __name__ == "__main__":
    main()
        