from pathlib import Path
import datetime
import numpy as np
import pandas as pd
from loguru import logger
from dataclasses import asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import threading
from tqdm import tqdm
import time

from solhycool_optimization import HorizonResults
from solhycool_optimization.problems.horizon.evaluation import evaluate_day
from solhycool_evaluation import SimulationConfig

def update_bar_every(pbar: tqdm, interval=1) -> None:
    """ Updates progress bar every `interval` seconds """
    while True:
        time.sleep(interval)
        pbar.refresh()

def evaluate_optimization(
    sim_config_path: str,
    env_path: str,
    output_path: str,
    sim_id: str,
    date_span: tuple[str, str],
    n_parallel_steps: int,
    n_parallel_days: int,
) -> None:
    """

    """
    # Handle paths
    file_id = f"results_eval_at_{datetime.datetime.now():%Y%m%dT%H%M}_sim_results"
    output_path = Path(output_path) / f"{date_span[0]}_{date_span[1]}/{sim_id}/{file_id}.h5"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get simulation configuration
    sim_config: SimulationConfig = SimulationConfig.from_config_file(sim_config_path, sim_id)
    sim_config.to_config_file(output_path.parent / "sim_config.json")

    # Read environment
    env_path = Path(env_path) / f"{sim_config.env_id}.h5"
    df_env = pd.read_hdf(env_path).loc[date_span[0]:date_span[1]]

    # Compute decision variable arrays
    dv_values=sim_config.vals_dec_vars.generate_arrays(sim_config.model_inputs_range)
            
    total_num_evals = np.prod([len(value) for value in asdict(dv_values).values()])
    start_date = datetime.datetime.strptime(date_span[0], "%Y%m%d").replace(hour=0)
    end_date = datetime.datetime.strptime(date_span[1], "%Y%m%d").replace(hour=23)
    all_dates = list(pd.date_range(start=start_date, end=end_date, freq='D', tz='UTC'))
    batch_size = n_parallel_days  # Number of days to process in parallel
    
    logger.info(f"Starting evaluation for {len(all_dates)} days from {date_span[0]} to {date_span[1]} ({total_num_evals} total evaluations per day).")
    logger.info(f"Results will be saved to: {output_path}")
    logger.info(f"Using environment data from: {env_path}. Available columns: {df_env.columns.tolist()}")
    logger.info(f"Using simulation configuration from: {sim_config_path}. Simulation ID: {sim_id}")
    
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
                    df_day = df_day[df_day["Q_kW"] > sim_config.power_threshold]
                    
                    if not len(df_day) > 0:
                        continue 
                    
                    future = executor.submit(evaluate_day, n_parallel_steps, df_day, dv_values, total_num_evals, sim_config)
                    futures[future] = date_str
                    
                    logger.info(f"[{i+1}/{len(all_dates)}] Submitted {date_str} for evaluation ({len(df_day)} steps / {n_parallel_steps} evaluated in parallel).")

                for future in as_completed(futures):
                    day_results: HorizonResults = future.result()
                    day_results.export(output_path, reduced=True)

                    pbar.update(1)