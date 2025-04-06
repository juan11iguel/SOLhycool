import time
import math
from dataclasses import dataclass
import numpy as np
import pandas as pd
from tqdm import tqdm
import pygmo as pg
import multiprocessing
import threading
import datetime
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from dataclasses import asdict
from loguru import logger
import argparse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from solhycool_modeling import EnvironmentVariables, OperationPoint
from solhycool_optimization import DecisionVariables, ValuesDecisionVariables
from solhycool_optimization.utils import pareto_front_indices
from solhycool_optimization.problems.horizon import CombinedCoolerPathFinderProblem

multiprocessing.set_start_method("spawn", force=True) # MATLAB Engine Cannot Be Used in Forked Processes

@dataclass
class AlgoParams:
    algo_id: str = "sga"
    max_n_obj_fun_evals: int = 20_000
    max_n_logs: int = 300
    pop_size: int = 80
    # Vavail0: list[float] = None
    
    params_dict: dict = None
    log_verbosity: int = None
    gen: int = None

    def __post_init__(self, ):

        if self.algo_id in ["gaco", "sga", "pso_gen"]:
            self.gen = self.max_n_obj_fun_evals // self.pop_size
            self.params_dict = {
                "gen": self.gen,
            }
        elif self.algo_id == "simulated_annealing":
            self.gen = self.max_n_obj_fun_evals // self.pop_size
            self.params_dict = {
                "bin_size": self.pop_size,
                "n_T_adj": self.gen
            }
        else:
            self.pop_size = 1
            self.gen = self.max_n_obj_fun_evals
            self.params_dict = { self.max_n_obj_fun_evals // self.pop_size }
        
        if self.log_verbosity is None:
            self.log_verbosity = math.ceil( self.gen / self.max_n_logs)
    # def add_water_available_from_env(self, df_env: pd.DataFrame) -> None:
    #     self.Vavail0 = [df_env.loc[date_str].iloc[0]["Vavail_m3"] for date_str in self.date_strs]

@dataclass
class DayResults:
    index: pd.DatetimeIndex # Index of the results
    df_paretos: list[pd.DataFrame] # List of dataframes with the pareto fronts for each step
    consumption_arrays: list[np.ndarray[float]] # Array with the consumption values for the candidate operation points
    pareto_idxs: list[int] # Path of indices of the pareto fronts from the dataset of candidate operation points
    selected_pareto_idxs: list[int] # Path of indices of the selected pareto fronts
    df_results: pd.DataFrame # DataFrame with the results of the path composed by the selected pareto fronts

def update_bar_every(pbar: tqdm, interval=0.5) -> None:
    """ Updates progress bar every `interval` seconds """
    while True:
        time.sleep(interval)
        pbar.refresh()

def evaluate_decision_variables(step_idx: int, ds_env: pd.Series, dv_values: ValuesDecisionVariables, total_num_evals: int, date_str: str) -> tuple[list[DecisionVariables], list[list[float], list[float]]]:
    """Evaluates decision variables for a given step."""
    
    # logger.info(f"Starting evaluation for step {step_idx}")
    import combined_cooler
    cc_model = combined_cooler.initialize()
    
    # Prepare environment variables
    ev = EnvironmentVariables.from_series(ds_env).constrain_to_model()
    ev_m = ev.to_matlab()
    
    # Evaluate different combination of decision variables
    dv_list = []
    consumption_list = [[], []]
    with tqdm(total=total_num_evals, desc=f"{date_str} | Step {step_idx:02d}", position=step_idx, leave=False) as pbar:
        for qc_val in dv_values.qc:
            for rp_val in dv_values.Rp:
                for rs_val in dv_values.Rs:
                    for wdc_val in dv_values.wdc:
                        dv = DecisionVariables(qc=qc_val, Rp=rp_val, Rs=rs_val, wdc=wdc_val).to_matlab()
                        Ce_kWe, Cw_lh, d, valid = cc_model.evaluate_operation(
                            ev_m.Tamb, ev_m.HR, ev_m.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, ev_m.Tv, nargout=4
                        )
                        if valid:
                            dv_list.append(DecisionVariables(qc=d["qc"], Rp=d["Rp"], Rs=d["Rs"], wdc=d["wdc"], wwct=d["wwct"]))
                            consumption_list[0].append(Cw_lh)
                            consumption_list[1].append(Ce_kWe)
                        
            pbar.update(len(dv_values.Rp) * len(dv_values.Rs) * len(dv_values.wdc))
            pbar.set_postfix(valid_candidates=len(dv_list))                        

    return dv_list, consumption_list, 

def get_pareto_front(dv_list: list[DecisionVariables], consumption_array: np.ndarray[float], df_day: pd.DataFrame, step_idx: int) -> tuple[list[int], pd.DataFrame]:
    """ Generate pareto front """
    
    import combined_cooler
    cc_model = combined_cooler.initialize()
    
    pareto_idxs = pareto_front_indices(consumption_array, objective="minimize")
    logger.info(f"{df_day.index[0].strftime("%Y%m%d")} | Pareto front indices: {pareto_idxs}")
        
    # Generate operation points for the Pareto front
    ev = EnvironmentVariables.from_series(df_day.iloc[step_idx]).constrain_to_model()
    ev_m = ev.to_matlab()
    ops = [
        OperationPoint.from_multiple_sources(
            dict_src=cc_model.evaluate_operation(ev_m.Tamb, ev_m.HR, ev_m.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, ev_m.Tv, nargout=3)[2],
            env_vars=ev,
            time=df_day.index[step_idx],
        )
        for dv in [dv_list[i] for i in pareto_idxs]
    ]
    df_paretos = pd.DataFrame([asdict(op) for op in ops])
    
    return pareto_idxs, df_paretos

def path_selector(params: AlgoParams, problem: CombinedCoolerPathFinderProblem) -> list[int]:
    """ Select points in the pareto fronts """
    
    # Initialize problem instance
    prob = pg.problem(problem)
        
    # Initialize population
    pop = pg.population(prob, size=params.pop_size, seed=0)

    algo = pg.algorithm(getattr(pg, params.algo_id)(**params.params_dict))
    algo.set_verbosity( params.log_verbosity )
    
    pop = algo.evolve(pop)
    
    return pop.champion_x.astype(int)

# Evaluate combinations of decision variables
@retry(
    stop=stop_after_attempt(1),  # Retry up to 3 times
    wait=wait_exponential(multiplier=2, min=1, max=10),  # Exponential backoff
    retry=retry_if_exception_type(SystemError),  # Retry only on MATLAB runtime errors
)
def evaluate_day(n_parallel_evals: int, df_day: pd.DataFrame, 
                 dv_values: ValuesDecisionVariables, 
                 total_num_evals: int, path_selector_params: AlgoParams,):
    """ Evaluate optimization for a given day """
    
    date_str = df_day.index[0].strftime("%Y%m%d")
    start_time = time.time()

    # 1. Evaluate decision variables
    df_paretos = []
    consumption_arrays = []
    pareto_idxs_list = []
    with ProcessPoolExecutor(max_workers=n_parallel_evals) as executor:
        futures = {executor.submit(evaluate_decision_variables, step_idx, ds, dv_values, total_num_evals, date_str): step_idx for step_idx, (dt, ds) in enumerate(df_day.iterrows())}
        for future in as_completed(futures):
            step_idx = futures[future]
            dv_list, consumption_list = future.result()
            
            # 2. Generate pareto front
            consumption_array = np.array(consumption_list).transpose()
            pareto_idxs, df_pareto = get_pareto_front(dv_list, consumption_array, df_day, step_idx)
            df_paretos.append(df_pareto) 
            consumption_arrays.append(consumption_array)
            pareto_idxs_list.append(pareto_idxs)
    
    # Sort the pareto fronts and consumption arrays by time
    df_paretos.sort(key=lambda df: df["time"].min()) 
    consumption_array.sort(key=lambda df: df["time"].min())# This will probably not work
    pareto_idxs_list.sort(key=lambda df: df["time"].min())
    
    # 3. Select points in the pareto fronts
    problem = CombinedCoolerPathFinderProblem(df_paretos=df_paretos, Vavail0=df_day.iloc[0]["Vavail_m3"])
    selected_pareto_idxs = path_selector(df_paretos, path_selector_params, problem)
    logger.info(f"{date_str} | Selected pareto front indices: {selected_pareto_idxs}")
    
    # 4. Generate results dataframe for the day
    _, ops = problem.evaluate(
        [OperationPoint(
            **problem.df_paretos[step_idx].iloc[selected_idx]
            ) for step_idx, selected_idx in enumerate(selected_pareto_idxs)],
        update_operation_pts=True
    )
    df_results = pd.DataFrame([asdict(op) for op in ops],).set_index("time", drop=True)
    logger.info(f"{date_str} | Completed evaluation in {time.time() - start_time:.1f} seconds")
    
    return DayResults(
        index=df_day.index,
        df_paretos=df_paretos,
        consumption_arrays=consumption_arrays,
        pareto_idxs=pareto_idxs_list,
        selected_pareto_idxs=selected_pareto_idxs,
        df_results=df_results
    )
    
def export_results_day(day_results: DayResults, output_path: Path) -> None:
    with pd.HDFStore(output_path, mode='a') as store:
        for dt, df_pareto, consumption_array in zip(
            day_results.index, day_results.df_paretos, day_results.consumption_arrays
        ):
            table_key = dt.strftime("%Y%m%dT%H%M")

            # Save pareto front for this timestep
            store.put(f"/pareto/{table_key}", df_pareto)

            # Save consumption array for this timestep
            df_consumption = pd.DataFrame(consumption_array, columns=["Cw", "Ce"])
            store.put(f"/consumption/{table_key}", df_consumption)

        # Append df_results (path of selected solutions)
        if "/results" in store:
            existing = store["/results"]
            combined = pd.concat([existing, day_results.df_results])
            combined = combined.sort_index()
            store.put("/results", combined)
        else:
            store.put("/results", day_results.df_results.sort_index())

        # Save  paths
        store.put("/paths/pareto_idxs", pd.Series(day_results.pareto_idxs, index=day_results.index))
        store.put("/paths/selected_pareto_idxs", pd.Series(day_results.selected_pareto_idxs, index=day_results.index))

    logger.info(f"Results saved to {output_path}")

def clear_screen_every(interval=10):
    """Clears the screen every `interval` seconds to avoid clutter from progress bars."""
    while True:
        time.sleep(interval)
        os.system("clear")

def main(date_span: tuple[str, str], n_parallel_evals: int, base_path: Path, env_path: Path, values_per_decision_variable: int, power_threshold: float, file_id: str):
    # # Start the screen clearing thread
    # clear_thread = threading.Thread(target=clear_screen_every, daemon=True)
    # clear_thread.start()

    # Load environment into EnvironmentVariables for the episode
    df_env = pd.read_hdf(base_path / env_path).loc[date_span[0]:date_span[1]]

    # Generate decision variable arrays
    dv_values: ValuesDecisionVariables = ValuesDecisionVariables.initialize(values_per_decision_variable).generate_arrays()
    # Compute total number of evaluations
    total_num_evals = np.prod([len(value) for value in asdict(dv_values).values()])

    start_date = datetime.datetime.strptime(date_span[0], "%Y%m%d").replace(hour=0)
    end_date = datetime.datetime.strptime(date_span[1], "%Y%m%d").replace(hour=23)

    all_dates = list(pd.date_range(start=start_date, end=end_date, freq='D', tz='UTC'))
    
    output_path = base_path / f"optimization/results/cc_horizon_optimization/{file_id}.h5"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # df_sim_all = []
    start_time = time.time()
    batch_size = n_parallel_evals

    # Evaluate all days
    with tqdm(total=len(all_dates), desc="Evaluating days", unit="day", leave=True, ) as pbar:
        # Start the parallel thread to update the main progress bar
        status_update_thread = threading.Thread(target=update_bar_every, args=[pbar, 20], daemon=True)
        status_update_thread.start()
        
        for i in range(0, len(all_dates), batch_size):
            batch_dates = all_dates[i:i + batch_size]
            futures = {}

            # Evaluate days in parallel batches
            with ProcessPoolExecutor(max_workers=len(batch_dates)) as executor:
                for date in batch_dates:
                    date_str = date.strftime("%Y%m%d")
                    df_day = df_env.loc[date_str]
                    # Only evaluate steps where power is above some thresholds, otherwise just DC is used
                    df_day = df_day[df_day["Q_kW"] > power_threshold]
                    
                    future = executor.submit(evaluate_day, 5, df_day, dv_values, total_num_evals, AlgoParams())
                    futures[future] = date_str

                for future in as_completed(futures):
                    day_results = future.result()
                    export_results_day(day_results, output_path)

                    pbar.update(1)
        
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--date_span', nargs=2, default=["20220101", "20221231"], help="Date span for evaluation in YYYYMMDD format")
    parser.add_argument('--evaluation_id', type=str, default="")
    parser.add_argument('--n_parallel_evals', type=int, default=20, help="Number of parallel evaluations")
    parser.add_argument('--base_path', type=str, default="/workspaces/SOLhycool", help="Base path for the project")
    parser.add_argument('--env_path', type=str, default="data/datasets/environment_data_20220101_20241231.h5", help="Path to the environment data file")
    parser.add_argument('--values_per_decision_variable', type=int, default=10, help="Number of values per decision variable")
    parser.add_argument('--power_threshold', type=float, default=0, help="Thermal load power to cool below which only the Dry Cooler is used")

    args = parser.parse_args()
    
    file_id = f"cc_horizon_optimization_eval_at_{datetime.datetime.now():%Y%m%dT%H%M}_{args.evaluation_id}"
    

    # Call the main function with the parsed arguments
    main(
        date_span=args.date_span,
        n_parallel_evals=args.n_parallel_evals,
        base_path=Path(args.base_path),
        env_path=Path(args.env_path),
        values_per_decision_variable=args.values_per_decision_variable,
        power_threshold=args.power_threshold,
        file_id=file_id
    )