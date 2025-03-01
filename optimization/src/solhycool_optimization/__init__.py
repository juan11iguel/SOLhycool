from typing import Literal
from dataclasses import dataclass, asdict
import numpy as np

import matlab

from solhycool_modeling.utils import dump_in_span

@dataclass
class RealDecVarsBoxBounds:
    """ Real decision variables box bounds, as in: (lower bound, upper bound)"""
    qc: tuple[float, float] = (5.2211, 24.1543)
    Rp: tuple[float, float] = (0., 1.)
    Rs: tuple[float, float] = (0., 1.)
    wdc: tuple[float, float] = (11.0, 99.1800)
    wwct: tuple[float, float] = (0., 93.4161)
    
@dataclass
class DecisionVariables:
    qc: float | np.ndarray[float]
    Rp: float | np.ndarray[float]
    Rs: float | np.ndarray[float]
    wdc: float | np.ndarray[float]
    wwct: float | np.ndarray[float]
    
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
    
