import itertools
from loguru import logger
from pathlib import Path
import pandas as pd
import numpy as np
import time
from tqdm import tqdm
import time
from dataclasses import asdict, dataclass
import math
import pygmo as pg
import copy

from solhycool_modeling import EnvironmentVariables, OperationPoint, ModelInputsRange
from solhycool_optimization.problems.horizon import CombinedCoolerPathFinderProblem
from solhycool_optimization import DecisionVariables, ValuesDecisionVariables

@dataclass
class Parameters:
    date_str: str = "20221215"
    max_n_obj_fun_evals: int = 100_000
    Vavail0: float = 1.0
    n_trials: int = 1
    log_verbosity: int = None
    date_strs: list[str] = None
    
    def __post_init__(self):
        if log_verbosity is None:
            log_verbosity = self.max_n_obj_fun_evals // 1000
            
        if self.date_strs is None:
            day = self.date_str[-2:]
            year = self.date_str[:4]
            start_month = int(self.date_str[4:6])
            self.date_strs = [f"{year}{month:02d}{day}" for month in range(start_month, 13)]

algo_ids: list[str] = ["gaco", "simulated_annealing", "ihs", "sga", "pso_gen", "sea"]
pop_sizes: list[int] = [1, 50, 100, 1000] # Only applies for gaco, 

# Paths
data_path: Path = Path("../../data")
env_path: Path = data_path / "datasets/environment_data_20220101_20241231.h5"
results_base_path: Path = Path("/workspaces/SOLhycool/optimization/results/")

# Constants/parameters
params = Parameters()

with tqdm(total=len(params.date_strs), desc="Evaluating days", unit="day", leave=True, ) as pbar:
    for date_str in params.date_strs:

        results_path = results_base_path / f"ops_pareto_fronts_{date_str}.h5"

        # Open the HDF5 store
        with pd.HDFStore(results_path, mode='r') as store:
            table_names = list(store.keys())  # Get a list of stored tables
            df_paretos = [store[table_name] for table_name in table_names]  # Read all tables into a list
        # Sort list by "time" column
        df_paretos.sort(key=lambda df: df["time"].min())  # Assuming "time" exists in all tables

        candidates_per_step = [len(df_pareto) for df_pareto in df_paretos]

        # Initialize problem instance
        problem = CombinedCoolerPathFinderProblem(df_paretos=df_paretos, Vavail0=params.Vavail0)
        prob = pg.problem(problem)

        # Initialize archipielago
        archi = pg.archipelago()
        
        # Initialize and add different alternatives to the archipielago
        for algo_id, pop_size in itertools.product(algo_ids, pop_sizes):
            algo_params = {}
            gen = params.max_n_obj_fun_evals // pop_size
            
            
            if algo_id in ["gaco"]:
                if pop_size <= problem.n_steps:
                    # logger.warning(f"Skipping {algo_id} with pop_size={pop_size} <= {problem.size_dec_vector}")
                    continue
                algo_params["gen"] = gen
                
            elif algo_id == "simulated_annealing":
                algo_params.update({
                    "bin_size": pop_size,
                    "n_T_adj": gen,   
                })
                
            else:
                if pop_size > 1:
                    continue
                algo_params["gen"] = gen
                
            # Generate the same intial population for all algorithms
            pop0 = pg.population(prob, size=pop_size, seed=0)
            # logger.info("Initial population generated")
            
            algo = pg.algorithm(getattr(pg, algo_id)(**algo_params, seed=0))
            algo.set_verbosity(params.log_verbosity)
            
            archi.push_back(
                # Setting use_pool=True results in ever-growing memory footprint for the sub-processes
                # https://github.com/esa/pygmo2/discussions/168#discussioncomment-10269386
                pg.island(udi=pg.mp_island(use_pool=False), algo=algo, pop=pop0, )
            )
        
        # 6. Evaluate the archipielago
        archi.evolve()
        print(archi)

        start_time = time.time()
        while archi.status == pg.evolve_status.busy:
            pbar.refresh()
            time.sleep(5)
            # print(f"Current evolution results | Best fitness: {pop_current.champion_f[0]}, \nbest decision vector: {pop_current.champion_x}")
        metadata["evaluation_time"] = int(time.time() - start_time)

        # Export results
        algo_logs = []
        algo_ids = []
        for isl, result_key in zip(archi, results_dict.keys()):
            results_dict[result_key]["x"] = isl.get_population().champion_x
            results_dict[result_key]["fitness"] = isl.get_population().champion_f
            algo_id = extract_prefix(result_key)
            
            algo_ids.append(algo_id)
            algo_logs.append( isl.get_algorithm().extract( getattr(pg, algo_id) ).get_log() )

        pbar.update(1)