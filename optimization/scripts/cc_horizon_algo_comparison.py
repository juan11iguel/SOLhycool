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
import datetime

from solhycool_modeling import EnvironmentVariables, OperationPoint, ModelInputsRange
from solhycool_optimization.problems.horizon import CombinedCoolerPathFinderProblem
from solhycool_optimization import DecisionVariables, ValuesDecisionVariables
from solhycool_optimization.utils import extract_prefix
from solhycool_evaluation.utils.serialization import export_evaluation_results, get_fitness_history

@dataclass
class Parameters:
    starting_date_str: str = "20220115"
    max_n_obj_fun_evals: int = 100_000
    max_n_logs: int = 300
    Vavail0: list[float] = None
    n_trials: int = 1
    date_strs: list[str] = None
    
    def __post_init__(self):
            
        if self.date_strs is None:
            day = self.starting_date_str[-2:]
            year = self.starting_date_str[:4]
            start_month = int(self.starting_date_str[4:6])
            self.date_strs = [f"{year}{month:02d}{day}" for month in range(start_month, 13)]

    def add_water_available_from_env(self, df_env: pd.DataFrame) -> None:
        self.Vavail0 = [df_env.loc[date_str].iloc[0]["Vavail_m3"] for date_str in self.date_strs]

def build_archipielago(algo_ids: list[str], pop_sizes: list[int], algos_dict: dict, problem: CombinedCoolerPathFinderProblem, params: Parameters) -> tuple[pg.archipelago, dict]:
    archi = pg.archipelago()
    prob = pg.problem(problem)
    
    for algo_id, pop_size in itertools.product(algo_ids, pop_sizes):
        algo_params = {}
        gen = params.max_n_obj_fun_evals // pop_size
        
        if algo_id in ["gaco", "sga", "pso_gen"]:
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
            
        # Generate the same intial population for all algorithms (not really)
        pop0 = pg.population(prob, size=pop_size, seed=0)
        # logger.info("Initial population generated")
        
        algo = pg.algorithm(getattr(pg, algo_id)(**algo_params, seed=0))
        algo.set_verbosity( math.ceil( gen / params.max_n_logs) )
        
        archi.push_back(
            # Setting use_pool=True results in ever-growing memory footprint for the sub-processes
            # https://github.com/esa/pygmo2/discussions/168#discussioncomment-10269386
            pg.island(udi=pg.mp_island(use_pool=False), algo=algo, pop=pop0, )
        )
        
        algos_dict[f"{algo_id}_pop{pop_size}_gen{gen}"] = {}
                
    return archi, algos_dict


algo_ids: list[str] = ["gaco", "ihs", "sga", "pso_gen", "sea"] # "simulated_annealing"
pop_sizes: list[int] = [1, 80, 150, 1000]

# Paths
base_path: Path = Path("/workspaces/SOLhycool")
data_path: Path = base_path / "data"
env_path: Path = data_path / "datasets/environment_data_psa_20220101_20241231.h5"
results_base_path: Path = base_path / "optimization/results/"

# Constants
evaluation_id = "path_finder_algo_comparison"
file_id = f"eval_at_{datetime.datetime.now():%Y%m%dT%H%M}_{evaluation_id}"

df_env = pd.read_hdf(env_path)
params = Parameters(max_n_obj_fun_evals=200_000, )
params.add_water_available_from_env(df_env)

def main():

    with tqdm(total=len(params.date_strs), desc="Evaluating days", unit="day", leave=True, ) as pbar:
        for date_idx, date_str in enumerate(params.date_strs):

            logger.info(f"{date_idx+1} / {len(params.date_strs)} | Evaluating {date_str}")

            results_path = results_base_path / f"ops_pareto_fronts_{date_str}.h5"

            # Import pareto fronts
            try:
                with pd.HDFStore(results_path, mode='r') as store:
                    table_names = list(store.keys())  # Get a list of stored tables
                    df_paretos = [store[table_name] for table_name in table_names]  # Read all tables into a list
                # Sort list by "time" column
                df_paretos.sort(key=lambda df: df["time"].min())  # Assuming "time" exists in all tables
            except Exception as e:
                logger.error(f"Error importing {results_path}: {e}")
                pbar.update(1)
                continue
            
            if not len(df_paretos) > 0:
                logger.warning(f"No pareto fronts found for {results_path}")
                pbar.update(1)
                continue 
            
            # Initialize problem instance
            problem = CombinedCoolerPathFinderProblem(df_paretos=df_paretos, Vavail0=params.Vavail0[date_idx])
            candidates_per_step = [len(df_pareto) for df_pareto in df_paretos]

            results_dict = {date_str: {}}
            metadata = {
                "n_steps": problem.n_steps,
                "n_combinations": math.prod(candidates_per_step),
                "algo_ids": algo_ids,
                "pop_sizes": pop_sizes,
                **asdict(params),
            }

            # Initialize and add different alternatives to the archipielago
            archi, results_dict[date_str] = build_archipielago(algo_ids, pop_sizes, algos_dict=results_dict[date_str], problem=problem, params=params)
                    
            # 6. Evaluate the archipielago
            archi.evolve()
            print(archi)
            
            for isl, result_key in zip(archi, results_dict[date_str].keys()):
                results_dict[date_str][result_key]["x"] = isl.get_population().champion_x.astype(int)
                results_dict[date_str][result_key]["fitness"] = isl.get_population().champion_f[0]
                
                algo_id = extract_prefix(result_key)
                algo_log = isl.get_algorithm().extract( getattr(pg, algo_id) ).get_log()
                results_dict[date_str][result_key]["fitness_history"] = get_fitness_history(algo_id, algo_log)

            export_evaluation_results(
                results_dict=results_dict,
                metadata=metadata,
                output_path=results_base_path,
                file_id=file_id,
            )
            
            pbar.update(1)
            
if __name__ == "__main__":
    start_time = time.time()
    main()
    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"Elapsed time: {elapsed_time:.2f} seconds")
    logger.info(f"Elapsed time: {elapsed_time / 60:.2f} minutes / {elapsed_time / 3600:.2f} hours")