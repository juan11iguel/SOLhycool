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
from tables.exceptions import NaturalNameWarning

# Always import combined_cooler before importing matlab
import combined_cooler
import matlab

from solhycool_modeling import ModelInputsRange
from solhycool_modeling.utils import dump_in_span
from solhycool_optimization.utils.serialization import get_queryable_columns

warnings.filterwarnings("ignore", category=NaturalNameWarning)

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
            dump = {k: matlab.double([v]) for k, v in dump.items()}

        return dump if return_dict else DecisionVariables(**dump)

    def dump_in_span(self, span: tuple[int, int]) -> 'DecisionVariables':
        """ Dump environment variables within a given span """

        vars_dict = dump_in_span(vars_dict=asdict(self), span=span, return_format="values")
        
        return DecisionVariables(**vars_dict)

    def to_matlab(self) -> "DecisionVariables":
        """ Convert all attributes to matlab.double """
        
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
    
    def generate_arrays(self, ) -> "ValuesDecisionVariables":
        inputs_range = ModelInputsRange()
        
        return ValuesDecisionVariables(**{
            name: np.linspace(getattr(inputs_range, name)[0], getattr(inputs_range, name)[1], n_values) 
            for name, n_values in asdict(self).items()
        })
        
@dataclass
class DayResults:
    index: pd.DatetimeIndex # Index of the results
    df_paretos: list[pd.DataFrame] # List of dataframes with the pareto fronts for each step
    selected_pareto_idxs: list[int] # Path of indices of the selected pareto fronts
    df_results: pd.DataFrame # DataFrame with the results of the path composed by the selected pareto fronts
    fitness_history: Optional[pd.Series] = None # Series with the fitness history of the path selection optimization
    consumption_arrays: Optional[list[np.ndarray[float]]] = None # Array with the consumption values for the candidate operation points
    pareto_idxs: Optional[list[int]] = None # Path of indices of the pareto fronts from the dataset of candidate operation points
    
    date_str: str = None

    def __post_init__(self):
        if self.date_str is None:
            self.date_str = self.index[0].strftime("%Y%m%d")
        # if len(self.index) != len(self.df_paretos):
        #     raise ValueError("Length of index and df_paretos must be the same")
            

    @classmethod
    def initialize(cls, input_path: Path, date_str: Optional[str] = None, log: bool = True) -> "DayResults":
        if input_path.suffix == ".gz":
            # Uncompress the gzip file into a temporary .h5 file
            with gzip.open(input_path, 'rb') as f_in:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    temp_path = Path(f_out.name)
        else:
            temp_path = input_path
            
        try:
            with pd.HDFStore(temp_path, mode='r') as store:
                # Access the results dataframe
                df_results = store["/results"].sort_index()
                
                if date_str is None:
                    available_dates = sorted(set(idx.date() for idx in df_results.index))
                    date_str = available_dates[0].strftime("%Y%m%d")

                # Ensure the index is datetime and in UTC
                if not isinstance(df_results.index, pd.DatetimeIndex):
                    raise TypeError(f"The index of '/results' is not a DatetimeIndex, got {type(df_results.index)}")

                # Filter by date_str (assumed to be in "YYYYMMDD" format)
                date_prefix = pd.to_datetime(date_str, format="%Y%m%d").date()
                filtered_index = df_results.index[df_results.index.date == date_prefix]

                if filtered_index.empty:
                    available_dates = sorted(set(idx.date().isoformat() for idx in df_results.index))
                    raise ValueError(f"No results found for date {date_str} in {input_path.stem}. "
                                    f"Available dates are: {available_dates}")

                # Load data for the selected date
                df_paretos = []
                consumption_arrays = []

                for dt in filtered_index:
                    key = dt.strftime("%Y%m%dT%H%M")
                    # print(dt, key)
                    table_key = f"/pareto/{key}"
                    if table_key in store:
                        df_paretos.append(store[table_key])
                    
                    table_key = f"/pareto/{key}"
                    if table_key in store:
                        fitness_history = store.get(f"/paths/fitness_history/{key}")
                    else:
                        fitness_history = None
                    
                    table_key = f"/consumption/{key}"
                    if table_key in store:
                        df_consumption = store[table_key]
                        consumption_arrays.append(df_consumption.to_numpy())

                # Load df_results (subset for the day)
                df_results = df_results.loc[filtered_index]
                # df_results = df_results.loc[
                #     (df_results.index >= filtered_index[0]) & (df_results.index <= filtered_index[-1])
                # ]

                # Load indices of points in the pareto front and the ones selected from it for each step
                table_key = filtered_index[0].strftime("%Y%m%d")
                # pareto_idxs = store[f"/paths/pareto_idxs/{table_key}"].to_list()
                selected_pareto_idxs = store[f"/paths/selected_pareto_idxs/{table_key}"].to_list()
                
                table_key_ = f"/paths/pareto_idxs/{table_key}"
                if table_key_ in store:
                    pareto_idxs = store[table_key_].apply(lambda row: [int(x) for x in row.dropna()], axis=1)
                else:
                    pareto_idxs = None

                # pareto_idxs = [pareto_idxs_series.loc[dt] for dt in filtered_index]
                # selected_pareto_idxs = [selected_pareto_idxs_series.loc[dt] for dt in filtered_index]
                # np.concatenate().tolist()

            day_results = cls(
                index=filtered_index,
                df_paretos=df_paretos,
                consumption_arrays=consumption_arrays,
                fitness_history=fitness_history,
                df_results=df_results,
                pareto_idxs=pareto_idxs,
                selected_pareto_idxs=selected_pareto_idxs
            )
            
            if log:
                logger.info(f"DayResults loaded for {date_str} from {input_path}")
            
        finally:
            if input_path.suffix == ".gz":
                temp_path.unlink()  # Clean up temp .h5 file
        
        return day_results
        
    def export(self, output_path: Path, reduced: bool = False) -> None:
        """ Export results to a file. """
        
        if not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
        if reduced:
            self = copy.deepcopy(self) # To avoid modifying the original object
            self.consumption_arrays = None
            self.pareto_idxs = None 
            
        if self.consumption_arrays is None:
            self.consumption_arrays = [None] * len(self.df_paretos)
        
        with pd.HDFStore(output_path, mode='a', complevel=9, complib='zlib') as store:
            for dt, df_pareto, consumption_array in zip(
                self.index, self.df_paretos, self.consumption_arrays
            ):
                table_key = dt.strftime("%Y%m%dT%H%M")

                # Save pareto front for this timestep
                store.put(
                    f"/pareto/{table_key}", df_pareto, format="table", data_columns=get_queryable_columns(df_pareto))

                # Save consumption array for this timestep
                if consumption_array is not None:
                    df_consumption = pd.DataFrame(consumption_array, columns=["Cw", "Ce"])
                    store.put(f"/consumption/{table_key}", df_consumption, format="table", data_columns=True)

                # Save path selection optimization fitness history
                if self.fitness_history is not None:
                    store.put(f"/paths/fitness_history/{table_key}", self.fitness_history, format="table",)

            # Append df_results (path of selected solutions)
            if "/results" in store:
                existing = store["/results"]
                results_df = pd.concat([existing, self.df_results])
            else:
                results_df = self.df_results
            store.put("/results", results_df.sort_index(), format="table", data_columns=get_queryable_columns(results_df), complib="zlib", complevel=9,)

            # Save indices of points in the pareto front and the ones selected from it for each step
            table_key = self.index[0].strftime("%Y%m%d")
            store.put(f"/paths/selected_pareto_idxs/{table_key}", pd.Series(self.selected_pareto_idxs))
            
            if self.pareto_idxs is not None:
                # store.put(f"/paths/pareto_idxs/{table_key}", pd.Series(self.pareto_idxs))
                lists = [arr.tolist() if not isinstance(arr, list) else arr for arr in self.pareto_idxs]
                max_len = max(len(lst) for lst in lists)
                padded_pareto_idxs_df = pd.DataFrame([lst + [np.nan] * (max_len - len(lst)) for lst in lists])
                store.put(
                    f"/paths/pareto_idxs/{table_key}",
                    padded_pareto_idxs_df,
                    format="table",
                    complib="zlib",
                    complevel=9,
                )

        logger.info(f"Results for {self.date_str} saved to {output_path}")
        
        
@dataclass
class MultipleDayResults:
    """Class for handling multiple day results."""
    df_results: pd.DataFrame # DataFrame with the results of the path composed by the selected pareto fronts joined
    date_strs: list[str] # List of date strings for the days
    index: list[pd.DatetimeIndex] # Index of the results
    df_paretos: list[list[pd.DataFrame]] # List of dataframes with the pareto fronts for each step
    fitness_history: list[pd.Series] # Series with the fitness history of the path selection optimization
    selected_pareto_idxs: list[list[int]] # Path of indices of the selected pareto fronts
    df_results_individual: list[pd.DataFrame] # DataFrame with the results of the path composed by the selected pareto fronts for each day
    consumption_arrays: list[list[np.ndarray[float]]] = None # Array with the consumption values for the candidate operation points
    pareto_idxs: list[list[int]] = None # Path of indices of the pareto fronts from the dataset of candidate operation points

    @classmethod
    def initialize_from_file(cls, results_path: Path, date_strs: list[str]) -> "MultipleDayResults":
        """Initialize the class from a possibly gzipped file."""
        
        if results_path.suffix == ".gz":
            # Uncompress the gzip file into a temporary .h5 file
            with gzip.open(results_path, 'rb') as f_in:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                    temp_path = Path(f_out.name)
        else:
            temp_path = results_path

        try:
            day_results_list = [
                DayResults.initialize(temp_path, date_str=date_str, log=False) for date_str in date_strs
            ]
        finally:
            if results_path.suffix == ".gz":
                temp_path.unlink()  # Clean up temp .h5 file

        return cls.initialize_from_day_results(day_results_list)

    @classmethod
    def initialize_from_day_results(cls, day_results_list: list[DayResults]) -> "MultipleDayResults":
        """Initialize the class from a list of DayResults."""
        
        multiple_day_results = cls(
            date_strs=[day_results.date_str for day_results in day_results_list],
            index=[day_results.index for day_results in day_results_list],
            df_paretos=[day_results.df_paretos for day_results in day_results_list],
            consumption_arrays=[day_results.consumption_arrays for day_results in day_results_list],
            fitness_history=[day_results.fitness_history for day_results in day_results_list],
            pareto_idxs=[day_results.pareto_idxs for day_results in day_results_list],
            selected_pareto_idxs=[day_results.selected_pareto_idxs for day_results in day_results_list],
            df_results=pd.concat([day_result.df_results for day_result in day_results_list], axis=0).sort_index(),
            df_results_individual=[day_result.df_results for day_result in day_results_list]
        )
        
        logger.info(f"MultipleDayResults initialized with {len(day_results_list)} days ({multiple_day_results.date_strs[0]}-{multiple_day_results.date_strs[-1]})")
        
        return multiple_day_results
            
    def export(self, output_path: Path) -> None:
        """ Export results to a gzip-compressed file. """

        temp_h5_path = output_path.with_suffix(".h5")

        for day_idx in range(len(self.df_results_individual)):
            DayResults(
                index=self.index[day_idx],
                df_paretos=self.df_paretos[day_idx],
                fitness_history=self.fitness_history[day_idx],
                selected_pareto_idxs=self.selected_pareto_idxs[day_idx],
                df_results=self.df_results_individual[day_idx],
                consumption_arrays=self.consumption_arrays[day_idx] if self.consumption_arrays is not None else None,
                pareto_idxs=self.pareto_idxs[day_idx] if self.pareto_idxs is not None else None,
            ).export(temp_h5_path)

        # Compress the .h5 file using gzip
        with open(temp_h5_path, 'rb') as f_in, gzip.open(output_path.with_suffix(".h5.gz"), 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

        temp_h5_path.unlink()  # Remove uncompressed .h5 file
        
        logger.info(f"Results for {self.date_strs[0]}-{self.date_strs[-1]} compressed and saved to {output_path}")


def import_simulation_results(results_path: Path) -> pd.DataFrame:
    """ Import simulation results from a gzip-compressed file. """
    
    if results_path.suffix == ".gz":
        # Uncompress the gzip file into a temporary .h5 file
        with gzip.open(results_path, 'rb') as f_in:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as f_out:
                shutil.copyfileobj(f_in, f_out)
                temp_path = Path(f_out.name)
    else:
        temp_path = results_path

    try:
        df_results = pd.read_hdf(temp_path, key="/results")
    finally:
        if results_path.suffix == ".gz":
            temp_path.unlink()  # Clean up temp .h5 file

    return df_results