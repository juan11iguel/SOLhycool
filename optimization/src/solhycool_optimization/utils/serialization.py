from enum import Enum
from pathlib import Path
import numpy as np
import pandas as pd
from solhycool_optimization import DayResults  # adjust this import
from loguru import logger
import pygmo as pg
import pandas.api.types as pandas_dtypes 
import warnings
from tables.exceptions import NaturalNameWarning

warnings.filterwarnings("ignore", category=NaturalNameWarning)

def get_queryable_columns(df: pd.DataFrame) -> list[str]:
    return [
        col for col in df.columns
        if (not pandas_dtypes.is_complex_dtype(df[col]) and (pandas_dtypes.is_numeric_dtype(df[col])
                                                             or pandas_dtypes.is_string_dtype(df[col])
                                                             or pandas_dtypes.is_datetime64_any_dtype(df[col])))
    ]

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

def export_results_day(day_results: DayResults, output_path: Path) -> None:
    with pd.HDFStore(output_path, mode='a', complevel=9, complib='zlib') as store:
        for dt, df_pareto, consumption_array in zip(
            day_results.index, day_results.df_paretos, day_results.consumption_arrays
        ):
            table_key = dt.strftime("%Y%m%dT%H%M")

            # Save pareto front for this timestep
            store.put(
                f"/pareto/{table_key}", df_pareto, format="table", data_columns=get_queryable_columns(df_pareto))

            # Save consumption array for this timestep
            df_consumption = pd.DataFrame(consumption_array, columns=["Cw", "Ce"])
            store.put(f"/consumption/{table_key}", df_consumption, format="table", data_columns=True)

            # Save path selection optimization fitness history
            if day_results.fitness_history is not None:
                store.put(f"/paths/fitness_history/{table_key}", day_results.fitness_history, format="table",)

        # Append df_results (path of selected solutions)
        if "/results" in store:
            existing = store["/results"]
            combined = pd.concat([existing, day_results.df_results])
            combined = combined.sort_index()
            store.put("/results", combined, format="table", data_columns=get_queryable_columns(combined))
        else:
            store.put("/results", 
                      day_results.df_results.sort_index(), 
                      format="table", 
                      data_columns=get_queryable_columns(day_results.df_results))

        # Save indices of points in the pareto front and the ones selected from it for each step
        table_key = dt.strftime("%Y%m%d")
        store.put(f"/paths/pareto_idxs/{table_key}", pd.Series(day_results.pareto_idxs))
        store.put(f"/paths/selected_pareto_idxs/{table_key}", pd.Series(day_results.selected_pareto_idxs))

    logger.info(f"Results saved to {output_path}")

def import_results_day(input_path: Path, date_str: str) -> DayResults:
    with pd.HDFStore(input_path, mode='r') as store:
        # Find all pareto keys for the given date
        all_keys = store.keys()
        date_keys = [
            key.split("/")[-1] for key in all_keys
            if key.startswith("/pareto/") and key.split("/")[-1].startswith(date_str)
        ]
        
        if not date_keys:
            avail_dates = np.unique([key.split('/')[-1][:8] for key in all_keys if key.startswith("/pareto/")]).tolist()
            raise ValueError(f"No pareto results found for date {date_str} in {input_path.stem}. Available dates are: {avail_dates}")
        
        # Extract and sort datetime index
        time_index = sorted([
            pd.to_datetime(key, format="%Y%m%dT%H%M").tz_localize("UTC")
            for key in date_keys
        ])

        # Load data for the selected date
        df_paretos = []
        consumption_arrays = []

        for dt in time_index:
            key = dt.strftime("%Y%m%dT%H%M")
            # print(dt, key)
            
            df_paretos.append(store[f"/pareto/{key}"])
            df_consumption = store[f"/consumption/{key}"]
            consumption_arrays.append(df_consumption.to_numpy())
            fitness_history = store.get(f"/paths/fitness_history/{key}")

        # Load df_results (subset for the day)
        df_results = store["/results"]
        df_results = df_results.loc[
            (df_results.index >= time_index[0]) & (df_results.index <= time_index[-1])
        ]

        # Load indices of points in the pareto front and the ones selected from it for each step
        table_key = time_index[0].strftime("%Y%m%d")
        pareto_idxs = store[f"/paths/pareto_idxs/{table_key}"].to_list()
        selected_pareto_idxs = store[f"/paths/selected_pareto_idxs/{table_key}"].to_list()

        # pareto_idxs = [pareto_idxs_series.loc[dt] for dt in time_index]
        # selected_pareto_idxs = [selected_pareto_idxs_series.loc[dt] for dt in time_index]
        # np.concatenate().tolist()

    logger.info(f"DayResults loaded for {date_str} from {input_path}")

    return DayResults(
        index=time_index,
        df_paretos=df_paretos,
        consumption_arrays=consumption_arrays,
        fitness_history=fitness_history,
        df_results=df_results,
        pareto_idxs=pareto_idxs,
        selected_pareto_idxs=selected_pareto_idxs
    )
