import time
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
import gzip
import shutil

from solhycool_modeling import EnvironmentVariables, OperationPoint
from solhycool_optimization import DecisionVariables, ValuesDecisionVariables, DayResults
from solhycool_optimization.utils import pareto_front_indices
from solhycool_optimization.utils.evaluation import optimize
from solhycool_optimization.utils.serialization import get_fitness_history
from solhycool_optimization.problems.horizon import CombinedCoolerPathFinderProblem, AlgoParams
from solhycool_optimization.problems.static import CombinedCoolerProblem

multiprocessing.set_start_method("spawn", force=True) # MATLAB Engine Cannot Be Used in Forked Processes

def update_bar_every(pbar: tqdm, interval=0.5) -> None:
    """ Updates progress bar every `interval` seconds """
    while True:
        time.sleep(interval)
        pbar.refresh()

@retry(
    stop=stop_after_attempt(3),  # Retry up to 3 times
    wait=wait_exponential(multiplier=2, min=1, max=10),  # Exponential backoff
    retry=retry_if_exception_type(SystemError),  # Retry only on MATLAB runtime errors
)
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
            
    # At least one point should be found, otherwise fallback
    # to static optimization
    if len(dv_list) < 1:
        problem = CombinedCoolerProblem(env_vars=ev)
        logger.warning(f"{date_str} - step {step_idx:02d} | Not a single point was found during decision variables evaulation. Trying to find one by performing a static optimization")
        # Parameters taken from simulation/scripts/yearly_simulation_static.py
        operation_points, _, pop_list, fitness_list, _ = optimize(
            problem,
            initial_pop_size=1000,
            log_verbosity=0,
            algo_id="sea",
            use_mbh=False, 
            use_cstrs=True,
            n_trials=1,
            wrapper_algo_iters=50,
            max_iter=100,
            evaluate_global_with_local=False,
            extra_outputs=True,
        )
        best_idx = np.argmin(fitness_list[:, 0])
        dv_list.append(DecisionVariables(**{var_id: value for var_id, value in zip(problem.dec_var_ids, pop_list[best_idx].champion_x)}))
        consumption_list[0].append(operation_points[best_idx].Cw)
        consumption_list[1].append(operation_points[best_idx].Ce)
        
    return dv_list, consumption_list

def get_pareto_front(dv_list: list[DecisionVariables], consumption_array: np.ndarray[float], df_day: pd.DataFrame, step_idx: int) -> tuple[list[int], pd.DataFrame]:
    """ Generate pareto front """
    
    import combined_cooler
    cc_model = combined_cooler.initialize()
    
    pareto_idxs = pareto_front_indices(consumption_array, objective="minimize")
    logger.debug(f"{df_day.index[0].strftime("%Y%m%dT%H%M")} | Pareto front indices: {pareto_idxs}")
        
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

def path_selector(params: AlgoParams, problem: CombinedCoolerPathFinderProblem) -> tuple[list[int], pd.Series]:
    """ Select points in the pareto fronts """
    
    # Initialize problem instance
    prob = pg.problem(problem)
        
    # Initialize population
    pop = pg.population(prob, size=params.pop_size, seed=0)

    algo = pg.algorithm(getattr(pg, params.algo_id)(**params.params_dict))
    algo.set_verbosity( params.log_verbosity )
    
    pop = algo.evolve(pop)
    
    x = pop.champion_x.astype(int).tolist()
    fitness_history = get_fitness_history(params.algo_id, algo)
    
    return x, fitness_history

# Evaluate combinations of decision variables
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
    # Step 1: Get the time keys for sorting
    time_keys = [df["time"].min() for df in df_paretos]
    # Step 2: Get the sorted indices based on the time keys
    sorted_indices = sorted(range(len(time_keys)), key=lambda i: time_keys[i])
    # Step 3: Apply sorted indices to all parallel lists
    df_paretos = [df_paretos[i] for i in sorted_indices]
    consumption_arrays = [consumption_arrays[i] for i in sorted_indices]
    pareto_idxs_list = [pareto_idxs_list[i] for i in sorted_indices]
    
    # 3. Select points in the pareto fronts
    problem = CombinedCoolerPathFinderProblem(df_paretos=df_paretos, Vavail0=df_day.iloc[0]["Vavail_m3"])
    logger.info(f"{date_str} | Started evaluation of best path of pareto front points")
    selected_pareto_idxs, fitness_history = path_selector(path_selector_params, problem)
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
        fitness_history=fitness_history,
        selected_pareto_idxs=selected_pareto_idxs,
        df_results=df_results
    )

def clear_screen_every(interval=10):
    """Clears the screen every `interval` seconds to avoid clutter from progress bars."""
    while True:
        time.sleep(interval)
        os.system("clear")

def main(date_span: tuple[str, str], n_parallel_days: int, n_parallel_steps: int, base_path: Path, env_path: Path, values_per_decision_variable: int, power_threshold: float, file_id: str, full_export: bool):
    # # Start the screen clearing thread
    # clear_thread = threading.Thread(target=clear_screen_every, daemon=True)
    # clear_thread.start()
    logger.info(f"Evaluating Combined Cooler (CC) optimization with prediction horizon for date span {date_span[0]}-{date_span[-1]} with {n_parallel_days} parallel days and {n_parallel_steps} parallel steps")

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
    batch_size = n_parallel_days

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
                    
                    future = executor.submit(evaluate_day, n_parallel_steps, df_day, dv_values, total_num_evals, AlgoParams())
                    futures[future] = date_str

                for future in as_completed(futures):
                    day_results = future.result()
                    day_results.export(output_path, reduced=not full_export)

                    pbar.update(1)
                    
    # Finally, compress the resulting file using gzip
    with open(output_path, 'rb') as f_in, gzip.open(output_path.with_suffix(".gz"), 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    output_path.unlink()  # Remove uncompressed .h5 file
    logger.info(f"Results for {date_span[0]}-{date_span[-1]} compressed and saved to {output_path.with_suffix('.gz')}. Total evaluation time took {(time.time() - start_time)/3600:.1f} hours")

        
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--date_span', nargs=2, default=["20220101", "20221231"], help="Date span for evaluation in YYYYMMDD format")
    parser.add_argument('--evaluation_id', type=str, default="")
    parser.add_argument('--n_parallel_days', type=int, default=5, help="Number of parallel day evaluations")
    parser.add_argument('--n_parallel_steps', type=int, default=25, help="Number of parallel step in day evaluations")
    parser.add_argument('--base_path', type=str, default="/workspaces/SOLhycool", help="Base path for the project")
    parser.add_argument('--env_path', type=str, default="data/datasets/environment_data_psa_20220101_20241231.h5", help="Path to the environment data file")
    parser.add_argument('--values_per_decision_variable', type=int, default=10, help="Number of values per decision variable")
    parser.add_argument('--power_threshold', type=float, default=0, help="Thermal load power to cool below which only the Dry Cooler is used")
    parser.add_argument('--full_export', action='store_true', help="Export full version of the results (increases file size)")

    args = parser.parse_args()
        
    file_id = f"cc_horizon_optimization_eval_at_{datetime.datetime.now():%Y%m%dT%H%M}_{args.evaluation_id}"
    

    # Call the main function with the parsed arguments
    main(
        date_span=args.date_span,
        n_parallel_days=args.n_parallel_days,
        n_parallel_steps=args.n_parallel_steps,        
        base_path=Path(args.base_path),
        env_path=Path(args.env_path),
        values_per_decision_variable=args.values_per_decision_variable,
        power_threshold=args.power_threshold,
        file_id=file_id,
        full_export=args.full_export
    )