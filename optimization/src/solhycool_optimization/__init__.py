from typing import Literal
from inspect import signature
from pathlib import Path
from dataclasses import dataclass, asdict, field
import numpy as np
from loguru import logger
import pandas as pd
from solhycool_modeling import ModelInputsRange

# Always import combined_cooler before importing matlab
import combined_cooler
import matlab

from solhycool_modeling import ModelInputsRange
from solhycool_modeling.utils import dump_in_span

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
    consumption_arrays: list[np.ndarray[float]] # Array with the consumption values for the candidate operation points
    fitness_history: pd.Series # Series with the fitness history of the path selection optimization
    pareto_idxs: list[int] # Path of indices of the pareto fronts from the dataset of candidate operation points
    selected_pareto_idxs: list[int] # Path of indices of the selected pareto fronts
    df_results: pd.DataFrame # DataFrame with the results of the path composed by the selected pareto fronts
