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

