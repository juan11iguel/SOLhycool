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
from dataclasses import asdict
import numpy as np
import pandas as pd
from loguru import logger
import pygmo as pg
import datetime
import time
import multiprocessing

from solhycool_modeling import EnvironmentVariables, OperationPoint
from solhycool_evaluation.utils.serialization import export_evaluation_results

logger.disable("phd_visualizations")

# Paths
# Assuming the working directory is the package root (project_fld/simulation/)
base_path = Path("/workspaces/SOLhycool")

data_path: Path = base_path / "data"
env_path: Path = data_path / "datasets/environment_data_20220101_20241231.h5"
base_output_path: Path = base_path / "simulation/results"
date_span: tuple[str, str] = ("20220117", "20221231")#"20221233")
date_span_str: str = f"{date_span[0]}_{date_span[1]}"

# Parameters
problem_id: Literal["dc", "wct", "cc"] = "dc"
save_algo_logs: bool = False
reduce_load: bool = True
params_per_problem: dict = {
    "dc": dict(
        initial_pop_size = 400,
        log_verbosity = 5,
        algo_id = "sea",
        use_mbh = False,
        use_cstrs = True,
        n_trials = 3,
        wrapper_algo_iters=10,
        max_iter=80,
    )
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
    
    # # Evaluate just simulate function
    # df_ = df_env.loc[df_env.index[0].strftime("%Y%m%d")]

    # env_vars = EnvironmentVariables.from_series(df_.iloc[0])
    # env_vars.reduce_load(0.5)

    # problem = Problem(env_vars=env_vars, debug_mode=False)
    # solutions = [pg.random_decision_vector(pg.problem(problem))] * len(df_)
     
    # df_sim = simulate(df_env=df_, solutions=solutions, df=None)
    # print(df_sim)

    # archi = pg.archipelago()
    # pg._cleanup()
    # df_sim = simulate(df_env=df_, solutions=solutions, df=None)
    # print(df_sim)
    
    # archi = pg.archipelago()
    # df_sim = simulate(df_env=df_, solutions=solutions, df=None)
    # print(df_sim)
    
    # if algo_id == "mbh":
    #     inner_algo = pg.algorithm(getattr(pg, inner_algo_id)(**algo_params))
    #     inner_algo.set_verbosity(log_verbosity) 
    #     algo = pg.algorithm(pg.mbh(inner_algo))
    # else:
    #     algo = pg.algorithm(getattr(pg, algo_id)(**algo_params))
    # algo.set_verbosity(log_verbosity) 
    
    current_month = start_date.month
    results_dict: dict = {}
    df_sim: pd.DataFrame = None
    df_opt: pd.DataFrame = None
    n_days = (end_date-start_date).days + 1
    for n_day, single_date in enumerate(pd.date_range(start=start_date, end=end_date, freq='D', tz='UTC')):
        date_str = single_date.strftime("%Y%m%d")
        
        logger.info(f"[{n_day:03d}/{n_days:03d}] Evaluating {date_str}")
        
        # 2. Setup problems for the day
        problems = []
        # pop0 = []
        archi = pg.archipelago()
        for idx, (dt, ds) in enumerate(df_env.loc[date_str].iterrows()):
            
            env_vars = EnvironmentVariables.from_series(ds)
            env_vars.reduce_load(0.5) # With only one component we can only get to half of the nominal power
            problems.append(Problem(env_vars=env_vars, store_fitness=False))
            
            logger.info(f"Problem {idx+1:02d} created for {dt}")
            
            # pop0.append( pg.population(problems[-1], size=initial_pop_size) )
            archi.push_back(
                # Setting use_pool=True results in ever-growing memory footprint for the sub-processes
                # https://github.com/esa/pygmo2/discussions/168#discussioncomment-10269386
                # udi=pg.mp_island(use_pool=False), 
                pg.island(algo=algo, prob=pg.problem(problems[-1]), size = initial_pop_size)
            )
        
        results_dict[date_str] = {
            # "x0": [pop.champion_x for pop in pop0],
            # "fitness0": [pop.champion_f for pop in pop0],
        }
        
        archi.evolve()
        print(archi)
        
        start_time = time.time()
        while archi.status == pg.evolve_status.busy:
            time.sleep(5)
            logger.info(f"Elapsed time: {time.time() - start_time:.0f}")
            # logger.info(f"Current evolution results | Best fitness: {pop_current.champion_f[0]}, \nbest decision vector: {pop_current.champion_x}")
        evaluation_time = int(time.time() - start_time)
        logger.info(f"[{n_day:03d}/{n_days:03d}] Completed evolution for {date_str}! Took {evaluation_time:.0f} seconds") 
        
        # 7. Process results
        # Extract evolved populations and algorithm logs
        x_values = []
        fitness_values = []
        algo_logs = []
        fitness_history = []

        for isl in archi:
            population = isl.get_population()
            algorithm = isl.get_algorithm()
            problem = population.problem.extract(object)
            
            x_values.append(population.champion_x)
            fitness_values.append(population.champion_f)
            algo_logs.append(algorithm.extract(getattr(pg, algo_id)).get_log())
            fitness_history.append( problem.fitness_history )

        results_dict[date_str].update({"x": x_values, "fitness": fitness_values})
        
        pg._cleanup()
        
        # Simulate the best operation points
        # This is where we would have the opportunity to make use of a different
        # environment in the simulation to account for forecast uncertainties
        df_sim = simulate(df_env=df_env.loc[date_str], solutions=results_dict[date_str]["x"], df=df_sim, parallel=False)
            
        # Evaluate the best operation points
        # With exactly the same environment as the original problem
        # df_opt = simulate(df_env=df_env.loc[date_str], solutions=results_dict[date_str]["x"], df=df_opt, parallel=False)
        
        # 8. Export results. Once per month
        # if (single_date + pd.Timedelta(days=1)).month != current_month or single_date == end_date:
        #     current_month = (single_date + pd.Timedelta(days=1)).month
        export_evaluation_results(
            results_dict=results_dict,
            metadata=metadata,
            df_opt=df_opt,
            df_sim=df_sim,
            algo_logs=algo_logs if save_algo_logs else None,
            algo_table_ids=[f"{date_str}T{hour:02d}" for hour in range(24)],
            output_path=output_path,
            file_id = file_id,
            fitness_history=fitness_history
        )
        results_dict = {}
        df_sim = None
        df_opt = None
        del x_values, fitness_values, archi, population, algorithm, problem # Free memory
            
if __name__ == "__main__":
    main()
        