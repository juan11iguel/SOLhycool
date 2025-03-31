import time
import numpy as np
import pandas as pd
from tqdm import tqdm
import multiprocessing
import threading
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from dataclasses import asdict
from loguru import logger
import argparse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import combined_cooler
from solhycool_modeling import EnvironmentVariables, OperationPoint
from solhycool_optimization import DecisionVariables, ValuesDecisionVariables
from solhycool_optimization.utils import pareto_front_indices

multiprocessing.set_start_method("spawn", force=True) # MATLAB Engine Cannot Be Used in Forked Processes

@retry(
    stop=stop_after_attempt(3),  # Retry up to 3 times
    wait=wait_exponential(multiplier=2, min=1, max=10),  # Exponential backoff
    retry=retry_if_exception_type(SystemError),  # Retry only on MATLAB runtime errors
)
def safe_evaluate_decision_variables(step_idx, ds, dv_values, total_num_evals, date_str):
    return evaluate_decision_variables(step_idx, ds, dv_values, total_num_evals, date_str)

def evaluate_decision_variables(step_idx: int, ds_env: pd.Series, dv_values: ValuesDecisionVariables, total_num_evals: int, clear_screen: bool = False) -> tuple[list[DecisionVariables], list[list[float], list[float]]]:
    """Evaluates decision variables for a given step."""
    
    # logger.info(f"Starting evaluation for step {step_idx}")
    import combined_cooler
    cc_model = combined_cooler.initialize()
    
    # Prepare environment variables
    ev = EnvironmentVariables.from_series(ds_env).constrain_to_model()
    ev_m = ev.to_matlab()
    
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
                        
                        pbar.update(1)
                        pbar.set_postfix(valid_candidates=len(dv_list))
                        pbar.refresh()
                        
                        # if clear_screen:
                        #     os.system("clear")
    
    return dv_list, consumption_list

def clear_screen_every(interval=10):
    """Clears the screen every `interval` seconds to avoid clutter from progress bars."""
    while True:
        time.sleep(interval)
        os.system("clear")

# Start the screen clearing thread
clear_thread = threading.Thread(target=clear_screen_every, daemon=True)
clear_thread.start()

def main(date_str: str, n_parallel_evals: int, base_path: Path, env_path: Path, values_per_decision_variable: int, power_threshold: float):

    cc_model = combined_cooler.initialize()

    # Load environment into EnvironmentVariables for the episode
    df_env = pd.read_hdf(base_path / env_path)
    df_day = df_env.loc[date_str]
    # Only evaluate steps where power is above some thresholds, otherwise
    # just DC is used
    df_day = df_day[df_day["Q_kW"] > power_threshold]

    # Generate decision variable arrays
    dv_values: ValuesDecisionVariables = ValuesDecisionVariables.initialize(values_per_decision_variable).generate_arrays()
    # Compute total number of evaluations
    total_num_evals = np.prod([len(value) for value in asdict(dv_values).values()])

    logger.info(f"Evaluating operation for {date_str} | Number of evaluations: {total_num_evals} x {len(df_day)}")

    results = []
    start_time = time.time()

    with ProcessPoolExecutor(max_workers=n_parallel_evals) as executor:
        futures = {executor.submit(safe_evaluate_decision_variables, step_idx, ds, dv_values, total_num_evals, date_str): step_idx for step_idx, (dt, ds) in enumerate(df_day.iterrows())}
        for future in as_completed(futures):
            step_idx = futures[future]
            
            try:
                dv_list, consumption_list = future.result()
                consumption_array = np.array(consumption_list).transpose()
                idxs = pareto_front_indices(consumption_array, objective="minimize")

                logger.info(f"Pareto front indices: {idxs}")

                # Generate operation points for the Pareto front
                ev = EnvironmentVariables.from_series(df_day.iloc[step_idx]).constrain_to_model()
                ev_m = ev.to_matlab()
                ops = [
                    OperationPoint.from_multiple_sources(
                        dict_src=cc_model.evaluate_operation(ev_m.Tamb, ev_m.HR, ev_m.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, ev_m.Tv, nargout=3)[2],
                        env_vars=ev,
                        time=df_day.index[step_idx],
                    )
                    for dv in [dv_list[i] for i in idxs]
                ]
                df_paretos = pd.DataFrame([asdict(op) for op in ops])
                results.append((step_idx, df_paretos, consumption_array))
            except Exception as e:
                logger.error(f"Evaluation failed at step {step_idx}: {e}")
    
    logger.info(f"Completed evaluation in {time.time() - start_time:.1f} seconds")

    # Save results to HDF5
    output_path = base_path / f"optimization/results/ops_pareto_fronts_{date_str}.h5"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with pd.HDFStore(output_path, mode='w') as store:
        for step_idx, df_paretos, _ in results:
            store.put(f"step_{step_idx}", df_paretos)
    logger.info(f"Results saved to {output_path}")
    
    # Save consumptions to CSV
    output_path = output_path.parent / f"consumptions_array_{date_str}.h5"
    with pd.HDFStore(output_path, mode='w') as store:
        for step_idx, _, consumption_array in results:
            store.put(f"step_{step_idx}", pd.DataFrame(consumption_array, columns=["Cw", "Ce"]))
    logger.info(f"Pareto front indices saved to {output_path}")
    
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--date_str', type=str, default="20220615", help="Date string in YYYYMMDD format")
    parser.add_argument('--repeat_for_each_month', action='store_true', help="Repeat the evaluation for each provided day in each month of the year starting from the provided month")
    parser.add_argument('--n_parallel_evals', type=int, default=20, help="Number of parallel evaluations")
    parser.add_argument('--base_path', type=str, default="/workspaces/SOLhycool", help="Base path for the project")
    parser.add_argument('--env_path', type=str, default="data/datasets/environment_data_20220101_20241231.h5", help="Path to the environment data file")
    parser.add_argument('--values_per_decision_variable', type=int, default=10, help="Number of values per decision variable")
    parser.add_argument('--power_threshold', type=float, default=100, help="Thermal load power to cool below which only the Dry Cooler is used")

    args = parser.parse_args()
    
    if args.repeat_for_each_month:
        day = args.date_str[-2:]
        year = args.date_str[:4]
        start_month = int(args.date_str[4:6])
        date_strs: list[str] = [f"{year}{month:02d}{day}" for month in range(start_month, 13)]
    else:
        date_strs: list[str] = [args.date_str]

    for date_str in date_strs:
        logger.info(f"Evaluating for date: {date_str}")
        
        # Call the main function with the parsed arguments
        main(
            date_str=date_str,
            n_parallel_evals=args.n_parallel_evals,
            base_path=Path(args.base_path),
            env_path=Path(args.env_path),
            values_per_decision_variable=args.values_per_decision_variable,
            power_threshold=args.power_threshold
        )