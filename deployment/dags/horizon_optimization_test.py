from pathlib import Path
from os import unlink
import datetime
import tempfile
import numpy as np
import pandas as pd
from dataclasses import asdict
from loguru import logger
from airflow.sdk import dag, task

from solhycool_optimization import DayResults, ValuesDecisionVariables
from solhycool_optimization.problems.horizon.evaluation import evaluate_day
from solhycool_optimization.problems.horizon import AlgoParams
from solhycool_visualization.utils import generate_visualizations
from deployment.webdav import init_file_system

def create_mock_day_results(date_str: str, template_path: Path, template_date_str: str = "20220501") -> DayResults:
    """
    Create a new DayResults object with the same content as the template,
    but with timestamps shifted to match the given date_str.
    """
    # 1. Load from existing file
    original = DayResults.initialize(template_path, date_str=template_date_str)

    # 2. Convert new date_str to datetime
    new_date = pd.to_datetime(date_str, format="%Y%m%d")
    old_date = pd.to_datetime(template_date_str, format="%Y%m%d")
    delta_days = (new_date - old_date).days

    # 3. Shift index and time-dependent fields
    new_index = original.index + pd.Timedelta(days=delta_days)
    new_df_results = original.df_results.copy()
    new_df_results.index = new_df_results.index + pd.Timedelta(days=delta_days)

    # Optional: shift fitness history index if needed (not always datetime-indexed)
    if original.fitness_history is not None:
        fitness_history = original.fitness_history.copy()
        if isinstance(fitness_history.index, pd.DatetimeIndex):
            fitness_history.index = fitness_history.index + pd.Timedelta(days=delta_days)
    else:
        fitness_history = None

    return DayResults(
        index=new_index,
        df_paretos=original.df_paretos,  # usually per-timestep, no timestamp inside
        fitness_history=fitness_history,
        selected_pareto_idxs=original.selected_pareto_idxs,
        df_results=new_df_results,
        consumption_arrays=original.consumption_arrays,
        pareto_idxs=original.pareto_idxs,
        date_str=date_str
    )
    
@dag(
    schedule=None,
    catchup=False,
    tags=["solhycool"],
)
def horizon_optimization_test(
    webdav_url: str = "https://collab.psa.es/s/WR6MxyJsnZWi9xH",
    env_file_id: str = "environment",
    out_file_id: str = "optimization_results_test",
    n_parallel_steps: int = 24,
    values_per_decision_variable: int = 10,
    plt_config_path: str = "./data/plot_config_day_horizon.hjson"
):
    """
    ### Experimental evaluation of Horizon Optimization DAG
    This is a simple data pipeline test DAG that reads data from a Nextcloud 
    public link, extracts it
    
    
    1. Download and read optimization_results.csv
    2. Replace rows that overlap with the current results and append new rows
    3. Upload the updated file back to the share
    4. Create a folder f"eval_at_{YYYYMMDDTHHMM}" with:
        - `environment_data_{datetime_str}.csv` file
        - `optimization_results_{datetime_str}.csv` file
        - report.md with static plots
        - report.html which includes interactive plots
        - results plots both in png and html format
        - some json files with results objects
        
    """
        
    @task() # multiple_outputs=True
    def evaluate_optimization(
        data_url: str,
        file_id_env: str,
        file_id_results: str,
        n_parallel_steps: int,
        values_per_decision_variable: int,
        algo_params: AlgoParams = AlgoParams(),
    ) -> str:
        """
        #### Transform task
        In theory this task should call the horizon optimization and then return the results.
        However, for the sake of this example, we will just return precomputed values.
        Initializes DayResults and writes it to a temporary file.
        Returns the path to the temp file.
        """
        # Initialize WebDAV file system
        fs = init_file_system(data_url)

        # Read environment
        df_env = pd.read_csv(fs.open(f'{file_id_env}.csv'), index_col=0, parse_dates=True)

        # Manipulate dates in results to match the date_str
        template_date_str: str = "20220501"
        template_path: Path = Path("/workspaces/SOLhycool/deployment/dags/results_eval_at_20250421T1741_psa_partial.gz")
        
        day_results = create_mock_day_results(
            date_str=datetime.datetime.now().strftime("%Y%m%d"),
            template_path=template_path,
            template_date_str=template_date_str
        )
        
        # Write results table
        day_results.df_results.to_csv(fs.open(f'{file_id_results}.csv', 'w'), index=True)
        
        # Write results to a temporary file for further processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as tmp_file:
            temp_path = Path(tmp_file.name)
            day_results.export(temp_path, reduced=True, single_day=False)

        # return {"total_order_value": str(temp_path), "date_str": day_results.date_str}
        return str(temp_path)
        
    @task()
    def results_report(export_path: str, out_url: str, plt_config_path: str) -> None:
        """
        Creates visualization figures and packages everything into a compressed file.
        """
        # Initialize WebDAV file system
        fs = init_file_system(out_url)
        
        # Create filename with timestamp
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        output_dir = f"{date_str}/optimization_results_eval_at_{current_time}/"

        # Load results
        day_results = DayResults.initialize(Path(export_path))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            
            temp_dir_path = Path(temp_dir)

            generate_visualizations(
                day_results=day_results, 
                output_path=temp_dir_path,
                plot_config_path=Path(plt_config_path),
            )

            # Save the day results
            day_results.export(temp_dir_path / "results.h5", reduced=True)
                
            # Copy all files from temp_dir to output_dir BEFORE the context exits
            fs.put(f"{str(temp_dir_path)}/", output_dir, recursive=True)

            logger.info(f"Created visualization package in remote folder: {fs.ls(output_dir, detail=False)}")

    @task()
    def cleanup(paths: list[str]) -> None:
        """
        #### Cleanup task
        Removes the temporary file created by the transform task.
        This runs after both load and visualization tasks are complete.
        """
        for path_ in paths:
            p = Path(path_)
            if not p.exists():
                logger.warning(f"Cleanup: {p} does not exist, skipping deletion.")
                continue
                        
            # Clean up archive file
            unlink(p)            
            logger.info(f"Cleanup: Deleting temporary file {p}")
            
       
    # Pipeline logic
    export_path = evaluate_optimization(
        data_url=webdav_url,
        file_id_env=env_file_id,
        file_id_results=out_file_id, 
        n_parallel_steps=n_parallel_steps,
        values_per_decision_variable=values_per_decision_variable
    )
        
    results_report_task = results_report(export_path, out_url=webdav_url, plt_config_path=plt_config_path)

    # Set cleanup dependency
    [export_path, results_report_task] >> cleanup([export_path])

horizon_optimization_test()
