from pathlib import Path
import json
from datetime import datetime
import numpy as np
import pandas as pd
from loguru import logger
from enum import Enum

from solhycool_optimization.utils.serialization import get_fitness_history, AlgoLogColumns

# TODO: Move to phd_utils
class CustomEncoder(json.JSONEncoder):
    """ Custom JSON encoder supporting NumPy arrays, pandas objects, and Enums """
    
    def default(self, obj):
        if isinstance(obj, np.ndarray):  # Handle NumPy arrays
            return obj.tolist()
        elif isinstance(obj, pd.Series):  # Handle pandas Series (keep index)
            return obj.to_dict()
        elif isinstance(obj, pd.DataFrame):  # Handle pandas DataFrame
            return obj.to_dict(orient="records")
        elif isinstance(obj, Enum):  # Handle Enums
            return obj.value
        return super().default(obj)

# class FilenamesMapping(Enum):
#     """Enum for the file ids to filenames mapping."""
    
#     METADATA = "metadata.json"
#     PROBLEM_PARAMS = "problem_params.json"
#     INITIAL_STATES = "initial_states.json"
#     ALGO_LOGS = "algo_logs.h5"
#     OPTIM_DATA = "optim_data.h5"
#     DF_HORS = "df_hors.h5"
#     DF_SIM = "df_sim.h5"
    
#     @property
#     def fn(self) -> str:
#         return self.value
    
def step_idx_to_step_id(step_idx: int) -> str:
    return f"step_{step_idx:03d}"
    
def export_evaluation_results(results_dict: dict, metadata:dict,
                              output_path: Path, 
                              algo_logs: list[ pd.DataFrame ] | list[ list[tuple[int|float]] ] = None, 
                              algo_table_ids: list[str] = None,
                              df_opt: pd.DataFrame = None,
                              df_sim: pd.DataFrame = None,
                              file_id: str = None,
                              fitness_history: list[list[float]] = None) -> None:
    """
    Exports evaluation results to an HDF5 file and a JSON file.
    Args:
        results_dict (dict): Dictionary containing the results of the algorithm comparison.
        metadata (dict): Metadata information related to the algorithm comparison.
        problem_params (ProblemParameters): Parameters of the problem being solved.
        algo_logs (list[pd.DataFrame] | list[list[tuple[int | float]]]): List of algorithm logs, either as DataFrames or lists of tuples.
        algo_ids (list[str]): List of algorithm identifiers.
        table_ids (list[str]): List of table identifiers for storing logs in the HDF5 file.
        output_path (Path): Path to the output directory where the files will be saved.
    Raises:
        KeyError: If none of the possible fitness keys are found in the algorithm logs.
    Returns:
        None
    """
    
    if file_id is None:
        file_id = f"eval_at_{datetime.now():%Y%m%dT%H%M}"
    
    # Extract algorithm logs
    if algo_logs is not None:
        assert algo_table_ids is not None, "algo_table_ids must be provided if algo_logs is provided"
        algo_id = metadata["algo_id"]
        for idx, algo_log in enumerate(algo_logs):
            if not isinstance(algo_log, pd.DataFrame):
                algo_logs[idx] = pd.DataFrame(algo_log, columns=AlgoLogColumns[algo_id.upper()].columns)
        
        out_path = output_path / f"algo_logs_{file_id}.h5"
        with pd.HDFStore(out_path, mode='a') as store:
            [store.put(f"log_{table_id}", algo_log) for algo_log, table_id in zip(algo_logs, algo_table_ids)]
        logger.info(f"Exported algorithm logs to {out_path}")
        
        # Export results dictionary
        # Add fitness_history to the results dict
        possible_fitness_keys: list[str] = ["Best", "gbest", "objval"]
        date_str: str = algo_table_ids[0][:-3]
        if fitness_history is None:
            results_dict[date_str]["fitness_history"] = []
            for idx, algo_log in enumerate(algo_logs):
                # Extract for algorithm logs
                fitness_value = None
                for key in possible_fitness_keys:
                    if key in algo_log.columns:
                        fitness_value = algo_log[key].values
                        break
                if fitness_value is None:
                    raise KeyError(f"None of the possible fitness keys {possible_fitness_keys} found in case study")
                # print(f"Case study: {cs_id} | Fitness: {fitness_value}")
                results_dict[date_str]["fitness_history"].append(fitness_value) 
        else:
            # Use the provided one
            results_dict[date_str]["fitness_history"] = fitness_history
        
    
    out_path = output_path / f"eval_results_{file_id}.json"
    if out_path.exists():
        # Just update the results dict
        output_dict = json.loads(out_path.read_text())
        output_dict["results"].update(results_dict)
    else:
        output_dict = {
            "metadata": metadata,
            "results": results_dict,
        }
    with open(out_path, "w") as f:
        json.dump(output_dict, f, indent=4, cls=CustomEncoder)
    logger.info(f"Exported evaluation results to {out_path}")
    
    # Export optimization results
    if df_opt is not None:
        out_path = output_path / f"df_opt_{file_id}.h5"
        # df_opt_new = pd.DataFrame([asdict(op) for op in operation_points], index=df_sim.index[-len(operation_points):])
        if out_path.exists():
            df_opt = pd.concat([pd.read_hdf(out_path), df_opt])
        df_opt.to_hdf(out_path, key="optimization_results")
        logger.info(f"Exported optimziation results to {out_path}")
    
    # Export simulation data
    if df_sim is not None:
        out_path = output_path / f"df_sim_{file_id}.h5"
        if out_path.exists():
            df_sim = pd.concat([pd.read_hdf(out_path), df_sim])
            # Remove duplicates
            df_sim = df_sim[~df_sim.index.duplicated(keep='last')]
            # Order by index
            df_sim = df_sim.sort_index()
        df_sim.to_hdf(out_path, key="simulation_data")
        logger.info(f"Exported simulation data to {out_path}")
    