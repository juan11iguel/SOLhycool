import shutil
import tarfile
from enum import Enum
from pathlib import Path
import numpy as np
import pandas as pd
from loguru import logger
import pygmo as pg
import pandas.api.types as pandas_dtypes 
import warnings
from tables.exceptions import NaturalNameWarning

warnings.filterwarnings("ignore", category=NaturalNameWarning)

class AlgoLogColumns(Enum):
    """Enum for the algorithm logs columns."""
    
    GACO = ["Gen", "Fevals", "Best", "Kernel", "Oracle", "dx", "dp"]
    SGA = ["Gen", "Fevals", "Best", "Improvement"]
    NSGA2 = ["Gen", "Fevals", "ideal_point"]
    SIMULATED_ANNEALING = ["Fevals", "Best", "Current", "Mean range", "Temperature"]
    DE = ["Gen", "Fevals", "Best", "dx", "df"]
    CMAES = ["Gen", "Fevals", "Best", "dx", "df", "sigma"]
    SEA = ["Gen", "Fevals", "Best", "Improvement", "Mutations"]
    PSO_GEN = ["Gen", "Fevals", "gbest", "Mean Vel.", "Mean lbest", "Avg. Dist."]
    SADE = ["Gen", "Fevals", "Best", "F", "CR", "dx", "df"]
    IPOPT = ["objevals","objval","violated","viol. norm", "valid"]
    COMPASS_SEARCH = ["objevals","objval","violated","viol. norm", "valid"]
    MBH = ["objevals","objval","violated","viol. norm", "valid"]
    IHS= ["Fevals", "ppar", "bw", "dx", "df", "Violated", "Viol. Norm", "ideal1"] 
    
    @property
    def columns(self) -> list[str]:
        return self.value

def get_queryable_columns(df: pd.DataFrame) -> list[str]:
    return [
        col for col in df.columns
        if (not pandas_dtypes.is_complex_dtype(df[col]) and (pandas_dtypes.is_numeric_dtype(df[col])
                                                             or pandas_dtypes.is_string_dtype(df[col])
                                                             or pandas_dtypes.is_datetime64_any_dtype(df[col])))
    ]

def get_fitness_history(algo_id: str, algo_log: pg.algorithm | pd.DataFrame |  list[tuple[int|float]], possible_fitness_keys: list[str] = ["Best", "gbest", "objval", "ideal1"]) -> pd.Series:
    """
    Extracts the fitness history from the algorithm log.
    
    Args:
        algo_log (pd.DataFrame | list[tuple[int|float]]): Algorithm log, either as a DataFrame or a list of tuples.
        possible_fitness_keys (list[str]): List of possible fitness keys to look for in the log.
        
    Returns:
        pd.Series: Series containing the fitness history with number of objective function evaluations as the index.
    """
    if not isinstance(algo_log, pd.DataFrame):
        if isinstance(algo_log, pg.algorithm):
            algo_log = algo_log.extract(getattr(pg, algo_id)).get_log()
        try:
            algo_log = pd.DataFrame(algo_log, columns=AlgoLogColumns[algo_id.upper()].columns)
        except ValueError as e:
            raise ValueError(f"Invalid algo_log format for {algo_id}: {e}")
    # Extract fitness history
    fitness_value = None
    for key in possible_fitness_keys:
        if key in algo_log.columns:
            fitness_value = algo_log[key].values
            break
    if fitness_value is None:
        raise KeyError(f"None of the possible fitness keys {possible_fitness_keys} found in case study")
    
    # Create a Series with the number of objective function evaluations as the index
    fitness_history = pd.Series(fitness_value, index=algo_log["Fevals"].values)
    
    return fitness_history

def load_optimization_results(results_path: Path, ) -> tuple[pd.DataFrame, str]:
    """    Load optimization results from a compressed archive and return the results DataFrame.
    Args:
        results_path (Path): Path to the compressed optimization results archive.
    Returns:
        pd.DataFrame: DataFrame containing the optimization results.
        
    Example:
        df_results = load_optimization_results(
            results_path = data_path / "datasets/experimental/optimization_results_eval_at_20250725_1028.tar.gz",
        )
    """

    from solhycool_optimization import DayResults # Import here to avoid circular import issues

    # Define a temporary extraction directory
    extract_dir = results_path.parent / "extracted_results"
    extract_dir.mkdir(exist_ok=True)

    # Extract the tar.gz archive
    with tarfile.open(results_path, "r:gz") as tar:
        tar.extractall(path=extract_dir, filter="data")

    # Find the results.h5 file (assuming only one)
    results_h5 = next(extract_dir.rglob("results.h5"))

    # Load with DayResults.initialize
    day_results = DayResults.initialize(results_h5)

    # Optional: clean up extracted files after loading (uncomment to enable)
    shutil.rmtree(extract_dir)
    
    # Extract date from filename
    eval_time = results_path.stem.split("eval_at_")[-1].split(".")[0]  
    
    return day_results.df_results, eval_time

def load_multiple_optimization_results(results_dir: Path, date_str: str) -> tuple[list[pd.DataFrame], list[str], pd.DataFrame]:
    """
        The joined dataframe is built by "masking by precedence" behavior, where:
            - Each DataFrame contains indexed values (e.g., by step, timestamp, or some id).
            - If a newer DataFrame contains values at a given index, you want to ignore all values from older DataFrames starting from that index onward, even for rows not duplicated.
            - This means older DataFrames contribute only up to the earliest index present in any newer DataFrame.
    """
    results_files = sorted(results_dir.glob(f"*{date_str}*.tar.gz"))  # Oldest to newest
    
    dfs, eval_times = zip(*[load_optimization_results(results_path) for results_path in results_files])
    
    # Start merging from oldest to newest, but apply masking
    kept_indices = set()
    merged_parts = []

    for df in reversed(dfs):  # Process from newest to oldest
        new_rows = df.loc[~df.index.isin(kept_indices)]
        kept_indices.update(new_rows.index)
        merged_parts.append(new_rows)

    # merged_parts has newest first, so reverse back to original order
    merged_df = pd.concat(reversed(merged_parts)).sort_index()

    return list(dfs), eval_times, merged_df