from pathlib import Path
from os import unlink
import datetime
import tempfile
import numpy as np
import pandas as pd
import requests
from io import StringIO
import shutil
from airflow.sdk import dag, task
from loguru import logger
from dataclasses import asdict

from solhycool_optimization import DayResults, ValuesDecisionVariables
from solhycool_optimization.problems.horizon.evaluation import evaluate_day
from solhycool_optimization.problems.horizon import AlgoParams
from solhycool_visualization.utils import generate_visualizations
from deployment import get_data, extract_url_components, build_file_url


@dag(
    schedule=None,
    catchup=False,
    tags=["solhycool"],
)
def horizon_optimization(
    data_url: str = "https://collab.psa.es/s/WR6MxyJsnZWi9xH",
    env_file_id: str = "environment",
    out_file_id: str = "optimization_results",
    n_parallel_steps: int = 24,
    values_per_decision_variable: int = 10,
):
    """
    ### Basic ETL DAG
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
    @task()
    def read_environment(url: str, file_id: str) -> pd.DataFrame:
        """
        #### Extract task
        A simple Extract task to get data ready for the rest of the data
        pipeline
        """
        
        request_url = build_file_url(            
            url=url,
            file_id=file_id,
            ext="csv"
        )
                
        logger.info(f"extract: {request_url=}")
        
        return get_data(request_url)
        
    @task() # multiple_outputs=True
    def evaluate_optimization(
        df_env: pd.DataFrame,
        n_parallel_steps: int,
        values_per_decision_variable: int,
        algo_params: AlgoParams = AlgoParams()
    ) -> str:
        """
        #### Transform task
        In theory this task should call the horizon optimization and then return the results.
        However, for the sake of this example, we will just return precomputed values.
        Initializes DayResults and writes it to a temporary file.
        Returns the path to the temp file.
        """
        df_env.index = pd.to_datetime(df_env.index)
        # date_str = df_env.index[0].strftime("%Y%m%d")
        dv_values=ValuesDecisionVariables.initialize(
            values_per_dv=values_per_decision_variable
        ).generate_arrays()
        
        # print(dv_values)
        
        # Compute total number of evaluations
        total_num_evals = np.prod([len(value) for value in asdict(dv_values).values()])
        
        day_results = evaluate_day(
            n_parallel_evals=n_parallel_steps,
            df_day=df_env, 
            dv_values=dv_values, 
            total_num_evals=total_num_evals, 
            path_selector_params=algo_params,
        )
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as tmp_file:
            temp_path = Path(tmp_file.name)
            day_results.export(temp_path, reduced=True,)

        # return {"total_order_value": str(temp_path), "date_str": day_results.date_str}
        return str(temp_path)
    
    @task()
    def write_optimization_results(url: str, file_id: str, export_path: str) -> None:
        """
        #### Load task
        A simple Load task which takes in the result of the Transform task and
        instead of saving it to end user review, just logger.infos it out.
        
        Reads DayResults from the given file and uploads results as CSV.
        
        WARNING: Using the local file system for temporary storage. 
        This is not recommended for production use.
        Instead, we should be using a distributed file system or object storage.
        See: https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html#communication

        """
        domain, share_id = extract_url_components(url)
        
        request_url = build_file_url(            
            domain=domain,
            file_id=file_id,
            ext="csv"
        )
        
        day_results = DayResults.initialize(Path(export_path))

        # Create a temporary directory for results
        # Generate visualization and report files
        # This should be done in a separate task
        
        # Upload results csv file
        # Convert DataFrame to CSV in-memory
        csv_buffer = StringIO()
        day_results.df_results.to_csv(csv_buffer, index=True)
        csv_buffer.seek(0)  # rewind to beginning
        
        # Upload using HTTP PUT
        response = requests.put(
            request_url,
            data=csv_buffer,
            auth=(share_id, '')  # empty password
        )
        
        # Check response
        if response.status_code == 201 or response.status_code == 204:
            logger.info("Upload successful!")
        else:
            logger.error(f"Upload failed: {response.status_code} - {response.text}")
    
    @task()
    def create_results_report(export_path: str) -> str:
        """
        Creates visualization figures and packages everything into a compressed file.
        Returns the path to the compressed temp file.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Load and generate
            day_results = DayResults.initialize(Path(export_path))
            generate_visualizations(day_results=day_results, output_path=temp_dir_path)

            # Save the day results
            day_results_path = temp_dir_path / "day_results.h5"
            day_results.export(day_results_path, reduced=True)

            # Create archive directly
            archive_base = Path(tempfile.mktemp(suffix=""))  # Don't add .tar.gz manually
            archive_path = shutil.make_archive(
                str(archive_base),
                format='gztar',
                root_dir=temp_dir
            )

            logger.info(f"Created visualization package: {archive_path}")
            return str(archive_path)
    
    @task()
    def write_results_report(url: str, archive_path: str) -> None:
        """
        #### Load package task
        Uploads the compressed visualization package to the webdav server.
        """
        domain, share_id = extract_url_components(url)
        
        # Create filename with timestamp
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        file_id = f"optimization_results_eval_at_{current_time}"
        
        request_url = build_file_url(            
            domain=domain,
            file_id=file_id,
            ext="tar.gz"
        )
        
        # Upload the compressed file
        with open(archive_path, 'rb') as f:
            response = requests.put(
                request_url,
                data=f,
                auth=(share_id, '')  # empty password
            )
        
        # Check response
        if response.status_code == 201 or response.status_code == 204:
            logger.info(f"Package upload successful: {file_id}.tar.gz")
        else:
            logger.info(f"Package upload failed: {response.status_code} - {response.text}")
            
    
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
    df_env = read_environment(data_url, env_file_id)
    export_path = evaluate_optimization(
        df_env, 
        n_parallel_steps=n_parallel_steps,
        values_per_decision_variable=values_per_decision_variable
    )
    
    load_task = write_optimization_results(data_url, out_file_id, export_path)
    
    archive_path = create_results_report(export_path)
    load_package_task = write_results_report(data_url, archive_path)

    # Set cleanup dependency on both parallel branches
    [load_task, load_package_task] >> cleanup( [archive_path, export_path] )

horizon_optimization()
