from dataclasses import asdict, dataclass, field
from collections.abc import Iterable
from datetime import datetime
from typing import Literal, Optional, ClassVar
import inspect
import numpy as np
import pandas as pd
from enum import Enum
from iapws import IAPWS97 as w_props
from pathlib import Path
from pydantic import BaseModel, Field, model_validator
from typing import get_origin, get_args, Union

import combined_cooler_model # Always import combined_cooler_model before importing matlab
import matlab

class EnvIds(str, Enum):
    """ Environment variables identifiers and mapping to dataframe columns """
    HR = "HR_pct"
    Tamb = "Tamb_C"
    Tv = "Tv_C"
    Q = "Q_kW"
    Pe = "Ce_spot_market_price_eur_kWh"
    Pw_s1 = "water_price_eur_l"
    Pw_s2 = "water_price_alternative_eur_l"
    Vavail = "Vavail_m3"
    deltaV = "deltaV_m3_h"
    mv = "mv_kgh"
    
class EnvIdsMatlab(str, Enum):
    """ Environment variables identifiers for matlab struct """
    HR = "HR_pp"
    Tamb = "Tamb_C"
    Tv = "Tv_C"
    mv = "mv_kgh"
    
@dataclass
class ModelInputsRange:
    """ Real decision variables box bounds, as in: (lower bound, upper bound)"""
    qc: tuple[float, float] = (6., 24.)
    Rp: tuple[float, float] = (0., 1.)
    Rs: tuple[float, float] = (0., 1.)
    wdc: tuple[float, float] = (11.0, 99.1800)
    wwct: tuple[float, float] = (21., 93.4161)
    Tamb: tuple[float, float] = (3., 50.)
    HR: tuple[float, float] = (1., 99.)
    Tdc_in: tuple[float, float] = (25., 55.)
    Twct_in: tuple[float, float] = (25., 55.)
    
@dataclass
class EnvironmentVariables:
    """
    Simple class to make sure that the required environment variables are passed

    All the variables should be 1D arrays with as many elements as the horizon of the optimization problem
    """
    # Weather
    HR: float | np.ndarray[float]  # Relative humidity, %
    Tamb: float | np.ndarray[float] # Ambient temperature, ºC

    # Thermal load
    Tv: float | np.ndarray[float] # Vapor temperature, ºC
    Q: Optional[float | np.ndarray[float]] = None # Thermal power, kWth

    # Costs
    Pe: Optional[float | np.ndarray[float]] = None # Cost of electricity, €/kWhe
    Pw: Optional[float | np.ndarray[float]] = None # Cost of water, €/l
    Pw_s1: Optional[float | np.ndarray[float]] = None # Cost of water from source 1, €/l
    Pw_s2: Optional[float | np.ndarray[float]] = None # Cost of water from source 2, €/l
    
    Vavail: Optional[float | np.ndarray[float]] = None # Available volume of water, m³
    deltaV: Optional[float | np.ndarray[float]] = None # Variation of available volume of water, m³/h

    # Thermal load (optional)
    mv: Optional[float | np.ndarray[float]] = None # Vapor mass flow rate, kg/h!!
    
    # Add a hidden field to store the list of names of the fields from the dataframe
    

    def __post_init__(self) -> None:
        
        assert self.mv is not None or self.Q is not None, "Either mv or Q must be provided"
        assert not np.any(np.isnan(self.Tv)), "Tv cannot contain NaN values"
        assert not np.any(np.isnan(self.HR)), "HR cannot contain NaN values"
        assert not np.any(np.isnan(self.Tamb)), "Tamb cannot contain NaN values"
        
        if self.mv is None:
        
            if isinstance(self.Tv, matlab.double):
                Tv = np.asarray(self.Tv).flatten()[0]
                Pth = np.asarray(self.Q).flatten()[0]
            else:
                Tv = self.Tv
                Pth = self.Q

            # Calculate mv
            # if isinstance(self.Tv, Iterable):
            #     hsat_v = w_props.from_list(T=Tv+273.15, x=1).h
            #     hsat_l = w_props.from_list(T=Tv+273.15, x=0).h
            # else:
            if isinstance(self.Tv, Iterable):
                # Terrible
                mv = np.array(
                    [pth / (w_props(T=tv+273.15, x=1).h - w_props(T=tv+273.15, x=0).h) * 3600 for pth, tv in zip(Pth, Tv)]
                )
            else:
                hsat_v = w_props(T=Tv+273.15, x=1).h
                hsat_l = w_props(T=Tv+273.15, x=0).h
                mv = Pth / (hsat_v - hsat_l) * 3600 # kg/h

            if isinstance(self.Tv, matlab.double):
                self.mv = matlab.double([mv])
            else:
                self.mv = mv
                
        if self.Q is None:
        
            if isinstance(self.Tv, matlab.double):
                Tv = np.asarray(self.Tv).flatten()[0]
                Mv = np.asarray(self.mv).flatten()[0]
            else:
                Tv = self.Tv
                Mv = self.mv

            # Calculate Q
            if isinstance(self.Tv, Iterable):
                # Terrible
                Q = np.array(
                    [mv * (w_props(T=tv+273.15, x=1).h - w_props(T=tv+273.15, x=0).h) / 3600 for mv, tv in zip(Mv, Tv)]
                )
            else:
                hsat_v = w_props(T=Tv+273.15, x=1).h
                hsat_l = w_props(T=Tv+273.15, x=0).h
                Q = mv * (hsat_v - hsat_l) / 3600 # kWth

            if isinstance(self.Tv, matlab.double):
                self.Q = matlab.double([Q])
            else:
                self.Q = Q
                
            assert not np.any(np.isnan(self.Q)), "Q cannot contain NaN values"
            
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "EnvironmentVariables":
        """
        Create an EnvironmentVariables instance from a pandas dataframe

        Parameters:
        - df: Pandas dataframe with the data

        Returns:
        - An EnvironmentVariables instance
        """
        return cls(
            HR=np.asarray(df[EnvIds.HR.value]),
            Tamb=np.asarray(df[EnvIds.Tamb.value]),
            Q=np.asarray(df[EnvIds.Q.value]),
            Tv=np.asarray(df[EnvIds.Tv.value]),
            mv=df[EnvIds.mv.value] if EnvIds.mv.value in df else None, 
            Pe=np.asarray(df[EnvIds.Pe.value]),
            Pw=np.asarray(df[EnvIds.Pw.value]) if EnvIds.Pw.value in df else None,
            Pw_s1=np.asarray(df[EnvIds.Pw.value]) if EnvIds.Pw.value in df else None,
            Pw_s2=np.asarray(df[EnvIds.Pw_s2.value]) if EnvIds.Pw_s2.value in df else None,
            Vavail=np.asarray(df[EnvIds.Vavail.value]) if EnvIds.Vavail.value in df else None,
            deltaV=np.asarray(df[EnvIds.deltaV.value]) if EnvIds.deltaV.value in df else None 
        )

    @classmethod
    def from_series(cls, ds: pd.Series) -> "EnvironmentVariables":
        """
        Create an EnvironmentVariables instance from a pandas Series

        Parameters:
        - ds: Pandas Series with the data

        Returns:
        - An EnvironmentVariables instance
        """
        return cls(
            HR=ds[EnvIds["HR"].value],
            Tamb=ds[EnvIds["Tamb"].value],
            Q=ds[EnvIds["Q"].value],
            Tv=ds["Tv_C"],
            mv=ds["mv_kgh"] if "mv_kgh" in ds else None, 
            Pe=ds[EnvIds.Pe.value],
            Pw=ds[EnvIds.Pw_s1.value] if EnvIds.Pw_s1.value in ds else None,
            Pw_s1=ds[EnvIds.Pw_s1.value] if EnvIds.Pw_s1.value in ds else None,
            Pw_s2=ds[EnvIds.Pw_s2.value] if EnvIds.Pw_s2.value in ds else None,
            Vavail=ds[EnvIds.Vavail.value] if EnvIds.Vavail.value in ds else None,
            deltaV=ds["deltaV_m3_h"] if "deltaV_m3_h" in ds else None 
        )
        
    def reduce_load(self, reduction_factor: float = 0.5) -> "EnvironmentVariables":
        
        self.Q = self.Q * reduction_factor
        self.mv = self.mv * reduction_factor
        
        return self
        
    def update_available_water(self, Cw_lh: float, sample_time_h: float = 1) -> float:
        # Vavail in m^3
        self.Vavail = max(0, self.Vavail-Cw_lh*1e-3*sample_time_h)
        
        return self.Vavail
        

    def dump_at_index(self, idx: int, return_dict: bool = False, return_format: Literal["number", "matlab"] = "number") -> "EnvironmentVariables":
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

    def dump_in_span(self, span: tuple[int, int]) -> 'EnvironmentVariables':
        """ Dump environment variables within a given span """
        
        from solhycool_modeling.utils import dump_in_span

        vars_dict = dump_in_span(vars_dict=asdict(self), span=span, return_format="values")
        
        return EnvironmentVariables(**vars_dict)

    def to_matlab(self) -> "EnvironmentVariables":
        """Convert all attributes to matlab.double (2D lists of floats)"""
        def convert_value(v):
            if isinstance(v, (np.ndarray, list)):
                return matlab.double(np.atleast_2d(np.array(v, dtype=float)).tolist())
            elif isinstance(v, (int, float, np.integer, np.floating)):
                return matlab.double([[float(v)]])
            else:
                raise TypeError(f"Unsupported type for MATLAB conversion: {type(v)}")

        return EnvironmentVariables(**{
            k: convert_value(v)
            for k, v in asdict(self).items()
            if v is not None
        })
        
    def to_matlab_dict(self) -> dict:
        data = asdict(self.to_matlab())
        allowed_keys = {e.name: e.value for e in EnvIdsMatlab}
        return {
            allowed_keys[k]: v
            for k, v in data.items()
            if k in allowed_keys and v is not None
        }
    
    def constrain_to_model(self, model_inputs_range: ModelInputsRange = ModelInputsRange()) -> "EnvironmentVariables":
    # TODO: Consider requiring to pass a ModelInputsRange instance, instead of optional
        """
        Constrain the environment variables to the model inputs range

        Parameters:
        - model_inputs_range: ModelInputsRange instance
        """
        
        for key, value in asdict(model_inputs_range).items():
            if key in self.__dict__ and self.__dict__[key] is not None:
                if isinstance(self.__dict__[key], Iterable):
                    self.__dict__[key] = np.clip(self.__dict__[key], value[0], value[1])
                else:
                    self.__dict__[key] = max(value[0], min(value[1], self.__dict__[key]))
                    
        return self
    
    def to_dataframe(self, index: pd.DatetimeIndex = None, column_names: Optional[dict] = None) -> pd.DataFrame:
        """
        Convert the environment variables to a pandas dataframe

        Parameters:
        - index: Pandas DatetimeIndex to use as index of the dataframe

        Returns:
        - A pandas dataframe with the environment variables
        """
        
        if column_names is None:
            column_names = {e.name: e.value for e in EnvIds}
        
        data = asdict(self)
        df = pd.DataFrame(data, index=index)
        
        df.rename(columns=column_names, inplace=True)
        
        # Convert matlab.double to numpy arrays
        for col in df.columns:
            if isinstance(df[col].iloc[0], matlab.double):
                df[col] = df[col].apply(lambda x: np.asarray(x).flatten()[0])
                
        return df

@dataclass
class OperationPoint:
    # Ambient conditions
    Tamb: float = field(metadata={"description": "Ambient temperature", "units": "ºC"})
    HR: float = field(metadata={"description": "Relative humidity", "units": "%"})

    # Load conditions
    mv: float = field(metadata={"description": "Vapor mass flow rate", "units": "kg/h"})
    Tv: float = field(metadata={"description": "Vapour temperature in the condenser", "units": "ºC"})

    # Condenser
    qc: float = field(metadata={"description": "Cooling recirculation flow rate", "units": "m³/h"})
    Tc_in: float = field(metadata={"description": "Condenser inlet temperature", "units": "ºC"})
    Tc_out: float = field(metadata={"description": "Condenser outlet temperature", "units": "ºC"})
    Tcond: float = field(metadata={"description": "Condensate temperature", "units": "ºC"})
    Qc_released: float = field(metadata={"description": "Heat released by steam in the condenser", "units": "kWth"})
    Qc_absorbed: float = field(metadata={"description": "Heat absorbed by the refrigerant in the condenser", "units": "kWth"})
    Qc_transfered: float = field(metadata={"description": "Heat transferred in the condenser", "units": "kWth"})
    Ce_c: float = field(metadata={"description": "Electrical consumption by recirculation pump", "units": "kWe"})

    # Hydraulic distribution
    Rp: float = field(metadata={"description": "Parallel distribution ratio", "units": "-"})
    Rs: float = field(metadata={"description": "DC -> WCT series distribution ratio", "units": "-"})

    # DC
    wdc: float = field(metadata={"description": "DC fan percentage", "units": "%"})
    qdc: float = field(metadata={"description": "DC cooling flow rate", "units": "m³/h"})
    Tdc_in: float = field(metadata={"description": "DC inlet temperature", "units": "ºC"})
    Tdc_out: float = field(metadata={"description": "DC outlet temperature", "units": "ºC"})
    Ce_dc: float = field(metadata={"description": "DC electrical consumption", "units": "kWe"})
    Qdc: float = field(metadata={"description": "DC heat transfer", "units": "kWth"})

    # WCT
    wwct: float = field(metadata={"description": "WCT fan percentage", "units": "%"})
    qwct: float = field(metadata={"description": "WCT cooling flow rate", "units": "m³/h"})
    qwct_s: float = field(metadata={"description": "WCT secondary cooling flow rate", "units": "m³/h"})
    qwct_p: float = field(metadata={"description": "WCT primary cooling flow rate", "units": "m³/h"})
    Twct_in: float = field(metadata={"description": "WCT inlet temperature", "units": "ºC"})
    Twct_out: float = field(metadata={"description": "WCT outlet temperature", "units": "ºC"})
    Ce_wct: float = field(metadata={"description": "WCT electrical consumption", "units": "kWe"})
    Cw_wct: float = field(metadata={"description": "WCT water consumption", "units": "l/h"})
    Qwct: float = field(metadata={"description": "WCT heat transfer", "units": "kWth"})

    # Combined cooler
    Tcc_out: float = field(metadata={"description": "Combined cooler outlet temperature", "units": "ºC"})

    # Optional fields
    Cw_s1: float = field(default=None, metadata={"description": "Water consumption from source 1", "units": "l/h"})
    Cw_s2: float = field(default=0, metadata={"description": "Water consumption from source 2", "units": "l/h"})
    Pw: float = field(default=None, metadata={"description": "Price of water", "units": "€/l"})
    Pw_s1: float = field(default=None, metadata={"description": "Price of water from source 1", "units": "€/l"})
    Pw_s2: float = field(default=None, metadata={"description": "Price of water from source 2", "units": "€/l"})
    Pe: float = field(default=None, metadata={"description": "Price of electricity", "units": "€/kWh"})
    Vavail: float = field(default=None, metadata={"description": "Available volume of water", "units": "l"}) # Seguro que litros?
    deltaV: float = field(default=None, metadata={"description": "Variation of available volume of water", "units": "l/h"})
    time: datetime = field(default=None, metadata={"description": "Datetime of the operation point", "units": "datetime"})

    # Computable fields
    qdc_only: Optional[float] = field(default=None, metadata={"description": "DC only cooling flow rate", "units": "m³/h"})
    Tcc_in: Optional[float] = field(default=None, metadata={"description": "Combined cooler inlet temperature", "units": "ºC"})
    Ce_cc: Optional[float] = field(default=None, metadata={"description": "Combined cooler electrical consumption", "units": "kWe"})
    Cw_cc: Optional[float] = field(default=None, metadata={"description": "Combined cooler water consumption", "units": "l/h"})
    Qcc: Optional[float] = field(default=None, metadata={"description": "Combined cooler heat transfer", "units": "kWth"})
    Ce: Optional[float] = field(default=None, metadata={"description": "Total electrical consumption", "units": "kWe"})
    Cw: Optional[float] = field(default=None, metadata={"description": "Total water consumption", "units": "l/h"})
    qcc: Optional[float] = field(default=None, metadata={"description": "Combined cooler flow rate", "units": "m³/h"})
    Vavail_s1: Optional[float] = field(default=None, metadata={"description": "Available volume of water from source 1", "units": "l"})
    Je: Optional[float] = field(default=None, metadata={"description": "Total electrical cost", "units": "€/h"})
    Jw: Optional[float] = field(default=None, metadata={"description": "Total water cost", "units": "€/h"})
    J: Optional[float] = field(default=None, metadata={"description": "Total cost", "units": "€/h"})
    Je_c: Optional[float] = field(default=None, metadata={"description": "Recirculation pump electrical cost", "units": "€/h"})
    Je_dc: Optional[float] = field(default=None, metadata={"description": "DC electrical cost", "units": "€/h"})
    Je_wct: Optional[float] = field(default=None, metadata={"description": "WCT electrical cost", "units": "€/h"})
    Jw_wct: Optional[float] = field(default=None, metadata={"description": "WCT water cost", "units": "€/h"})
    Jw_s1: Optional[float] = field(default=None, metadata={"description": "Water cost from source 1", "units": "€/h"})
    Jw_s2: Optional[float] = field(default=None, metadata={"description": "Water cost from source 2", "units": "€/h"})
    dc_active: Optional[bool] = field(default=None, metadata={"description": "State of dry cooler (active=1, inactive=0)", "units": ""},)
    dc_mode: Optional[int] = field(default=None, metadata={"description": "Operation mode of dry cooler (0=auto, 1=manual)", "units": ""},)
    wct_active: Optional[bool] = field(default=None, metadata={"description": "State of wet cooler (active=1, inactive=0)", "units": ""},)
    wct_mode: Optional[int] = field(default=None, metadata={"description": "Operation mode of wet cooler (0=auto, 1=manual)", "units": ""},)
    
    def __post_init__(self) -> None:
        
        # Fill not provided computable values
        if self.Tcc_in is None:
            self.Tcc_in = self.Tc_out
            
        if self.Ce_cc is None:
            self.Ce_cc = self.Ce_dc + self.Ce_wct
            
        if self.Cw_cc is None:
            self.Cw_cc = self.Cw_wct
        
        if self.Cw_s1 is None:
            self.Cw_s1 = self.Cw_cc
            
        if self.Qcc is None:
            self.Qcc = self.Qdc + self.Qwct
            
        if self.qdc_only is None:
            self.qdc_only = self.qdc * (1-self.Rs)
            
        if self.Ce is None:
            self.Ce = self.Ce_cc + self.Ce_c
            
        if self.Cw is None:
            self.Cw = self.Cw_cc    
            
        if self.qcc is None:
            self.qcc = self.qc
            
        if self.Vavail_s1 is None and self.Vavail is not None:
            self.Vavail_s1 = self.Vavail
            
        if self.Pe is not None:
            if self.Je is None:
                self.Je = self.Ce * self.Pe
                
            if self.Je_c is None:
                self.Je_c = self.Ce_c * self.Pe
            
            if self.Je_dc is None:
                self.Je_dc = self.Ce_dc * self.Pe
                
            if self.Je_wct is None:
                self.Je_wct = self.Ce_wct * self.Pe
                
        # Only one source of water
        if self.Pw is None and self.Pw_s1 is not None and self.Pw_s2 is None:
            self.Pw = self.Pw_s1        
        if self.Pw is not None:
            if self.Jw is None:
                self.Jw = self.Cw * self.Pw
                
            if self.Jw_wct is None:
                self.Jw_wct = self.Cw_wct * self.Pw
                
            if self.Pw_s1 is None:
                self.Pw_s1 = self.Pw
                self.Jw_s1 = self.Cw_s1 * self.Pw_s1
        
        # Multiple sources of water
        if self.Pw_s1 is not None and self.Pw_s2 is not None:
            if self.Jw_s1 is None and self.Cw_s1 is not None:
                self.Jw_s1 = self.Cw_s1 * self.Pw_s1
            if self.Jw_s2 is None and self.Cw_s2 is not None:
                self.Jw_s2 = self.Cw_s2 * self.Pw_s2
            self.Jw_wct = self.Jw_s1 + self.Jw_s2
            self.Jw = self.Jw_wct
                
        # Total cost
        if self.J is None and self.Je is not None and self.Jw is not None:
            self.J = self.Je + self.Jw
            
        # Set the available volume of water
        if self.Vavail_s1 is not None:
            if self.Vavail is None:
                self.Vavail = self.Vavail_s1
        else:
            if self.Vavail is not None:
                self.Vavail_s1 = self.Vavail
                
        # Set operation variables (active and mode)
        if self.dc_active is None:
            self.dc_active = self.Qdc > 0
        if self.dc_mode is None:
            # The inverted logic is used here:
            # 0==auto if active, 1==manual if inactive
            self.dc_mode = int(not self.dc_active)
            
        if self.wct_active is None:
            self.wct_active = self.Qwct > 0
        if self.wct_mode is None:
            # The inverted logic is used here:
            # 0==auto if active, 1==manual if inactive
            self.wct_mode = int(not self.wct_active)
        

    @classmethod
    def from_multiple_sources(cls, dict_src: dict, env_vars: EnvironmentVariables, time: datetime = None) -> "OperationPoint":
        """
        Create an OperationPoint instance from multiple sources

        Parameters:
        - dict_src: Dictionary with the source data
        - env_vars: EnvironmentVariables instance

        Returns:
        - An OperationPoint instance
        """
        # Extract the data
        data = {k: v for k, v in dict_src.items() if k in cls.__dataclass_fields__.keys()}
        data.update(
            {k: v for k,v in asdict(env_vars).items() if k in inspect.signature(cls).parameters}
        )
        # Add the time if provided
        if time is not None:
            data["time"] = time

        return cls(**data)
    
    @classmethod
    def initialize_null(cls, env_vars: EnvironmentVariables = None):
        """Return an instance with all values set to zero/none.
        
        Returns:
            OperationPoint: Instance with all values set to zero/none.
        """
        op_dict = {
            k: 0 if v.default is not None else None 
            for k, v in cls.__dataclass_fields__.items()
        }
        if env_vars is not None:
            op_dict.update({
                k: v for k, v in asdict(env_vars).items()
                if k in cls.__dataclass_fields__.keys()
            })
        return cls(**op_dict)
        

class MatlabOptions(BaseModel):
    # --- Public fields ---
    model_type: Optional[Literal["data", "physical"]] = Field(
        default=None,
        description="Type of model to use (data-driven or physical)",
        example="data",
    )
    
    # DC
    dc_lb: Optional[tuple[float, ...]] = Field(
        default=None,
        description="Lower bounds for dry cooler inputs, same order as dc_var_ids",
        example=[5.06, 10.0, 5.0, 11.0],
    )
    dc_ub: Optional[tuple[float, ...]] = Field(
        default=None,
        description="Upper bounds for dry cooler inputs",
        example=[50.75, 55.0, 24.5, 99.18],
    )
    dc_model_data_path: Optional[Path] = Field(
        default=None,
        description="Path to dry cooler model data file",
        example="/workspaces/SOLhycool/modeling/data/models_data/model_data_dc_fp_pilot_plant_gaussian_cascade.mat",
    )
    dc_ce_coeffs: Optional[tuple[float, ...]] = Field(
        default=None,
        description="Dry cooler electrical consumption coefficients (polynomial). From highest to lowest degree.",
        example=[-0.0002431, 0.04761, -2.2, 48.63, -295.6],
    )
    dc_n_dc: Optional[int] = Field(
        default=None,
        description="Number of dry cooler units in parallel",
        example=1,
    )
    dc_nf: Optional[float] = Field(
        default=None,
        description="Number of fans in the dry cooler (pilot plant has 2, which is the default for the power consumption correlation). If one fan set to 0.5",
        example=1,
        gt=0,
    )
    
    # WCT
    wct_lb: Optional[tuple[float, ...]] = Field(
        default=None,
        description="Lower bounds for wet cooling tower inputs, same order as wct_var_ids",
        example=[0.1, 0.1, 5.0, 5.0, 0.0],
    )
    wct_ub: Optional[tuple[float, ...]] = Field(
        default=None,
        description="Upper bounds for wet cooling tower inputs",
        example=[50.0, 99.99, 55.0, 24.5, 95.0],
    )
    wct_model_data_path: Optional[Path] = Field(
        default=None,
        description="Path to wet cooling tower model data file",
        example="/workspaces/SOLhycool/modeling/data/models_data/model_data_wct_fp_pilot_plant_gaussian_cascade.mat",
    )
    wct_ce_coeffs: Optional[tuple[float, ...]] = Field(
        default=None,
        description="Wet cooling tower electrical consumption coefficients (polynomial). From highest to lowest degree.",
        example=[0.4118, -11.54, 189.4],
    )
    wct_n_wct: Optional[int] = Field(
        default=None,
        description="Number of wet cooling tower units in parallel",
        example=1,
    )
    # Condenser
    condenser_option: Optional[int] = Field(
        default=None,
        description="Condenser option to use",
        example=1,
    )
    condenser_A: Optional[float] = Field(
        default=None,
        description="Condenser heat exchange area",
        example=19.30,
    )
    condenser_deltaTv_cout_min: Optional[float] = Field(
        default=None,
        description="Minimum temperature difference between condenser outlet and vapor temperature",
        example=1.0,
    )
    condenser_n_tb: Optional[int] = Field(
        default=None,
        description="Number of tubes in the condenser",
        example=24,
    )
    # Other
    recirculation_coeffs: Optional[tuple[float, ...]] = Field(
        default=None,
        description="Recirculation pump electrical consumption coefficients (polynomial). From highest to lowest degree.",
        example=[0.1461, 5.763, -38.32, 227.8],
    )
    
    # Miscellaneous
    raise_error_on_invalid_inputs: Optional[bool] = Field(
        default=None,
        description="Whether to raise an error if the inputs are invalid (out of bounds)",
        example=True,
    )
    silence_warnings: Optional[bool] = Field(
        default=None,
        description="Whether to silence warnings from the MATLAB engine",
        example=False,
    )

    # --- Internal fields (excluded from serialization) ---
    _dc_var_ids: ClassVar[tuple[str, ...]] = ("Tamb", "Tdc_in", "qdc", "wdc")
    _wct_var_ids: ClassVar[tuple[str, ...]] = ("Tamb", "HR", "Twct_in", "qwct", "wwct")

    class Config:
        json_encoders = {Path: str}
        extra='allow'
        

    # --- Validation ---
    @model_validator(mode="after")
    def validate_bounds(self):
        def check_pair(lb, ub, names):
            if lb is None or ub is None:
                return
            if len(lb) != len(names) or len(ub) != len(names):
                raise ValueError(
                    f"Expected {len(names)} bounds for {names}, got "
                    f"{len(lb)} lower and {len(ub)} upper."
                )
            for i, (l, u) in enumerate(zip(lb, ub)):
                if l is not None and u is not None and l > u:
                    raise ValueError(
                        f"Lower bound > upper bound for {names[i]}: {l} > {u}"
                    )

        check_pair(self.dc_lb, self.dc_ub, self._dc_var_ids)
        check_pair(self.wct_lb, self.wct_ub, self._wct_var_ids)
        return self

    # --- Methods ---
    # def model_post_init(self, context):
        
    #     # Scale 
    
    def to_matlab_dict(self) -> dict:
        import combined_cooler_model
        import matlab
        out = {}
        for k, v in self.model_dump(exclude_none=True).items():
            if isinstance(v, Path):
                out[k] = str(v)
            elif isinstance(v, tuple):
                out[k] = matlab.double([v])
            else:
                out[k] = v
        return out

    @classmethod
    def from_model_inputs_range(
        cls,
        mir: ModelInputsRange,
        qdc: Optional[tuple[float, float]] = None,
        qwct: Optional[tuple[float, float]] = None,
        other_options: dict = {},
    ) -> "MatlabOptions":

        dc_lb = [None] * len(cls._dc_var_ids)
        dc_ub = [None] * len(cls._dc_var_ids)
        wct_lb = [None] * len(cls._wct_var_ids)
        wct_ub = [None] * len(cls._wct_var_ids)

        for key, value in asdict(mir).items():
            if key in cls._dc_var_ids:
                idx = cls._dc_var_ids.index(key)
                dc_lb[idx], dc_ub[idx] = value
            if key in cls._wct_var_ids:
                idx = cls._wct_var_ids.index(key)
                wct_lb[idx], wct_ub[idx] = value

        dc_lb[cls._dc_var_ids.index("qdc")] = qdc[0] if qdc is not None else mir.qc[0]
        dc_ub[cls._dc_var_ids.index("qdc")] = qdc[1] if qdc is not None else mir.qc[1]
        wct_lb[cls._wct_var_ids.index("qwct")] = qwct[0] if qwct is not None else mir.qc[0]
        wct_ub[cls._wct_var_ids.index("qwct")] = qwct[1] if qwct is not None else mir.qc[1]

        if mir.Rp == (1, 1):
            dc_lb[cls._dc_var_ids.index("qdc")] = 0.0
            dc_ub[cls._dc_var_ids.index("qdc")] = 0.0
            
        elif mir.Rp == (0, 0) and mir.Rs == (0, 0):
            wct_lb[cls._wct_var_ids.index("qwct")] = 0.0
            wct_ub[cls._wct_var_ids.index("qwct")] = 0.0


        return cls(
            dc_lb=tuple(dc_lb),
            dc_ub=tuple(dc_ub),
            wct_lb=tuple(wct_lb),
            wct_ub=tuple(wct_ub),
            **other_options,
        )
        

def is_optional_type(tp) -> bool:
    """Return True if the given type annotation is Optional[...]"""
    return get_origin(tp) is Union and type(None) in get_args(tp)


@dataclass
class Scalator:
    """
    Parameters for scaling the system.
    Ratios are in format: target (nominal or max) value / base (nominal or max) value
    
    target_value = target_nominal_value / base_nominal_value x base_value
    
    
    NOTE: Default values correspond to, target=andasol, base=PSA pilot plant
    Andasol values from Table 7 in:
    
    Asfand, F., Palenzuela, P., Roca, L., Caron, A., Lemarié, C.-A., 
    Gillard, J., Turner, P., & Patchigolla, K. (2020). 
    Thermodynamic Performance and Water Consumption of Hybrid Cooling 
    System Configurations for Concentrated Solar Power Plants. 
    Sustainability, 12(11), 4739. https://doi.org/10.3390/su12114739 
    
    (Vapor temperature needs to be estimated since they say 41ºC but thats unfeasible given the ambient conditions)
    """

    thermal_power: float = 90_000 / 200
    water_consumption: float = 276_840.0 / 156 # Andasol: 76.9 kg/s at Tamb=45ºC, HR=60%, Tv=44ºC
    wct_electricity_consumption: float = 500 / 2.8 # Andasol: 4 fans/tower x 3 towers x 41.5 kw/fan = 498 kw
    dc_electricity_consumption: float = 2500 / 5.8 # 
    recirculation_electricity_consumption: float = 250 / 1.57 # Andasol: using value provided by Villena. Pilot plant: recirculation adjusted to same ratio compared to wct as in andasol
    recirculation_flow_rate: float = 11880 / 24 # Andasol: 11880 m3/h, Pilot plant: 24 m3/h
    
    
    _fix_recirculation: bool = True # TODO: This should not be needed
    _fields_to_update: list[str] = field(default_factory=lambda: [
        "mv", 
        "qc", "qdc", "qwct_s", "qwct_p", "qdc_only", 
        "Qc_released", "Qc_absorbed", "Qc_transfered", "Qdc", "Qwct",
        "Ce_wct", "Ce_dc", "Ce_c", 
        "Cw_wct", "Cw_s1", "Cw_s2",
    ])
    _op_pt_optional_fields: list[str] = field(
        default_factory=lambda: [k for k, v in OperationPoint.__annotations__.items() if is_optional_type(v)]
    )
    
    def scale_operation_point(self, op: OperationPoint) -> OperationPoint:
        """Scales an operation point according to the scaling ratios defined in the dataclass.

        Args:
            op (OperationPoint): Operation point to be scaled.

        Returns:
            OperationPoint: Scaled operation point.
        """
        
        # Procedure: create a new OperationPoint instance with the updated values for
        # self._fields_to_update, leave untouched the others which are not Optional fields.
        # The optional fields should be recalculated using the updated values.
        
        
        op_pt_unchanged_fields = {
            k:v
            for k, v in asdict().items() \
            if k not in self._fields_to_update and k not in self._op_pt_optional_fields
        }
        
        updated_fields = {
            "mv": op.mv * self.thermal_power,
            
            "qc": op.qc * self.recirculation_flow_rate,
            "qdc": op.qdc * self.recirculation_flow_rate,
            "qwct": op.qwct * self.recirculation_flow_rate,
            "qwct_s": op.qwct_s * self.recirculation_flow_rate,
            "qwct_p": op.qwct_p * self.recirculation_flow_rate,
            
            "Qc_released": op.Qc_released * self.thermal_power,
            "Qc_absorbed": op.Qc_absorbed * self.thermal_power,
            "Qc_transfered": op.Qc_transfered * self.thermal_power,
            "Qdc": op.Qdc * self.thermal_power,
            "Qwct": op.Qwct * self.thermal_power,
            
            "Ce_wct": op.Ce_wct * self.wct_electricity_consumption,
            "Ce_dc": op.Ce_dc * self.dc_electricity_consumption,
            "Ce_c": op.Ce_c * self.recirculation_electricity_consumption if not self._fix_recirculation else op.Ce_c * self.recirculation_electricity_consumption * 1000,
            
            "Cw_wct": op.Cw_wct * self.water_consumption,
            "Cw_s1": op.Cw_s1 * self.water_consumption,
            "Cw_s2": op.Cw_s2 * self.water_consumption,
        }
        assert list(updated_fields.keys()) == self._fields_to_update, "Updated fields do not match the fields to update"
        
        return OperationPoint(
            **updated_fields,
            **op_pt_unchanged_fields
        )
        
    def scale_dataframe(self, df_op: pd.DataFrame) -> pd.DataFrame:
        """Scales a dataframe of operation points according to the scaling ratios defined in the dataclass.
        
        NOTE: This method, different from `scale_operation_point`, does not recalculate 
        the optional fields, leaving some inconsistencies in the results.

        Args:
            df_op (pd.DataFrame): Dataframe of operation points to be scaled.

        Returns:
            pd.DataFrame: Scaled dataframe of operation points.
        """
        
        df_scaled = df_op.copy()
        
        for fld in self._fields_to_update:
            if fld in df_scaled.columns:
                if fld == "mv":
                    df_scaled[fld] = df_scaled[fld] * self.thermal_power
                elif fld.startswith("q"): # qc, qdc, qwct_s, qwct_p
                    df_scaled[fld] = df_scaled[fld] * self.recirculation_flow_rate
                elif fld.startswith("Q"): # Qc_released, Qc_absorbed, Qc_transfered, Qdc, Qwct
                    df_scaled[fld] = df_scaled[fld] * self.thermal_power
                elif fld in ["Ce_wct"]:
                    df_scaled[fld] = df_scaled[fld] * self.wct_electricity_consumption
                elif fld in ["Ce_dc"]:
                    df_scaled[fld] = df_scaled[fld] * self.dc_electricity_consumption
                elif fld in ["Ce_c"]:
                    df_scaled[fld] = df_scaled[fld] * self.recirculation_electricity_consumption * 1000 if self._fix_recirculation else df_scaled[fld] * self.recirculation_electricity_consumption
                elif fld.startswith("Cw"): # Cw_wct, Cw_s1, Cw_s2
                    df_scaled[fld] = df_scaled[fld] * self.water_consumption
                else:
                    raise ValueError(f"Field {fld} not recognized for scaling.")
            else:
                print(f"Field {fld} not found in dataframe columns, skipping scaling for this field.")
                
        # Compute wct from series and parallel components
        df_scaled["qwct"] = df_scaled["qwct_p"] + df_scaled["qwct_s"]
                
        # Update costs
        cost_consumption_price: list[tuple[str, str]] = [
            *[(col_id.replace("C", "J"), col_id, "Pe") for col_id in list(df_scaled.columns) if col_id.startswith("Ce_")],
            ("Jw_s1", "Cw_s1", "Pw_s1"),
            ("Jw_s2", "Cw_s2", "Pw_s2"),
        ]
        
        for cost_col, consumption_col, price_col in cost_consumption_price:
            if consumption_col in df_scaled.columns and cost_col in df_scaled.columns:
                df_scaled[cost_col] = df_scaled[consumption_col] * df_scaled[price_col]
        
        df_scaled["Jw"] = df_scaled[["Jw_s1", "Jw_s2"]].sum(axis=1, skipna=True)
        df_scaled["J"] = df_scaled[["Je", "Jw"]].sum(axis=1, skipna=True)
        # Je
        Ce_cols = [col for col in df_scaled.columns if col.startswith("Ce_")]
        df_scaled["Je"] = df_scaled[Ce_cols].sum(axis=1, skipna=True)
        
        
        return df_scaled
    