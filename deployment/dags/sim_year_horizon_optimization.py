from pathlib import Path
import datetime
from airflow.sdk import dag, task
from loguru import logger

from solhycool_evaluation.evaluation import evaluate_optimization as evaluate
from solhycool_deployment import welcome_message


@dag(
    schedule=None,
    catchup=False,
    tags=["solhycool", "simulation"],
)
def sim_year_horizon_optimization(
    sim_id: str = None,
    sim_config_path: str = "/workspaces/SOLhycool/simulation/data/simulations_config.json",
    env_path: str = "/workspaces/SOLhycool/data/datasets/",
    output_path: str = "/workspaces/SOLhycool/simulation/results/", 
    date_span: tuple[str, str] = ("20220101", "20221231"),
    n_parallel_steps: int = 24,
    n_parallel_days: int = 5,
):
    """
    ### Annual simulation of the horizon optimization strategy DAG
    ...
    
    **Test this DAG:**
    ```
    airflow dags test sim_year_horizon_optimization --conf '{"sim_id": "pilot_plant_wct100_dc100", "date_span": [20220505,20220510], "optim_config_path": "/workspaces/SOLhycool/optimization/data/optimization_config.json"}'
    ```
        
    """
    @task() # multiple_outputs=True
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
        #### Transform task
        In theory this task should call the horizon optimization and then return the results.
        However, for the sake of this example, we will just return precomputed values.
        Initializes HorizonResults and writes it to a temporary file.
        Returns the path to the temp file.
        """
        
        evaluate(
            sim_config_path=sim_config_path,
            env_path=env_path,
            output_path=output_path,
            sim_id=sim_id,
            date_span=date_span,
            n_parallel_steps=n_parallel_steps,
            n_parallel_days=n_parallel_days,
        )
        
    # @task()
    # def create_results_report(export_path: str, out_url: str, plt_config_path: str) -> None:
    #     """
    #     Creates visualization figures and uploads them directly to WebDAV.
    #     """
        
    #     # Load results
    #     day_results = HorizonResults.initialize(Path(export_path))
        
    #     # Create filename with timestamp
    #     date_str = day_results.index[0].strftime("%Y%m%d") # datetime.datetime.now().strftime("%Y%m%d")
    #     current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    #     output_dir = f"extended/{date_str}/optimization_results_eval_at_{current_time}/"

        
    #     with tempfile.TemporaryDirectory() as temp_dir:
    #         temp_dir_path = Path(temp_dir)

    #         # Load and generate
    #         generate_visualizations(
    #             day_results=day_results, 
    #             output_path=temp_dir_path,
    #             plot_config_path=Path(plt_config_path),
    #         )

    #         # Save the day results
    #         day_results.export(temp_dir_path / "results.h5", reduced=True, single_day=False)
                
    #         # Initialize WebDAV file system
    #         fs = init_file_system(out_url)
    #         # Copy all files from temp_dir to output_dir before the context exits
    #         fs.put(f"{str(temp_dir_path)}/", output_dir, recursive=True)

    #         logger.info(f"Created visualization package in remote folder: {fs.ls(output_dir, detail=False)}")
    
    # @task()
    # def cleanup(paths: list[str]) -> None:
    #     """
    #     #### Cleanup task
    #     Removes the temporary file created by the transform task.
    #     This runs after both load and visualization tasks are complete.
    #     """
    #     cleanup_paths(paths)
        
    # Pipeline logic
    welcome_message()
    
    evaluate_optimization(
        sim_id=sim_id,
        sim_config_path=sim_config_path,
        env_path=env_path,
        output_path=output_path, 
        date_span=date_span,
        n_parallel_steps=n_parallel_steps,
        n_parallel_days=n_parallel_days
    )
        
    # create_results_report_task = create_results_report(export_path, out_url=data_url, plt_config_path=plt_config_path)

    # Set cleanup dependency
    # [export_path, create_results_report_task] >> cleanup([export_path])

sim_year_horizon_optimization()
