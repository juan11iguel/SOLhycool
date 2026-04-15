from typing import Literal, Optional
from inspect import signature
from pathlib import Path
from dataclasses import dataclass, asdict
import numpy as np
from loguru import logger
import pandas as pd
import gzip
import shutil
import tempfile
import warnings
import copy
import datetime
from tables.exceptions import NaturalNameWarning
import json
import math
from pydantic import BaseModel, Field
import plotly.graph_objects as go
from solhycool_optimization.utils.serialization import get_queryable_columns
from solhycool_modeling import ModelInputsRange, MatlabOptions, Scalator
from solhycool_modeling.utils import dump_in_span

def _get_matlab_module():
    """Import MATLAB runtime bindings lazily to avoid early native-lib side effects."""
    import combined_cooler  # noqa: F401  # Required before importing matlab.
    import matlab
    return matlab

warnings.filterwarnings("ignore", category=NaturalNameWarning)

# TODO: eval_at should be exported within the metadata in the hdf file, so it could be serialized an deserialized

@dataclass
class RealDecVarsBoxBounds:
    """ Real decision variables box bounds, as in: (lower bound, upper bound)"""
    qc: tuple[float, float]
    Rp: tuple[float, float]
    Rs: tuple[float, float]
    wdc: tuple[float, float]
    wwct: tuple[float, float]
    
    @classmethod
    def from_model_inputs_range(cls, model_inputs_range: ModelInputsRange = ModelInputsRange()) -> "RealDecVarsBoxBounds":
        """ Create instance from ModelInputsRange instance """
        return cls(**{name: value for name, value in asdict(model_inputs_range).items() if name in signature(cls).parameters})
    
@dataclass
class DecisionVariables:
    qc: float | np.ndarray[float]
    Rp: float | np.ndarray[float]
    Rs: float | np.ndarray[float]
    wdc: float | np.ndarray[float]
    wwct: float | np.ndarray[float] = None
    
    def dump_at_index(self, idx: int, return_dict: bool = False, return_format: Literal["number", "matlab"] = "number") -> "DecisionVariables":
        """
        Dump instance at a given index.

        Parameters:
        - idx: Integer index to extract.

        Returns:
        - A dictionary.
        """
        dump =  {name: np.asarray(value)[idx] for name, value in asdict(self).items() if value is not None}
        if return_format == "matlab":
            matlab = _get_matlab_module()
            dump = {k: matlab.double([v]) for k, v in dump.items()}

        return dump if return_dict else DecisionVariables(**dump)

    def dump_in_span(self, span: tuple[int, int]) -> 'DecisionVariables':
        """ Dump environment variables within a given span """

        vars_dict = dump_in_span(vars_dict=asdict(self), span=span, return_format="values")
        
        return DecisionVariables(**vars_dict)

    def to_matlab(self) -> "DecisionVariables":
        """ Convert all attributes to matlab.double """
        matlab = _get_matlab_module()
        return DecisionVariables(**{k: matlab.double(v) for k, v in asdict(self).items() if v is not None})

@dataclass
class ValuesDecisionVariables:
    qc: int | np.ndarray[float] = 10
    Rp: int | np.ndarray[float] = 10
    Rs: int | np.ndarray[float] = 10
    wdc: int | np.ndarray[float] = 10
    
    @classmethod
    def initialize(cls, values_per_dv: int):
        """ Initialize instance with the same number values per decision variable """
        
        fld_names = list(cls.__dataclass_fields__.keys())
        logger.info(f"Initializing {cls.__name__} with {values_per_dv} values per decision variable. A total of {values_per_dv**len(fld_names)} combinations will be generated.")
        
        return cls(**{name: values_per_dv for name in fld_names})
    
    def generate_arrays(self, inputs_range: ModelInputsRange = ModelInputsRange()) -> "ValuesDecisionVariables":        
        return ValuesDecisionVariables(**{
            name: np.linspace(getattr(inputs_range, name)[0], getattr(inputs_range, name)[1], n_values) 
            for name, n_values in asdict(self).items()
        })
        
    def to_matlab(self) -> "ValuesDecisionVariables":
        """ Convert all attributes to matlab.double """
        matlab = _get_matlab_module()
        return ValuesDecisionVariables(**{k: matlab.double(v.tolist()) for k, v in asdict(self).items() if v is not None})
        
    def to_matlab_dict(self, ) -> dict:
        return asdict(self.to_matlab())
        
@dataclass
class StaticResults:
    index: pd.DatetimeIndex # Index of the results
    df_paretos: list[pd.DataFrame] # List of dataframes with the pareto fronts for each step
    consumption_arrays: list[np.ndarray[float]] # Array with the consumption values for the candidate operation points
    pareto_idxs: list[int] # Path of indices of the pareto fronts from the dataset of candidate operation points
    
    @classmethod
    def initialize(cls, input_path: Path):
        """ Initialize the class from a possibly gzipped file. """
        
        if input_path.suffix == ".gz":
            # Uncompress the gzip file into a temporary .h5 file
            with gzip.open(input_path, 'rb') as f_in:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    temp_path = Path(f_out.name)
        else:
            temp_path = input_path

        with pd.HDFStore(temp_path, mode='r') as store:
            # Try new flattened structure first, fallback to old structure
            df_paretos = []
            consumption_arrays = []
            
            if "/pareto" in store:
                # New flattened structure
                pareto_df = store["/pareto"]
                pareto_by_timestamp = {dt: group.drop(columns=['timestamp']) 
                                     for dt, group in pareto_df.groupby('timestamp')}
                index = pd.DatetimeIndex(sorted(pareto_by_timestamp.keys()))
                df_paretos = [pareto_by_timestamp[dt] for dt in index]
            else:
                # Old structure - fallback
                for key in store.keys():
                    if key.startswith("/pareto/"):
                        df_paretos.append(store[key])
                index = pd.DatetimeIndex([pd.to_datetime(key.split("/")[-1], format="%Y%m%dT%H%M") 
                                        for key in store.keys() if key.startswith("/pareto/")])
            
            if "/consumption" in store:
                # New flattened structure
                consumption_df = store["/consumption"]
                consumption_by_timestamp = {dt: group.drop(columns=['timestamp'])[['Cw', 'Ce']].to_numpy() 
                                          for dt, group in consumption_df.groupby('timestamp')}
                consumption_arrays = [consumption_by_timestamp.get(dt) for dt in index]
            else:
                # Old structure - fallback
                for key in store.keys():
                    if key.startswith("/consumption/"):
                        consumption_arrays.append(store[key].to_numpy())

            pareto_idxs = [list(range(len(df))) for df in df_paretos]

        if input_path.suffix == ".gz":
            temp_path.unlink()

        return cls(index=index, df_paretos=df_paretos, consumption_arrays=consumption_arrays, pareto_idxs=pareto_idxs)
    
    def export(self, output_path: Path, ) -> None:
        """ Export results to a file. """
        
        if not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with pd.HDFStore(output_path, mode='a', complevel=9, complib='zlib') as store:
            # Flatten all pareto fronts into a single table with timestamp column
            all_paretos = []
            for dt, df_pareto in zip(self.index, self.df_paretos):
                df_with_timestamp = df_pareto.copy()
                df_with_timestamp['timestamp'] = dt
                all_paretos.append(df_with_timestamp)
            
            if all_paretos:
                flattened_paretos = pd.concat(all_paretos, ignore_index=True)
                store.put("/pareto", flattened_paretos, format="table", 
                         data_columns=get_queryable_columns(flattened_paretos))

            # Flatten all consumption arrays into a single table with timestamp column
            all_consumption = []
            for dt, consumption_array in zip(self.index, self.consumption_arrays):
                if consumption_array is not None:
                    df_consumption = pd.DataFrame(consumption_array, columns=["Cw", "Ce"])
                    df_consumption['timestamp'] = dt
                    all_consumption.append(df_consumption)
            
            if all_consumption:
                flattened_consumption = pd.concat(all_consumption, ignore_index=True)
                store.put("/consumption", flattened_consumption, format="table", data_columns=True)

            # Save indices of points in the pareto front as flattened table
            pareto_idx_data = []
            for dt, pareto_idx_list in zip(self.index, self.pareto_idxs):
                for idx, pareto_idx in enumerate(pareto_idx_list):
                    pareto_idx_data.append({'timestamp': dt, 'step_idx': idx, 'pareto_idx': pareto_idx})
            
            if pareto_idx_data:
                df_pareto_idxs = pd.DataFrame(pareto_idx_data)
                store.put("/paths/pareto_idxs", df_pareto_idxs, format="table", data_columns=True)

        logger.info(f"StaticResults saved to {output_path}")
        
    def visualize(self, ) -> go.Figure:
        
        from solhycool_visualization.optimization import plot_pareto_front

        return plot_pareto_front(
            ops_list=self.df_paretos,
            full_legend=True,
            showlegend=True,
            date_fmt='%Y%m%d',
            objective_keys=('Cw', 'Ce'),
            yaxis_label="<b>Electricity consumption</b> (KW<sub>e</sub>)",
            xaxis_label="<b>Water consumption</b> (l/h)",
            mode="overlap",
            simple_colors=True,
            template="plotly_white",
            title_text="<b>Pareto fronts</b> <span style='font-size:16px'> in different representative scenarios</span>",
            title_y=0.95,
            legend=dict(
                yanchor="top",
                xanchor="left",
                x=0.01,
                y=1.52  ,
            ),
            margin=dict(t=170, b=5, l=20, r=5),
            width=600,
            # xaxis_range=[-5, 310],
            xaxis_domain=[0.12, 1],
        )
        
@dataclass
class HorizonResults:
    """
    Container for optimization results from horizon-based optimization problems.
    
    The class is designed to handle two main optimization subproblems:
    1. Pareto front generation: Finding non-dominated solutions for each time step
    2. Path selection: Selecting optimal points from Pareto fronts to form a path
    
    Data Structure:
        The class follows a time-indexed structure where each timestamp in the index
        corresponds to entries in the list-based attributes (df_paretos, 
        selected_pareto_idxs, etc.).
    
    Attributes:
        index: DatetimeIndex containing timestamps for the optimization horizon
        df_results: Final optimization results with selected solutions for each timestamp
        df_paretos: Pareto front DataFrames for each time step (one per timestamp)
        selected_pareto_idxs: Indices of points selected from each Pareto front
        date_str: Human-readable identifier for the date range (auto-generated if None)
        eval_at: Timestamp when the optimization was evaluated (auto-generated if None)
        fitness_history: Optimization fitness evolution (optional, may be None in reduced exports)
        consumption_arrays: Raw consumption data for all feasible points (optional)
        pareto_idxs: Indices of non-dominated points in the full solution space (optional)
    
    Usage Patterns:
        - Create instances directly with optimization results
        - Load from saved files using HorizonResults.initialize()
        - Filter temporal subsets using HorizonResults.select()
        - Export for storage using the export() method
    
    File Format:
        When exported, data is stored in HDF5 format with a flattened structure
        that preserves temporal relationships through timestamp columns. This
        design enables querying and partial loading of large datasets.
    
    Examples:
        # Create from optimization results
        results = HorizonResults(
            index=pd.date_range('2023-01-01', periods=24, freq='H'),
            df_results=optimization_results_df,
            df_paretos=pareto_fronts_list,
            selected_pareto_idxs=selected_indices
        )
        
        # Load from file
        results = HorizonResults.initialize(Path("optimization_results.h5"))
        
        # Filter by date
        single_day = results.select("20230101")
        date_range = results.select(("20230101", "20230103"))
        
        # Export results
        results.export(Path("results.gz"), reduced=True)
    """
    index: pd.DatetimeIndex # Index of the results
    df_results: pd.DataFrame # DataFrame with the final results (result of solving both subproblems)
    df_paretos: list[pd.DataFrame] # List of dataframes with the pareto fronts for each step (result of pareto build subproblem)
    selected_pareto_idxs: list[int] # Selected points indices for each pareto front (result of path selection subproblem)
    
    # Metadata
    date_str: str = None # Identifier for the results date range, e.g. "20231001_20231007"
    eval_at: Optional[str] = None # Evaluation time, e.g. "20231001T1200"
    
    # Not present if reduced export
    fitness_history: Optional[pd.Series] = None # Series with the fitness history of the path selection subproblem
    consumption_arrays: Optional[list[np.ndarray[float]]] = None # Array with the consumption values for all feasible operation points
    pareto_idxs: Optional[list[int]] = None # Indices of non-dominated operation points from the dataset of all feasible operation points
    
    def __post_init__(self):
        if self.date_str is None:
            self.date_str = f'{self.index[0].strftime("%Y%m%dT%H%M")}-{self.index[-1].strftime("%Y%m%dT%H%M")}'

        if self.eval_at is None:
            self.eval_at = datetime.datetime.now().strftime("%Y%m%dT%H%M")
            
        self.df_results = self.df_results.sort_index() # Ensure results are sorted by index, might not be the case if concatenated from multiple runs
            
    @classmethod
    def initialize(cls, input_path: Path, date_str: Optional[str] = None, log: bool = True) -> "HorizonResults":
        """
        Initialize a HorizonResults instance from a saved HDF5 file.
        
        This method loads optimization results from HDF5 files that were created using the
        export method. It supports both compressed (.gz) and uncompressed (.h5) files,
        and can load either the entire dataset or filter by a specific date.
        
        The method expects data to be stored in a flattened structure with the following keys:
        - '/results': Main optimization results DataFrame
        - '/paretos': Flattened pareto fronts with timestamp column
        - 'selected_pareto_idxs': Selected pareto indices with timestamp column
        - '/extended/pareto_consumption_arrays': Consumption arrays with timestamp column
        - '/extended/pareto_idxs': Pareto indices with timestamp and step_idx columns
        - '/extended/path_selection_fitness_history': Fitness history with timestamp column
        
        Args:
            input_path: Path to the HDF5 file (.h5 or .gz). The file should contain
                       optimization results exported using the export method.
            date_str: Optional date string in YYYYMMDD format (e.g., "20230101").
                     If provided, only data for that specific date will be loaded.
                     If None, the entire dataset will be loaded.
            log: Whether to log information about the loading process. Defaults to True.
        
        Returns:
            HorizonResults instance with the loaded data. The instance will contain:
            - index: DatetimeIndex for the loaded time range
            - df_results: DataFrame with optimization results
            - df_paretos: List of pareto front DataFrames for each timestamp
            - selected_pareto_idxs: List of selected pareto indices
            - consumption_arrays: List of consumption arrays (if available)
            - pareto_idxs: List of pareto indices (if available)
            - fitness_history: Optimization fitness history (if available)
            - date_str: String identifier for the date range
            - eval_at: Evaluation timestamp from metadata (if available)
        
        Raises:
            TypeError: If the '/results' index is not a DatetimeIndex
            ValueError: If date_str is provided but no data exists for that date
            FileNotFoundError: If the input_path does not exist
            
        Examples:
            # Load entire dataset
            results = HorizonResults.initialize(Path("optimization_results.h5"))
            
            # Load specific date
            results = HorizonResults.initialize(
                Path("optimization_results.h5"), 
                date_str="20230101"
            )
            
            # Load compressed file without logging
            results = HorizonResults.initialize(
                Path("optimization_results.gz"), 
                log=False
            )
        """
        input_path = Path(input_path)
        
        temp_path = input_path
        if input_path.suffix == ".gz":
            with gzip.open(input_path, 'rb') as f_in, tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as f_out:
                shutil.copyfileobj(f_in, f_out)
                temp_path = Path(f_out.name)

        with pd.HDFStore(temp_path, mode='r') as store:
            df_results_all = store["/results"].sort_index()
            if not isinstance(df_results_all.index, pd.DatetimeIndex):
                raise TypeError(f"The index of '/results' is not a DatetimeIndex, got {type(df_results_all.index)}")

            # Read metadata attributes if available
            metadata = {}
            try:
                metadata = store.get_storer('/results').attrs.metadata
            except (AttributeError, KeyError):
                metadata = {}

            if date_str is None:
                # Use the entire index, no date filtering
                filtered_index = df_results_all.index
                df_results = df_results_all
                date_str = f'{filtered_index[0].strftime("%Y%m%dT%H%M")}-{filtered_index[-1].strftime("%Y%m%dT%H%M")}'
            else:
                # Filter by specific date
                target_date = pd.to_datetime(date_str, format="%Y%m%d").date()
                filtered_index = df_results_all.index[df_results_all.index.date == target_date]
                if filtered_index.empty:
                    available_dates = sorted(set(idx.date() for idx in df_results_all.index))
                    available_dates_str = sorted(d.isoformat() for d in available_dates)
                    raise ValueError(f"No results for date {date_str} in {input_path.stem}. "
                                    f"Available: {available_dates_str}")
                df_results = df_results_all.loc[filtered_index]

            # Load pareto fronts from flattened structure
            df_paretos = []
            if "/paretos" in store:
                pareto_df = store["/paretos"]
                if date_str and len(date_str) == 8:  # date filtering
                    target_date = pd.to_datetime(date_str, format="%Y%m%d").date()
                    pareto_df = pareto_df[pareto_df['timestamp'].dt.date == target_date]
                    
                pareto_by_timestamp = {dt: group.drop(columns=['timestamp']) 
                                     for dt, group in pareto_df.groupby('timestamp')}
                df_paretos = [pareto_by_timestamp.get(dt) for dt in filtered_index]
            else:
                df_paretos = [None] * len(filtered_index)

            # Load consumption arrays from flattened structure  
            consumption_arrays = []
            if "/extended/pareto_consumption_arrays" in store:
                consumption_df = store["/extended/pareto_consumption_arrays"]
                if date_str and len(date_str) == 8:  # date filtering
                    target_date = pd.to_datetime(date_str, format="%Y%m%d").date()
                    consumption_df = consumption_df[consumption_df['timestamp'].dt.date == target_date]
                    
                consumption_by_timestamp = {dt: group.drop(columns=['timestamp'])[['Cw', 'Ce']].to_numpy() 
                                          for dt, group in consumption_df.groupby('timestamp')}
                consumption_arrays = [consumption_by_timestamp.get(dt) for dt in filtered_index]
            else:
                consumption_arrays = [None] * len(filtered_index)

            # Load selected pareto indices from flattened structure
            selected_pareto_idxs = []
            if "selected_pareto_idxs" in store:
                selected_df = store["selected_pareto_idxs"]
                if date_str and len(date_str) == 8:  # date filtering
                    target_date = pd.to_datetime(date_str, format="%Y%m%d").date()
                    selected_df = selected_df[selected_df['timestamp'].dt.date == target_date]
                    
                selected_by_timestamp = {dt: group['selected_pareto_idx'].iloc[0] 
                                       for dt, group in selected_df.groupby('timestamp')}
                selected_pareto_idxs = [selected_by_timestamp.get(dt, 0) for dt in filtered_index]
            else:
                selected_pareto_idxs = [0] * len(filtered_index)

            # Load fitness history
            fitness_history = None
            if "/extended/path_selection_fitness_history" in store:
                fitness_df = store["/extended/path_selection_fitness_history"]
                if not fitness_df.empty:
                    # If there are multiple entries, take the first one (they should be the same for a single optimization run)
                    fitness_history = fitness_df.drop(columns=['timestamp']).iloc[:, 0] if 'timestamp' in fitness_df.columns else fitness_df.iloc[:, 0]

            # Load pareto indices from flattened structure
            pareto_idxs = None
            if "/extended/pareto_idxs" in store:
                pareto_idx_df = store["/extended/pareto_idxs"]
                if date_str and len(date_str) == 8:  # date filtering
                    target_date = pd.to_datetime(date_str, format="%Y%m%d").date()
                    pareto_idx_df = pareto_idx_df[pareto_idx_df['timestamp'].dt.date == target_date]
                    
                pareto_idxs_by_timestamp = {}
                for dt, group in pareto_idx_df.groupby('timestamp'):
                    sorted_group = group.sort_values('step_idx')
                    pareto_idxs_by_timestamp[dt] = sorted_group['pareto_idx'].tolist()
                pareto_idxs = [pareto_idxs_by_timestamp.get(dt, []) for dt in filtered_index]

            hor_results = cls(
                index=filtered_index,
                df_results=df_results,
                df_paretos=df_paretos,
                consumption_arrays=consumption_arrays,
                fitness_history=fitness_history,
                selected_pareto_idxs=selected_pareto_idxs,
                pareto_idxs=pareto_idxs,
                date_str=date_str,
                eval_at=metadata.get("eval_at")
            )
            
            if log:
                logger.info(f"HorizonResults loaded for {date_str} from {input_path}")

        if input_path.suffix == ".gz":
            temp_path.unlink()

        return hor_results
        
    def export(self, output_path: Path, reduced: bool = False) -> None:
        """
        Export HorizonResults to an HDF5 file with optional compression.
        
        This method saves the optimization results to an HDF5 file using a flattened
        structure that can be efficiently loaded by the initialize method. The data
        is organized in hierarchical groups and can optionally be compressed using gzip.
        
        The exported file contains the following structure:
        - '/results': Main optimization results DataFrame (always included)
        - '/paretos': Flattened pareto fronts with timestamp column
        - 'selected_pareto_idxs': Selected pareto indices with timestamp column
        - '/extended/pareto_consumption_arrays': Consumption arrays with timestamp column
        - '/extended/pareto_idxs': Pareto indices with timestamp and step_idx columns  
        - '/extended/path_selection_fitness_history': Fitness history with timestamp column
        - Metadata attributes: eval_at, exported_at stored in '/results' attributes
        
        Args:
            output_path: Path where the file will be saved. The extension determines
                        the output format:
                        - '.h5': Uncompressed HDF5 file
                        - '.gz': Compressed HDF5 file (recommended for storage)
            reduced: If True, excludes extended data (fitness_history, consumption_arrays,
                    pareto_idxs) to create a smaller file. Defaults to False.        
        Returns:
            None
            
        Raises:
            PermissionError: If unable to write to the output path
            OSError: If there are issues with file operations
            
        Notes:
            - The method creates a deep copy of the instance to avoid modifying the original
            - Timestamps are preserved exactly as stored in the original index
            - Metadata includes evaluation time and export timestamp for traceability
        
        Examples:
            # Export full results to compressed file
            results.export(Path("optimization_results.gz"))
            
            # Export reduced results to uncompressed file
            results.export(Path("optimization_results.h5"), reduced=True)
            
        """
        
        output_path = Path(output_path)
        self = copy.deepcopy(self) # To avoid modifying the original object
        
        if not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if reduced:
            self.fitness_history = None
            self.consumption_arrays = [None] * len(self.index)
            self.pareto_idxs = None 
        
        with pd.HDFStore(output_path.with_suffix(".h5"), mode='a', complevel=9, complib='zlib') as store:
            
            # Append df_results (path of selected solutions)
            store.append(
                "/results",
                self.df_results,
                format="table",
                data_columns=get_queryable_columns(self.df_results),
                complib="zlib",
                complevel=9
            )

            # Flatten all pareto fronts into a single table with timestamp column
            if any(df is not None for df in self.df_paretos): # If there is at least one pareto front
                all_paretos = []
                for dt, df_pareto in zip(self.index, self.df_paretos):
                    if df_pareto is not None:
                        df_with_timestamp = df_pareto.copy()
                        df_with_timestamp['timestamp'] = dt
                        all_paretos.append(df_with_timestamp)
                
                if all_paretos:
                    flattened_paretos = pd.concat(all_paretos, ignore_index=True)
                    store.append(
                        "/paretos",
                        flattened_paretos,
                        format="table",
                        data_columns=get_queryable_columns(flattened_paretos)
                    )
            
            # Save indices of points selected from the pareto front for each step - flattened
            if self.selected_pareto_idxs:
                selected_idx_data = []
                for dt, selected_idx in zip(self.index, self.selected_pareto_idxs):
                    selected_idx_data.append({'timestamp': dt, 'selected_pareto_idx': selected_idx})
                
                df_selected_idxs = pd.DataFrame(selected_idx_data)
                store.put("selected_pareto_idxs", df_selected_idxs, format="table", data_columns=True)

            # -- extended data --
            # Flatten all consumption arrays into a single table with timestamp column
            if any(arr is not None for arr in self.consumption_arrays):
                all_consumption = []
                for dt, consumption_array in zip(self.index, self.consumption_arrays):
                    if consumption_array is not None:
                        df_consumption = pd.DataFrame(consumption_array, columns=["Cw", "Ce"])
                        df_consumption['timestamp'] = dt
                        all_consumption.append(df_consumption)
                
                if all_consumption:
                    flattened_consumption = pd.concat(all_consumption, ignore_index=True)
                    store.append(
                        "/extended/pareto_consumption_arrays",
                        flattened_consumption,
                        format="table",
                        data_columns=True
                    )
            
            if self.pareto_idxs is not None:
                # Flatten pareto indices into a single table with timestamp column
                pareto_idx_data = []
                for dt, pareto_idx_list in zip(self.index, self.pareto_idxs):
                    if pareto_idx_list is not None:
                        idx_list = pareto_idx_list.tolist() if not isinstance(pareto_idx_list, list) else pareto_idx_list
                        for idx, pareto_idx in enumerate(idx_list):
                            pareto_idx_data.append({'timestamp': dt, 'step_idx': idx, 'pareto_idx': pareto_idx})
                
                if pareto_idx_data:
                    df_pareto_idxs = pd.DataFrame(pareto_idx_data)
                    store.put("/extended/pareto_idxs", df_pareto_idxs, format="table", 
                            data_columns=True, complib="zlib", complevel=9)

            # Save path selection optimization fitness history
            if self.fitness_history is not None:
                df = self.fitness_history.copy()
                df['timestamp'] = self.date_str  # Use date_str as identifier
                store.append(
                    "/extended/path_selection_fitness_history",
                    df,
                    format="table",
                    data_columns=df.columns  # makes all columns queryable, including timestamp
                )
                
            # -- metadata --
            metadata = {
                "eval_at": self.eval_at,
                "exported_at": datetime.datetime.now().strftime("%Y%m%dT%H%M%S"),
            }
            # Embed metadata in the HDF5 file attributes so that it can be retrived by the initialize method
            store.get_storer('/results').attrs.metadata = metadata
        
        # Compress the .h5 file using gzip
        if output_path.suffix == ".gz":
            with open(output_path.with_suffix(".h5"), 'rb') as f_in, gzip.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            output_path.with_suffix(".h5").unlink()  # Remove uncompressed .h5 file

        logger.info(f"Results for {self.date_str} saved to {output_path}")
        
    def select(self, date_rng: str | tuple[str, str]) -> "HorizonResults":
        """
        Filter HorizonResults to only include data spanning the specified date or date range.
        
        Args:
            date_rng: Either a single date string (e.g., "20010101") or a tuple of 
                     (start_date, end_date) strings (e.g., ("20010101", "20010103"))
        
        Returns:
            A new HorizonResults instance with filtered data
        
        Examples:
            # Select single day
            filtered_results = results.select("20010101")
            
            # Select date range
            filtered_results = results.select(("20010101", "20010103"))
        """
        # Parse date range
        if isinstance(date_rng, str):
            # Single date
            start_date = pd.to_datetime(date_rng, format="%Y%m%d").date()
            end_date = start_date
        elif isinstance(date_rng, tuple) and len(date_rng) == 2:
            # Date range
            start_date = pd.to_datetime(date_rng[0], format="%Y%m%d").date()
            end_date = pd.to_datetime(date_rng[1], format="%Y%m%d").date()
        else:
            raise ValueError("date_rng must be either a string (single date) or tuple of two strings (date range)")
        
        # Filter index by date range
        mask = (self.index.date >= start_date) & (self.index.date <= end_date)
        filtered_index = self.index[mask]
        
        if filtered_index.empty:
            available_dates = sorted(set(self.index.date))
            available_dates_str = [d.strftime("%Y%m%d") for d in available_dates]
            raise ValueError(f"No data found for date range {date_rng}. Available dates: {available_dates_str}")
        
        # Filter all data arrays based on the mask
        filtered_df_results = self.df_results.loc[filtered_index]
        
        # Filter list-based attributes by the same indices
        filtered_df_paretos = [self.df_paretos[i] for i in range(len(self.df_paretos)) if mask[i]]
        filtered_selected_pareto_idxs = [self.selected_pareto_idxs[i] for i in range(len(self.selected_pareto_idxs)) if mask[i]]
        
        # Handle optional list attributes
        filtered_consumption_arrays = None
        if self.consumption_arrays is not None:
            filtered_consumption_arrays = [self.consumption_arrays[i] for i in range(len(self.consumption_arrays)) if mask[i]]
        
        filtered_pareto_idxs = None
        if self.pareto_idxs is not None:
            filtered_pareto_idxs = [self.pareto_idxs[i] for i in range(len(self.pareto_idxs)) if mask[i]]
        
        # Generate new date_str for the filtered range
        if start_date == end_date:
            new_date_str = start_date.strftime("%Y%m%d")
        else:
            new_date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        
        # Create new HorizonResults instance with filtered data
        return HorizonResults(
            index=filtered_index,
            df_results=filtered_df_results,
            df_paretos=filtered_df_paretos,
            selected_pareto_idxs=filtered_selected_pareto_idxs,
            date_str=new_date_str,
            eval_at=self.eval_at,
            fitness_history=self.fitness_history,  # Keep the same fitness history (it's optimization-wide)
            consumption_arrays=filtered_consumption_arrays,
            pareto_idxs=filtered_pareto_idxs
        )
        
    def scale(self, scalator: Scalator = Scalator()) -> "HorizonResults":
        """
        Scale all DataFrame attributes using the provided Scalator instance.
        Args:
            scalator: Scalator instance with fit parameters. Defaults to a new Scalator.
        Returns:
            A new HorizonResults instance with scaled DataFrames.
        """
        
        return HorizonResults(
            index=self.index,
            df_results=scalator.scale_dataframe(self.df_results),
            df_paretos=[scalator.scale_dataframe(df) if df is not None else None for df in self.df_paretos],
            selected_pareto_idxs=self.selected_pareto_idxs,
            date_str=self.date_str,
            eval_at=self.eval_at,
            fitness_history=self.fitness_history,
            consumption_arrays=self.consumption_arrays,
            pareto_idxs=self.pareto_idxs
        )
        
        
        
# @dataclass
# class MultipleHorizonResults:
#     """Class for handling multiple day results."""
#     df_results: pd.DataFrame # DataFrame with the results of the path composed by the selected pareto fronts joined
#     date_strs: list[str] # List of date strings for the days
#     index: list[pd.DatetimeIndex] # Index of the results
#     df_paretos: list[list[pd.DataFrame]] # List of dataframes with the pareto fronts for each step
#     fitness_history: list[pd.Series] # Series with the fitness history of the path selection optimization
#     selected_pareto_idxs: list[list[int]] # Path of indices of the selected pareto fronts
#     df_results_individual: list[pd.DataFrame] # DataFrame with the results of the path composed by the selected pareto fronts for each day
#     consumption_arrays: list[list[np.ndarray[float]]] = None # Array with the consumption values for the candidate operation points
#     pareto_idxs: list[list[int]] = None # Path of indices of the pareto fronts from the dataset of candidate operation points

#     @classmethod
#     def initialize_from_file(cls, results_path: Path, date_strs: list[str]) -> "MultipleHorizonResults":
#         """Initialize the class from a possibly gzipped file."""
        
#         if results_path.suffix == ".gz":
#             # Uncompress the gzip file into a temporary .h5 file
#             with gzip.open(results_path, 'rb') as f_in:
#                 with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as f_out:
#                     shutil.copyfileobj(f_in, f_out)
#                     temp_path = Path(f_out.name)
#         else:
#             temp_path = results_path

#         try:
#             day_results_list = [
#                 HorizonResults.initialize(temp_path, date_str=date_str, log=False) for date_str in date_strs
#             ]
#         finally:
#             if results_path.suffix == ".gz":
#                 temp_path.unlink()  # Clean up temp .h5 file

#         return cls.initialize_from_day_results(day_results_list)

#     @classmethod
#     def initialize_from_day_results(cls, day_results_list: list[HorizonResults]) -> "MultipleHorizonResults":
#         """Initialize the class from a list of HorizonResults."""
        
#         multiple_day_results = cls(
#             date_strs=[day_results.date_str for day_results in day_results_list],
#             index=[day_results.index for day_results in day_results_list],
#             df_paretos=[day_results.df_paretos for day_results in day_results_list],
#             consumption_arrays=[day_results.consumption_arrays for day_results in day_results_list],
#             fitness_history=[day_results.fitness_history for day_results in day_results_list],
#             pareto_idxs=[day_results.pareto_idxs for day_results in day_results_list],
#             selected_pareto_idxs=[day_results.selected_pareto_idxs for day_results in day_results_list],
#             df_results=pd.concat([day_result.df_results for day_result in day_results_list], axis=0).sort_index(),
#             df_results_individual=[day_result.df_results for day_result in day_results_list]
#         )
        
#         logger.info(f"MultipleHorizonResults initialized with {len(day_results_list)} days ({multiple_day_results.date_strs[0]}-{multiple_day_results.date_strs[-1]})")
        
#         return multiple_day_results
            
#     def export(self, output_path: Path) -> None:
#         """ Export results to a gzip-compressed file. """

#         temp_h5_path = output_path.with_suffix(".h5")

#         for day_idx in range(len(self.df_results_individual)):
#             HorizonResults(
#                 index=self.index[day_idx],
#                 df_paretos=self.df_paretos[day_idx],
#                 fitness_history=self.fitness_history[day_idx],
#                 selected_pareto_idxs=self.selected_pareto_idxs[day_idx],
#                 df_results=self.df_results_individual[day_idx],
#                 consumption_arrays=self.consumption_arrays[day_idx] if self.consumption_arrays is not None else None,
#                 pareto_idxs=self.pareto_idxs[day_idx] if self.pareto_idxs is not None else None,
#             ).export(temp_h5_path)

#         # Compress the .h5 file using gzip
#         with open(temp_h5_path, 'rb') as f_in, gzip.open(output_path.with_suffix(".h5.gz"), 'wb') as f_out:
#             shutil.copyfileobj(f_in, f_out)

#         temp_h5_path.unlink()  # Remove uncompressed .h5 file
        
#         logger.info(f"Results for {self.date_strs[0]}-{self.date_strs[-1]} compressed and saved to {output_path}")


# def import_simulation_results(results_path: Path) -> pd.DataFrame:
#     """ Import simulation results from a gzip-compressed file. """
    
#     if results_path.suffix == ".gz":
#         # Uncompress the gzip file into a temporary .h5 file
#         with gzip.open(results_path, 'rb') as f_in:
#             with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as f_out:
#                 shutil.copyfileobj(f_in, f_out)
#                 temp_path = Path(f_out.name)
#     else:
#         temp_path = results_path

#     try:
#         df_results = pd.read_hdf(temp_path, key="/results")
#     finally:
#         if results_path.suffix == ".gz":
#             temp_path.unlink()  # Clean up temp .h5 file

#     return df_results


class AlgoParamsHorizon(BaseModel):
    algo_id: str = Field(default="sga", description="ID of the optimization algorithm")
    max_n_obj_fun_evals: int = Field(default=20_000, description="Max number of objective function evaluations")
    max_n_logs: int = Field(default=300, description="Maximum number of log entries")
    pop_size: int = Field(default=80, description="Population size for population-based algorithms")

    params_dict: Optional[dict] = Field(default=None, description="Derived algorithm-specific parameters")
    log_verbosity: Optional[int] = Field(default=None, description="Logging verbosity level")
    gen: Optional[int] = Field(default=None, description="Number of generations")

    def model_post_init(self, __context) -> None:
        # Calculate gen and params_dict based on algo_id
        if self.algo_id in ["gaco", "sga", "pso_gen"]:
            self.gen = self.max_n_obj_fun_evals // self.pop_size
            self.params_dict = {"gen": self.gen}

        elif self.algo_id == "simulated_annealing":
            self.gen = self.max_n_obj_fun_evals // self.pop_size
            self.params_dict = {
                "bin_size": self.pop_size,
                "n_T_adj": self.gen
            }

        else:
            self.pop_size = 1
            self.gen = self.max_n_obj_fun_evals
            self.params_dict = {"gen": self.max_n_obj_fun_evals // self.pop_size}

        # Calculate default log_verbosity if not given
        if self.log_verbosity is None:
            self.log_verbosity = math.ceil(self.gen / self.max_n_logs)


class EvaluationConfig(BaseModel):
    id: str = Field(..., description="Unique identifier for the configuration", example="pilot_plant")
    description: str
    model_inputs_range: ModelInputsRange
    matlab_options: MatlabOptions
    algo_params: AlgoParamsHorizon
    vals_dec_vars: ValuesDecisionVariables
    load_factor: float = Field(
        1.0,
        description="Factor to reduce thermal load power by (1.0 = no reduction, 0.5 = half load, etc.)",
        example=0.5,
        ge=0.0,
        le=1.0,
    )
    power_threshold: float = Field(
        0.0, 
        description="Load thermal power below which the cooling system is inactive, in kWth",
        example=20.0,
        ge=0.0,
    )

    class Config:
        json_encoders = {Path: str}
        arbitrary_types_allowed = True
    
    def to_config_file(self, path: Path) -> None:
        
        if isinstance(path, str):
            path = Path(path)
        
        if path.exists():
            # Read existing config, and replace or add this id
            config = json.loads(path.read_text())
        else:
            config = {}
        if self.id in config:
            logger.warning(
                f"Simulation ID '{self.id}' already exists in {path}, overwriting."
            )
        config[self.id] = self.model_dump(exclude_none=True, mode="json")
        
        path.write_text(json.dumps(config, indent=4))
        logger.info(f"Wrote simulation config to {path}")
     
    @classmethod   
    def from_config_file(cls, path: Path, id: str) -> "EvaluationConfig":
        
        if isinstance(path, str):
            path = Path(path)
            
        if not path.exists():
            raise FileNotFoundError(f"Config file {path} does not exist.")
        config = json.loads(path.read_text())
        if id not in config:
            raise ValueError(f"Simulation ID '{id}' not found in {path}.")
        
        return cls.model_validate(config[id])

