"""

environment_data_url: str = "https://collab.psa.es/s/PPBqa4ZSXqbNB6Y"
results_url: str = "https://collab.psa.es/s/WR6MxyJsnZWi9xH"

"""

from typing import Optional
from pathlib import Path
from os import unlink
import datetime
from urllib.parse import urlparse
import tempfile
import pandas as pd
import requests
from io import StringIO
import shutil
import hjson
from airflow.sdk import dag, task
from loguru import logger

from solhycool_optimization import DayResults
from solhycool_visualization.objects import HorizonResultsVisualizer

# Defining functions outside the DAG to demonstrate how they could just be 
# imported from any module of the project and just integrate them in any of the
# tasks of the DAG. 

def get_data(data_url: str) -> pd.DataFrame:
    """
    Function to download data from a public URL and return it as a pandas DataFrame.
    """
    # Read the CSV file from the URL
    df = pd.read_csv(data_url)
    return df

def extract_url_components(url: str) -> tuple[str, str]:
    
    domain = urlparse(url).netloc
    share_id = urlparse(url).path.split('/')[-1]
    
    return domain, share_id

def build_file_url(
    file_id: str, 
    ext: str, 
    url: Optional[str] = None, 
    domain: Optional[str] = None, 
    share_id: Optional[str] = None
) -> str:
    """Builds a URL for accessing a file on a webdav server.
    If a full URL is provided, it extracts the domain and share_id from it.
    If only domain and share_id are provided, it constructs the URL accordingly.
    If share_id is None, it assumes the file is being uploaded to webdav.
    """
    
    assert (url is not None) or (domain is not None), \
        "Either a full URL or both domain and share_id must be provided."
    if url is not None:
        domain, share_id = extract_url_components(url)
        
    if share_id is None: # When uploading to webdav
        return f"https://{domain}/public.php/webdav/{file_id}.{ext}"
    else: # When downloading from webdav
        return f"https://{domain}/public.php/dav/files/{share_id}/{file_id}.{ext}"

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
    fitness_history = original.fitness_history.copy()
    if isinstance(fitness_history.index, pd.DatetimeIndex):
        fitness_history.index = fitness_history.index + pd.Timedelta(days=delta_days)

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

def generate_visualizations(
    day_results: DayResults, 
    output_path: Path,
    plot_config_path = Path("../../data/plot_config_day_horizon.hjson")
) -> None:
    
    # Load plot configuration
    plot_config = hjson.loads(plot_config_path.read_text())
    
    # Create visualizer and generate figures
    visualizer = HorizonResultsVisualizer(
        results_plot_config=plot_config,
        day_results=day_results,
    )
    
    # Generate all visualization figures
    visualizer.generate_all(
        output_path=output_path,
        formats=["png"]
    )

@dag(
    schedule=None,
    # start_date=datetime.datetime(2021, 1, 1, tz="UTC"),
    catchup=False,
    tags=["tests"],
)
def basic_etl(
    data_url: str = "https://collab.psa.es/s/WR6MxyJsnZWi9xH",
    date_str: str = datetime.date.today().strftime("%Y%m%d"),
    env_file_id: str = "environment",
    out_file_id: str = "optimization_results",
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
    def extract(url: str, file_id: str) -> pd.DataFrame:
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
    def transform(df_env: pd.DataFrame) -> str:
        """
        #### Transform task
        In theory this task should call the horizon optimization and then return the results.
        However, for the sake of this example, we will just return precomputed values.
        Initializes DayResults and writes it to a temporary file.
        Returns the path to the temp file.
        """
        date_str = df_env.index[0].strftime("%Y%m%d") 
        
        # Manipulate dates in results to match the date_str
        template_date_str: str = "20220501"
        template_path: Path = Path("./results_eval_at_20250421T1741_psa_partial.gz")
        
        mock_day_results = create_mock_day_results(
            date_str=date_str,
            template_path=template_path,
            template_date_str=template_date_str
        )
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as tmp_file:
            temp_path = Path(tmp_file.name)
            mock_day_results.export(temp_path, reduced=True,)

        # return {"total_order_value": total_order_value}
        return str(temp_path)
    
    @task()
    def load(url: str, file_id: str, export_path: str, date_str: str) -> None:
        """
        #### Load task
        A simple Load task which takes in the result of the Transform task and
        instead of saving it to end user review, just logger.infos it out.
        
        Reads DayResults from the given file and uploads results as CSV.

        """
        domain, share_id = extract_url_components(url)
        
        request_url = build_file_url(            
            domain=domain,
            file_id=file_id,
            ext="csv"
        )
        
        day_results = DayResults.initialize(Path(export_path), date_str=date_str)

        # Create a temporary directory for results
        # Generate visualization and report files
        # This should be done in a separate task
        
        # Upload results csv file
        # Convert DataFrame to CSV in-memory
        csv_buffer = StringIO()
        day_results.df_results.to_csv(csv_buffer, index=False)
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
    def create_visualization_package(export_path: str, date_str: str) -> str:
        """
        #### Visualization task
        Creates visualization figures and packages everything into a compressed file.
        Returns the path to the compressed temp file.
        """
        # Create a temporary directory for all outputs
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Load day results
            day_results = DayResults.initialize(Path(export_path), date_str=date_str)
            
            # Generate visualizations
            generate_visualizations(day_results=day_results, output_path=temp_dir_path)
            
            # Export DayResults object to the same directory
            day_results_path = temp_dir_path / "day_results.h5"
            day_results.export(day_results_path, reduced=True)
            
            # Create compressed archive
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp_archive:
                archive_path = Path(tmp_archive.name)
                
            # Create the tar.gz archive
            shutil.make_archive(
                str(archive_path.with_suffix('')), 
                'gztar', 
                temp_dir
            )
            
            logger.info(f"Created visualization package: {archive_path}")
            return str(archive_path)
    
    @task()
    def load_package(url: str, archive_path: str, date_str: str) -> None:
        """
        #### Load package task
        Uploads the compressed visualization package to the webdav server.
        """
        domain, share_id = extract_url_components(url)
        
        # Create filename with timestamp
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        file_id = f"optimization_results_{current_time}"
        
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
            
        # Clean up archive file
        try:
            unlink(archive_path)
            logger.info(f"Deleted temporary archive: {archive_path}")
        except Exception as e:
            logger.error(f"Warning: failed to delete temp archive {archive_path}: {e}")
    
    @task()
    def cleanup(export_path: str) -> None:
        """
        #### Cleanup task
        Removes the temporary file created by the transform task.
        This runs after both load and visualization tasks are complete.
        """
        try:
            unlink(export_path)
            logger.info(f"Deleted temporary file: {export_path}")
        except Exception as e:
            logger.error(f"Warning: failed to delete temp file {export_path}: {e}")
    
    # DAG tasks execution flow
    df_env = extract(url=data_url, file_id=env_file_id)
    export_path = transform(df_env=df_env)
    
    # Parallel tasks after transform
    load_task = load(url=data_url, file_id=out_file_id, export_path=export_path, date_str=date_str)
    archive_path = create_visualization_package(export_path=export_path, date_str=date_str)
    load_package_task = load_package(url=data_url, archive_path=archive_path, date_str=date_str)
    cleanup_task = cleanup(export_path=export_path)
    
    # Set dependencies
    df_env >> export_path >> [load_task, archive_path >> load_package_task] >> cleanup_task
    load_task >> cleanup(export_path=export_path)
    load_package_task >> cleanup(export_path=export_path)

basic_etl()
