from pathlib import Path
from os import unlink
import datetime
import tempfile
import numpy as np
import pandas as pd
from airflow.sdk import dag, task
from loguru import logger
from dataclasses import asdict

from solhycool_optimization import HorizonResults, ValuesDecisionVariables, EvaluationConfig
from solhycool_optimization.problems.horizon.evaluation import evaluate_day
from solhycool_visualization.utils import generate_visualizations
from solhycool_deployment.webdav import init_file_system
from solhycool_deployment import cleanup_paths, welcome_message


@dag(
    schedule=None,
    catchup=False,
    tags=["solhycool", "experimental"],
)
def experimental_horizon_optimization(
    data_url: str = "https://collab.psa.es/s/WR6MxyJsnZWi9xH",
    env_file_id: str = "environment",
    out_file_id: str = "optimization_results",
    optim_id: str = "pilot_plant",
    n_parallel_steps: int = 24,
    values_per_decision_variable: int | None = None,
    plt_config_path: str = "./data/plot_config_day_horizon.hjson",
    optim_config_path: str = "./optimization/data/optimization_config.json",
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
        values_per_decision_variable: int | None,
        optim_config_path: str,
        optim_id: str,
    ) -> str:
        """
        #### Transform task
        In theory this task should call the horizon optimization and then return the results.
        However, for the sake of this example, we will just return precomputed values.
        Initializes HorizonResults and writes it to a temporary file.
        Returns the path to the temp file.
        
        **Args:**
            data_url (str): URL to the remote data storage (e.g., WebDAV endpoint).
            file_id_env (str): Identifier (base filename) for the environment CSV file.
            file_id_results (str): Identifier (base filename) for the output results CSV file.
            n_parallel_steps (int): Number of parallel evaluations to run during optimization.
            values_per_decision_variable (int | None): Number of discrete values to sample per decision variable. 
                If None, uses values from the optimization config.
            optim_config_path (str): Path to the optimization configuration file.
            optim_id (str): Identifier for the optimization configuration within the config file.

        **Returns:**
            str: Path to the temporary HDF5 file containing the optimization results.
            
        **Test this DAG:""
            ```
            airflow dags test experimental_horizon_optimization --conf '{"values_per_decision_variable":4, "plt_config_path":"/workspaces/SOLhycool/data/plot_config_day_horizon.hjson", "optim_config_path": "/workspaces/SOLhycool/optimization/data/optimization_config.json"}'
            ```
        """
        # Load optimization config
        optim_config: EvaluationConfig = EvaluationConfig.from_config_file(Path(optim_config_path), id=optim_id)
        
        # Initialize WebDAV file system
        fs = init_file_system(data_url)

        # Read environment
        df_env = pd.read_csv(fs.open(f'{file_id_env}.csv'), index_col=0, parse_dates=True)
        
        # df_env.index = pd.to_datetime(df_env.index)
        # date_str = df_env.index[0].strftime("%Y%m%d")
        if values_per_decision_variable is not None:
            dv_values=ValuesDecisionVariables.initialize(
                values_per_dv=values_per_decision_variable
            ).generate_arrays(optim_config.model_inputs_range)
        else:
            dv_values=optim_config.vals_dec_vars.generate_arrays(optim_config.model_inputs_range)
        
        # print(dv_values)
        
        # Compute total number of evaluations
        total_num_evals = np.prod([len(value) for value in asdict(dv_values).values()])
        
        day_results = evaluate_day(
            n_parallel_evals=n_parallel_steps,
            df_day=df_env, 
            dv_values=dv_values, 
            total_num_evals=total_num_evals, 
            config=optim_config,
        )
        
        # Initialize WebDAV file system
        fs = init_file_system(data_url)
        
        # Write results table
        day_results.df_results.to_csv(fs.open(f'{file_id_results}.csv', 'w'), index=True)
        
        # Write results to a temporary file for further processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as tmp_file:
            temp_path = Path(tmp_file.name)
            day_results.export(temp_path, reduced=True, single_day=False)

        # return {"total_order_value": str(temp_path), "date_str": day_results.date_str}
        return str(temp_path)
    
    @task()
    def create_results_report(export_path: str, out_url: str, plt_config_path: str) -> None:
        """
        Creates visualization figures and uploads them directly to WebDAV.
        """
        
        # Load results
        day_results = HorizonResults.initialize(Path(export_path))
        
        # Create filename with timestamp
        date_str = day_results.index[0].strftime("%Y%m%d") # datetime.datetime.now().strftime("%Y%m%d")
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        output_dir = f"extended/{date_str}/optimization_results_eval_at_{current_time}/"

        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Load and generate
            generate_visualizations(
                day_results=day_results, 
                output_path=temp_dir_path,
                plot_config_path=Path(plt_config_path),
            )

            # Save the day results
            day_results.export(temp_dir_path / "results.h5", reduced=True, single_day=False)
                
            # Initialize WebDAV file system
            fs = init_file_system(out_url)
            # Copy all files from temp_dir to output_dir before the context exits
            fs.put(f"{str(temp_dir_path)}/", output_dir, recursive=True)

            logger.info(f"Created visualization package in remote folder: {fs.ls(output_dir, detail=False)}")
    
    @task()
    def cleanup(paths: list[str]) -> None:
        """
        #### Cleanup task
        Removes the temporary file created by the transform task.
        This runs after both load and visualization tasks are complete.
        """
        cleanup_paths(paths)
        
    # Pipeline logic
    welcome_message()
    
    export_path = evaluate_optimization(
        data_url=data_url,
        file_id_env=env_file_id,
        file_id_results=out_file_id, 
        n_parallel_steps=n_parallel_steps,
        values_per_decision_variable=values_per_decision_variable,
        optim_config_path=optim_config_path,
        optim_id=optim_id
    )
        
    create_results_report_task = create_results_report(export_path, out_url=data_url, plt_config_path=plt_config_path)

    # Set cleanup dependency
    [export_path, create_results_report_task] >> cleanup([export_path])

experimental_horizon_optimization()
