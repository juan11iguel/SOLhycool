from pathlib import Path
import datetime
from typing import Optional
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

def get_completed_dates_from_results(output_path: Path, log: bool = True) -> set[str]:
    """
    Check what dates are already completed in the output file.
    
    Args:
        output_path: Path to the HDF5 results file
        
    Returns:
        Set of completed date strings in YYYYMMDD format
    """
    if not output_path.exists():
        return set()
    
    try:
        # Try to load existing results without specific date filter to get all available dates
        results = HorizonResults.initialize(output_path, log=False)
        # Extract unique dates from the index
        completed_dates = {dt.strftime("%Y%m%d") for dt in results.index.date}
        if log:
            logger.info(f"Found {len(completed_dates)} completed dates in existing results: {sorted(completed_dates)}")
        return completed_dates
    except Exception as e:
        logger.warning(f"Could not read existing results from {output_path}: {e}")
        return set()

def get_latest_completed_date(completed_dates: set[str]) -> str | None:
    """
    Get the latest (most recent) completed date.
    
    Args:
        completed_dates: Set of completed date strings in YYYYMMDD format
        
    Returns:
        Latest completed date string or None if no dates completed
    """
    if not completed_dates:
        return None
    return max(completed_dates)

def get_remaining_dates(requested_dates: list[datetime.datetime], completed_dates: set[str], start_from_date: str | None = None) -> list[datetime.datetime]:
    """
    Determine which dates from the requested range still need to be evaluated.
    
    Args:
        requested_dates: List of datetime objects for all requested dates
        completed_dates: Set of completed date strings in YYYYMMDD format
        start_from_date: Optional date string (YYYYMMDD) to start evaluation from
        
    Returns:
        List of datetime objects that still need to be evaluated
    """
    remaining = []
    for date in requested_dates:
        date_str = date.strftime("%Y%m%d")
        
        # Skip dates before the start_from_date if specified
        if start_from_date and date_str <= start_from_date:
            continue
            
        if date_str not in completed_dates:
            remaining.append(date)
    
    if len(remaining) < len(requested_dates):
        completed_count = len(requested_dates) - len(remaining)
        logger.info(f"Found {completed_count} already completed dates, {len(remaining)} remaining to evaluate")
        if start_from_date:
            logger.info(f"Starting evaluation from date after {start_from_date}")
    
    return remaining

def update_bar_every(pbar: tqdm, interval=1) -> None:
    """ Updates progress bar every `interval` seconds """
    while True:
        time.sleep(interval)
        pbar.refresh()

def evaluate_optimization_robust(
    sim_config_path: str,
    env_path: str,
    output_path: str,
    sim_id: str,
    date_span: tuple[str, str],
    n_parallel_steps: int,
    n_parallel_days: int,
    file_id: Optional[str] = None,
) -> None:
    """
    Robust wrapper for evaluate_optimization that handles SystemError and resumes from existing results.
    
    This function provides robust evaluation by:
    1. Checking for existing results and resuming from where it left off
    2. Catching SystemError and other process-related exceptions
    3. Retrying failed evaluations as long as progress is made in each attempt
    4. Preserving completed work between retries
    
    Args:
        sim_config_path: Path to simulation configuration file
        env_path: Path to environment data directory  
        output_path: Base output directory path
        sim_id: Simulation ID identifier
        date_span: Tuple of (start_date, end_date) in YYYYMMDD format
        n_parallel_steps: Number of parallel steps for each day evaluation
        n_parallel_days: Number of days to process in parallel
    """
    retry_count = 0
    # Check initial state - use the full output path that will be created
    if file_id is None:
        file_id = f"results_eval_at_{datetime.datetime.now():%Y%m%dT%H%M}_sim_results"
    full_output_path = Path(output_path) / f"{date_span[0]}_{date_span[1]}/{sim_id}/{file_id}.h5"
    
    n_completed_dates0 = len(get_completed_dates_from_results(full_output_path, log=False))
    n_completed_dates = n_completed_dates0

    while (n_completed_dates - n_completed_dates0 > 0) or (retry_count == 0):
        try:
            # Check for existing results and determine remaining dates to process
            completed_dates = get_completed_dates_from_results(full_output_path)
            
            # Generate full date range
            start_date = datetime.datetime.strptime(date_span[0], "%Y%m%d").replace(hour=0)
            end_date = datetime.datetime.strptime(date_span[1], "%Y%m%d").replace(hour=23)
            all_requested_dates = list(pd.date_range(start=start_date, end=end_date, freq='D', tz='UTC'))
            
            # Smart restart: start from the latest completed date (not from the beginning)
            latest_completed = get_latest_completed_date(completed_dates)
            
            # Get remaining dates to process, starting from after the latest completed date
            remaining_dates = get_remaining_dates(all_requested_dates, completed_dates, latest_completed)
            
            if not remaining_dates:
                logger.info(f"All dates in range {date_span[0]} to {date_span[1]} are already completed!")
                return
                
            logger.info(f"Found {len(completed_dates)} completed dates so far. {len(remaining_dates)} dates still need processing.")
            if latest_completed:
                logger.info(f"Latest completed date: {latest_completed}. Resuming from next unprocessed date.")
            logger.info(f"Next dates to process: {[d.strftime('%Y%m%d') for d in remaining_dates[:5]]}{'...' if len(remaining_dates) > 5 else ''}")
            
            # Calculate date span for remaining dates only (more efficient)
            remaining_start = remaining_dates[0].strftime("%Y%m%d")
            remaining_end = remaining_dates[-1].strftime("%Y%m%d")
            updated_date_span = (remaining_start, remaining_end)
            
            logger.info(f"Starting robust evaluation attempt {retry_count + 1}")
            logger.info(f"Processing date range {updated_date_span[0]} to {updated_date_span[1]} ({len(remaining_dates)} dates to evaluate)")
            
            # Call the original evaluation function with remaining dates
            evaluate_optimization(
                sim_config_path=sim_config_path,
                env_path=env_path,
                output_path=full_output_path,
                sim_id=sim_id,
                date_span=updated_date_span,
                n_parallel_steps=n_parallel_steps,
                n_parallel_days=n_parallel_days,
                file_id=file_id,
            )
            
            # If we get here, evaluation completed successfully
            logger.info("Evaluation completed successfully!")
            return
            
        except (ProcessLookupError, BrokenPipeError, ConnectionError, SystemError, TypeError) as e:
            retry_count += 1
            n_completed_dates = len(get_completed_dates_from_results(full_output_path))
            logger.error(f"SystemError encountered (attempt {retry_count + 1}): {e}")
            
            time.sleep(5)
            
    raise RuntimeError(f"Evaluation failed after {retry_count} retries with no progress.")
                

def evaluate_optimization(
    sim_config_path: str,
    env_path: str,
    output_path: str,
    sim_id: str,
    date_span: tuple[str, str],
    n_parallel_steps: int,
    n_parallel_days: int,
    file_id: Optional[str] = None,
) -> None:
    """
    Evaluate optimization results for a range of dates with parallel processing.
    
    This function has been enhanced with error handling for SystemError and other 
    process-related exceptions. For robust operation with automatic retry and resume
    capabilities, use evaluate_optimization_robust() instead.
    
    Args:
        sim_config_path: Path to simulation configuration file
        env_path: Path to environment data directory
        output_path: Base output directory path
        sim_id: Simulation ID identifier
        date_span: Tuple of (start_date, end_date) in YYYYMMDD format
        n_parallel_steps: Number of parallel steps for each day evaluation
        n_parallel_days: Number of days to process in parallel
        
    Raises:
        SystemError: If there are process-related issues during parallel execution
        ProcessLookupError: If process pool encounters issues
        BrokenPipeError: If communication between processes fails
        ConnectionError: If there are connection issues between processes
    """
    # Handle paths
    if file_id is None:
        file_id = f"results_eval_at_{datetime.datetime.now():%Y%m%dT%H%M}_sim_results"
        output_path = Path(output_path) / f"{date_span[0]}_{date_span[1]}/{sim_id}/{file_id}.h5"
    else:
        # When file_id is provided, output_path should already be the full path
        output_path = Path(output_path)
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
            try:
                with ProcessPoolExecutor(max_workers=len(batch_dates)) as executor:
                    for date in batch_dates:
                        date_str = date.strftime("%Y%m%d")
                        
                        try:
                            df_day = df_env.loc[date_str]
                        except KeyError:
                            logger.warning(f"No environment data available for {date_str}, skipping")
                            pbar.update(1)
                            continue
                        # Only evaluate steps where power is above some thresholds, otherwise just DC is used
                        df_day = df_day[df_day["Q_kW"] > sim_config.power_threshold]
                        
                        if not len(df_day) > 0:
                            continue 
                        
                        future = executor.submit(evaluate_day, n_parallel_steps, df_day, dv_values, total_num_evals, sim_config)
                        futures[future] = date_str
                        
                        logger.info(f"[{i+1}/{len(all_dates)}] Submitted {date_str} for evaluation ({len(df_day)} steps / {n_parallel_steps} evaluated in parallel).")

                    # Only process futures if any were submitted
                    if futures:
                        for future in as_completed(futures):
                            date_str = futures[future]
                            try:
                                day_results: Optional[HorizonResults] = future.result()
                                
                                # Check if results are None (no valid operations found for entire day)
                                if day_results is None:
                                    logger.warning(f"No valid operations found for entire day {date_str} (all steps dropped or no feasible solutions)")
                                    pbar.update(1)
                                    continue
                                    
                                # Additional check for empty results (shouldn't happen with None return, but defensive)
                                if (day_results.df_results.empty or len(day_results.df_results) == 0 or 
                                    day_results.index.empty or len(day_results.df_paretos) == 0):
                                    logger.warning(f"Empty results returned for {date_str} (unexpected - should be None)")
                                    pbar.update(1)
                                    continue
                                    
                                day_results.export(output_path, reduced=True)
                                pbar.update(1)
                            except IndexError as e:
                                logger.warning(f"IndexError during evaluation of {date_str}: {e}")
                                logger.warning(f"This likely indicates insufficient data points or no valid operations. Skipping {date_str}.")
                                pbar.update(1)
                                continue  # Skip this date and continue with others
                            except SystemError as e:
                                logger.error(f"SystemError during evaluation of {date_str}: {e}")
                                raise  # Re-raise to be caught by the wrapper function
                            except Exception as e:
                                logger.error(f"Error during evaluation of {date_str}: {e}")
                                raise  # Re-raise to be caught by the wrapper function
                    else:
                        logger.debug(f"No new dates to process in batch {i//batch_size + 1} (all already completed or no valid data)")
                            
            except (SystemError, ProcessLookupError, BrokenPipeError, ConnectionError) as e:
                logger.error(f"Process pool error in batch {i//batch_size + 1}: {e}")
                raise  # Re-raise to be caught by the wrapper function