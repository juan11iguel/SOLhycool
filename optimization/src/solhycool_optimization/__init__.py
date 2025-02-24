from typing import Literal
from datetime import datetime
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
from iapws import IAPWS97 as w_props
import matlab

from solhycool_optimization.utils import dump_in_span

@dataclass
class RealDecVarsBoxBounds:
    """ Real decision variables box bounds, as in: (lower bound, upper bound)"""
    qc: tuple[float, float] = (5.2211, 24.1543)
    Rp: tuple[float, float] = (0., 1.)
    Rs: tuple[float, float] = (0., 1.)
    wdc: tuple[float, float] = (11.0, 99.1800)
    wwct: tuple[float, float] = (0., 93.4161)
    
@dataclass
class EnvironmentVariables:
    """
    Simple class to make sure that the required environment variables are passed
    
    All the variables should be 1D arrays with as many elements as the horizon of the optimization problem
    """
    # Weather
    HR: float | np.ndarray[float] | pd.Series  # Relative humidity, %
    Tamb: float | np.ndarray[float] | pd.Series # Ambient temperature, ºC
    
    # Thermal load
    Tv: float | np.ndarray[float] | pd.Series # Vapor temperature, ºC
    Q: float | np.ndarray[float] | pd.Series # Thermal power, kW
    
    # Costs
    cost_e: float | np.ndarray[float] | pd.Series # Cost of electricity, €/kWhe
    cost_w: float | np.ndarray[float] | pd.Series = None # Cost of water, €/m³ 

    # Thermal load (optional)
    mv: float | np.ndarray[float] | pd.Series = None # Vapor mass flow rate, kg/s
    
    def __post_init__(self) -> None:
        if isinstance(self.Tv, matlab.double):
            Tv = np.asarray(self.Tv).flatten()[0]
            Pth = np.asarray(self.Q).flatten()[0]
        else:
            Tv = self.Tv
            Pth = self.Q
            
        # Calculate mv
        mv = Pth / (w_props(T=Tv+273.15, x=1).h - w_props(T=Tv+273.15, x=0).h) * 3600
        
        if isinstance(self.Tv, matlab.double):
            self.mv = matlab.double([mv])
        else:
            self.mv = mv
    
    def dump_at_index(self, idx: int, return_dict: bool = False, return_format: Literal["float", "matlab"] = "float") -> "EnvironmentVariables":
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
        
        return dump if return_dict else EnvironmentVariables(**dump)
    
    def dump_in_span(self, span: tuple[int, int] | tuple[datetime, datetime], return_format: Literal["values", "series"] = "values") -> 'EnvironmentVariables':
        """ Dump environment variables within a given span """
        
        vars_dict = dump_in_span(vars_dict=asdict(self), span=span, return_format=return_format)
        return EnvironmentVariables(**vars_dict)
    
    def resample(self, *args, **kwargs) -> "EnvironmentVariables":
        """ Return a new resampled environment variables instance """
        
        output = {}
        for name, value in asdict(self).items():
            if value is None:
                continue
            elif not isinstance(value, pd.Series):
                raise TypeError(f"All attributes must be pd.Series for datetime indexing. Got {type(value)} instead.")
            
            target_freq = int(float(args[0][:-1]))
            current_freq = value.index.freq.n
            
            value = value.resample(*args, **kwargs)
            if  target_freq > current_freq: # Downsample
                value = value.mean()
            else: # Upsample
                value = value.interpolate()
            output[name] = value
            
        return EnvironmentVariables(**output)
    
    def to_matlab(self) -> "EnvironmentVariables":
        """ Convert all attributes to matlab.double """
        
        return EnvironmentVariables(**{k: matlab.double(v) for k, v in asdict(self).items() if v is not None})
    
@dataclass
class DecisionVariables:
    qc: float
    Rp: float
    Rs: float
    wdc: float
    wwct: float
    
