from pathlib import Path
import datetime
import shutil
import tarfile
import tempfile
import numpy as np
import pandas as pd
from loguru import logger
from airflow.sdk import dag, task
import hjson
import copy

from solhycool_deployment.webdav import init_file_system
from solhycool_deployment.visualizations import process_dfs_for_exp_visualization
from solhycool_modeling import EnvironmentVariables
from solhycool_modeling.utils import add_aggretated_variables
from solhycool_optimization.utils.serialization import load_multiple_optimization_results
from solhycool_visualization.operation import plot_results
from phd_visualizations import save_figure
    
@dag(
    schedule=None,
    catchup=False,
    tags=["solhycool"],
)
def horizon_optimization_day_report(
    optimization_url: str = "https://collab.psa.es/s/WR6MxyJsnZWi9xH",
    test_data_url: str = "https://collab.psa.es/s/CcosLNJKw4Dbg9C",
    test_data_fn: str = f"{datetime.datetime.now().strftime("%Y%m%d")}_process_timeseries",
    date_str: str = datetime.datetime.now().strftime("%Y%m%d"),
    plt_config_path: str = "./data/plot_config_day_test.hjson",
    compress_and_delete: bool = True,
    max_n_plot_points: int = 600
):
    """
    ### SOLhycool Day Optimization Report Generator
    
    This DAG generates comprehensive visualization reports comparing experimental data 
    with optimization results for a specific day. It creates interactive plots showing
    the performance of the SOLhycool cooling system optimization algorithm against
    actual experimental measurements.
    
    #### What it does:
    1. Downloads experimental test data from WebDAV for the specified date
    2. Downloads optimization results from multiple evaluation runs for the same date
    3. Processes and aggregates the data to calculate thermal powers, hydraulic ratios, etc.
    4. Creates interactive comparison plots (HTML, PNG, SVG formats)
    5. Optionally compresses results and cleans up the source directory
    
    #### Parameters:
    - **optimization_url**: WebDAV URL containing optimization results directories
    - **test_data_url**: WebDAV URL containing experimental test data CSV files  
    - **test_data_fn**: Experimental data filename (e.g., "20250101_process_timeseries")
    - **date_str**: Target date in YYYYMMDD format (defaults to today)
    - **plt_config_path**: Path to HJSON configuration file defining plot layout and styling
    - **compress_and_delete**: If True, compress results to .tar.gz and delete source directory
    - **max_n_plot_points**: Maximum number of data points to plot (for performance)
    
    #### Output:
    - Interactive HTML plots comparing experimental vs optimization data
    - PNG and SVG static versions of the plots
    - CSV file with merged optimization results
    - Hydraulic distribution analysis across multiple optimization runs
    
    #### Data Sources:
    - Experimental data: `{test_data_fn}.csv` from test_data_url
    - Optimization results: All directories matching `*{date_str}*` from optimization_url
    
    #### Example Usage:
    ```python
    # Generate report for July 28, 2025 with default settings
    horizon_optimization_day_report(date_str="20250728")
    
    # Generate compressed report with custom data sources
    horizon_optimization_day_report(
        optimization_url="https://my-server.com/optimization-data",
        test_data_url="https://my-server.com/experimental-data", 
        date_str="20250715",
        compress_and_delete=True
    ) 
    ```
    
    #### Test DAG:
    ```bash
    airflow dags test horizon_optimization_day_report --conf '{"plt_config_path":"../data/plot_config_day_test.hjson"}'
    ```
    """
            
    @task()
    def build_day_visualization(
        date_str: str,
        optimization_url: str, 
        test_data_url: str, 
        test_data_fn: str,
        plt_config_path: str,
        compressed_results: bool,
        max_n_plot_points: int
    ) -> None:
        """
        #### Build Day Visualization Task
        
        This task is the core of the DAG and performs the following operations:
        
        1. **Data Loading & Preprocessing**:
           - Downloads experimental data CSV from WebDAV
           - Ensures timezone consistency (converts to UTC)
           - Calculates derived variables (thermal powers, hydraulic ratios, etc.)
           
        2. **Optimization Results Processing**:
           - Downloads all optimization result directories for the target date
           - Loads and merges multiple optimization runs with precedence handling
           - Handles both compressed (.tar.gz) and directory formats
           
        3. **Data Alignment & Sampling**:
           - Reduces experimental data to max_n_plot_points for performance
           - Aligns experimental and optimization data indices using forward-fill
           - Creates separate datasets for timeseries and hydraulic distribution plots
           
        4. **Visualization Generation**:
           - Creates comprehensive comparison plots using plotly
           - Generates hydraulic distribution analysis across optimization runs
           - Exports plots in multiple formats (HTML interactive, PNG, SVG)
           
        5. **Output Management**:
           - Saves merged optimization results as CSV
           - Optionally compresses all outputs to .tar.gz
           - Uploads results to WebDAV server
           - Cleans up temporary files and optionally source directories
        
        #### Key Features:
        - **Robust data handling**: Manages timezone conversions, missing data, alignment
        - **Performance optimization**: Limits pdf_exp["HR"].values,
            Tamb=df_exp["Tamb"].values,
            Tv=df_exp["Tv"].values,
            mv=df_exp["mv"].values,
            
            Vavail=df_opt["Vavail"].dropna().iloc[0], # From optimization results (just Vavail0)
            Pe=df_opt["Pe"].values, # From optimization results
            Pw_s1=df_opt["Pw_s1"].values, # From optimization results
            Pw_s2=df_opt["Pw_s2"].values, # From optimization results
        )lot points to prevent browser overload  
        - **Multi-format output**: Interactive HTML + static PNG/SVG for different use cases
        - **Compression support**: Optional .tar.gz packaging for efficient storage
        - **Cleanup automation**: Removes temporary files and optionally source data
        
        #### Data Flow:
        ```
        WebDAV Sources → Local Temp → Data Processing → Plot Generation → WebDAV Output
             ↓              ↓             ↓              ↓              ↓
        [CSV + H5 dirs] → [Pandas] → [Aggregation] → [Plotly] → [HTML/PNG/SVG]
        ```
        
        Args:
            date_str: Target date in YYYYMMDD format
            optimization_url: WebDAV URL for optimization results
            test_data_url: WebDAV URL for experimental data
            test_data_fn: Filename for experimental data
            plt_config_path: Path to plot configuration JSON
            compressed_results: Whether to compress and clean up outputs
            max_n_plot_points: Maximum data points to include in plots
            
        ### Testing the DAG:
        ```bash
        airflow dags test horizon_optimization_day_report --conf '{"plt_config_path":"/workspaces/SOLhycool/data/plot_config_day_test.hjson","date_str":"20250731","test_data_fn":"20250731_process_timeseries"}'
        ```
        """
        
        # Define output directory structure in WebDAV
        output_dir = f"extended/{date_str}/"
        
        # Initialize WebDAV file systems for both data sources
        fs = init_file_system(optimization_url)
        
        # Create a temporary directory for storing downloaded and processed files
        temp_dir = tempfile.TemporaryDirectory(delete=False)
        temp_dir_path = Path(temp_dir.name)

        # Load plot configuration from HJSON file
        # This defines the layout, styling, and which variables to plot
        plt_config = hjson.load(open(plt_config_path, "r"))
        
        # === EXPERIMENTAL DATA LOADING ===
        # Load and process experimental data from the test facility
        logger.info(f"Loading experimental data: {test_data_fn}.csv")
        df_exp = pd.read_csv(
            init_file_system(test_data_url).open(f"{test_data_fn}.csv"),
            index_col="time", parse_dates=True
        )
        
        # Ensure timezone consistency - all data should be in UTC
        if df_exp.index.tz is None:
            df_exp.index = df_exp.index.tz_localize("UTC")
        else:
            df_exp.index = df_exp.index.tz_convert("UTC")
        counts = df_exp.index.value_counts().sort_index()
        if counts.max() > 1:
            logger.warning(f"Found duplicate timestamps in experimental data: {counts[counts > 1]}")
            # If duplicates exist, average them to ensure unique timestamps
            df_exp = df_exp.groupby(df_exp.index).mean()
            logger.info("Averaged duplicate timestamps in experimental data")
        
        # === OPTIMIZATION RESULTS LOADING ===
        # Create temporary directory for downloading optimization results

        # Download all optimization result directories for this date from WebDAV
        logger.info(f"Downloading optimization results from: {output_dir}")
        fs.get(output_dir, f'{str(temp_dir_path)}/', recursive=True)
        logger.info(f"Downloaded to temporary directory: {temp_dir_path}")
        logger.info(f"Contents: {list(temp_dir_path.iterdir())}")

        # Load and merge multiple optimization runs with precedence handling
        # Newer runs override older runs for overlapping time periods
        dfs, eval_times, df_opt = load_multiple_optimization_results(
            temp_dir_path, 
            date_str=date_str,
            look_for="dir",  # Look for directories containing .h5 files
            eval_time_from_parent_fn = True
        )
        opt_index = copy.deepcopy(df_opt.index) # Save original index for later alignment
        
        # Export the merged optimization results for reference
        df_opt.to_csv(temp_dir_path / 'optimization_results.csv', index=True)
        logger.info("Saved merged optimization results to CSV")

        # === DATA PREPROCESSING FOR VISUALIZATION ===
        # df_opt2: optimization data aligned to experimental index
        df_opt = df_opt.reindex(df_exp.index, method="ffill")
        
        # Calculate derived variables (thermal powers, hydraulic ratios, costs, etc.)
        ev = EnvironmentVariables(
            HR=df_exp["HR"].values,
            Tamb=df_exp["Tamb"].values,
            Tv=df_exp["Tv"].values,
            mv=df_exp["mv"].values,
            
            # From optimization results
            Vavail=df_opt["Vavail"].values,
            Pe=df_opt["Pe"].values,
            Pw_s1=df_opt["Pw_s1"].values,
            Pw_s2=df_opt["Pw_s2"].values,
        )
        df_exp = add_aggretated_variables(df_exp, ev=ev, eval_times=eval_times)
 
        # Export the experimental timeseries for reference
        df_exp.to_csv(temp_dir_path / 'experimental_data.csv', index=True)
        logger.info("Saved processed experimental timeseries results to CSV")

        # Reduce experimental data points for better plot performance
        # Use linear interpolation to select evenly spaced points
        if len(df_exp) > max_n_plot_points:
            indices = np.linspace(0, len(df_exp) - 1, max_n_plot_points).astype(int)
            df_exp = df_exp.iloc[indices]
            logger.info(f"Reduced experimental data to {max_n_plot_points} points for plotting")
        
        # Create aligned datasets for different plot types:
        # df_opt: optimization data aligned to experimental index (for timeseries comparison)
        df_opt = df_opt.reindex(df_exp.index, method="ffill")
        # df_exp2: experimental data aligned to optimization index (for hydraulic distribution)
        df_exp2 = df_exp.reindex(opt_index, method="ffill")
        
        # === VISUALIZATION GENERATION ===
        df_exp_plot, df_opt_plot = process_dfs_for_exp_visualization(df_exp, df_opt)
        
        logger.info("Generating comparison plots...")
        fig = plot_results(
            plot_config=plt_config,
            df=df_exp_plot,                    # Main experimental data for timeseries
            df_comp=df_opt_plot,              # Optimization data aligned to experimental timeline
            template="plotly_white",       # Clean white theme
            hydraulic_distribution_dfs=[df_exp2] + dfs,  # All datasets for hydraulic analysis
            hydraulic_distribution_highlight_bar_idx=0,   # Highlight experimental data
            hydraulic_distribution_labels=["<b>Exp</b>"] + [  # Create time labels for each run
                f'{eval_time.split("_")[-1][0:2]}:{eval_time.split("_")[-1][2:]}' 
                for eval_time in eval_times
            ],
            hydraulic_distribution_transplant_xaxis=True  # Share x-axis across subplots
        )
        
        # Save the figure in multiple formats for different use cases
        save_figure(
            fig,
            figure_name="experimental_optimization_results",
            figure_path=temp_dir_path,
            formats=["html", "png", "svg"],  # Interactive + static formats
        )
        logger.info("Generated visualization files")
            
        # === OUTPUT UPLOAD AND CLEANUP ===
        # Re-initialize WebDAV connection to ensure it's still valid
        fs = init_file_system(optimization_url)
        
        if not compressed_results:
            # Upload all files directly to the output directory
            fs.put(f"{str(temp_dir_path)}/", output_dir, recursive=True)
            logger.info(f"Uploaded visualization package to: {output_dir}")
            logger.info(f"Remote files: {fs.ls(output_dir, detail=False)}")
        else:
            # === COMPRESSION AND CLEANUP MODE ===
            # Compress all results into a single .tar.gz file
            tar_path = temp_dir_path / "optimization_results.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                for file in temp_dir_path.iterdir():
                    if file != tar_path:  # Don't include the tar file itself
                        tar.add(file, arcname=file.name)
            logger.info(f"Compressed results to: {tar_path}")

            # Upload the compressed file with a clean filename
            output_path = f'{output_dir[:-1]}.tar.gz'  # Remove trailing slash, add .tar.gz
            fs.put(str(tar_path), output_path)
            logger.info(f"Uploaded compressed results to: {output_path}")

            # Clean up local temporary directory
            shutil.rmtree(temp_dir_path)
            logger.info(f"Cleaned up temporary directory: {temp_dir_path}")
            
            # Remove the original uncompressed files from WebDAV to save space
            try:
                # for file in fs.ls(output_dir, detail=False):
                #     fs.remove(f"{output_dir}{file}")
                fs.rmdir(output_dir, )  # Remove the empty directory
                logger.info(f"Cleaned up remote directory: {output_dir}")
            except Exception as e:
                logger.warning(f"Could not clean up remote directory {output_dir}: {e}")

    # === DAG PIPELINE EXECUTION ===
    # Execute the single task that performs all the work
    # In the future, this could be split into separate tasks:
    # 1. download_data
    # 2. process_data  
    # 3. generate_plots
    # 4. upload_results
    build_day_visualization(
        date_str=date_str,
        optimization_url=optimization_url,
        test_data_url=test_data_url,
        test_data_fn=test_data_fn,
        plt_config_path=plt_config_path,
        compressed_results=compress_and_delete,
        max_n_plot_points=max_n_plot_points
    )
    
horizon_optimization_day_report()
