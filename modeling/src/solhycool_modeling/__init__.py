from dataclasses import asdict, dataclass, field
from collections.abc import Iterable
from datetime import datetime
from typing import Literal, Optional
import inspect
import numpy as np
import pandas as pd
from iapws import IAPWS97 as w_props

import combined_cooler_model # Always import combined_cooler_model before importing matlab
import matlab

from solhycool_modeling.utils import dump_in_span

@dataclass
class ModelInputsRange:
    """ Real decision variables box bounds, as in: (lower bound, upper bound)"""
    qc: tuple[float, float] = (5.2211, 24.1543)
    Rp: tuple[float, float] = (0., 1.)
    Rs: tuple[float, float] = (0., 1.)
    wdc: tuple[float, float] = (11.0, 99.1800)
    wwct: tuple[float, float] = (0., 93.4161)
    Tamb: tuple[float, float] = (9.06, 38.75)
    HR: tuple[float, float] = (10.33, 89.25)
    Tdc_in: tuple[float, float] = (33.16, 41.92)
    Twct_in: tuple[float, float] = (31.17, 40.94)
    
    
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
    Q: float | np.ndarray[float] # Thermal power, kW

    # Costs
    Pe: float | np.ndarray[float] # Cost of electricity, €/kWhe
    Pw: float | np.ndarray[float] = None # Cost of water, €/l
    Pw_s1: float | np.ndarray[float] = None # Cost of water from source 1, €/l
    Pw_s2: float | np.ndarray[float] = None # Cost of water from source 2, €/l
    
    Vavail: float | np.ndarray[float] = None # Available volume of water, m³
    deltaV: float | np.ndarray[float] = None # Variation of available volume of water, m³/h

    # Thermal load (optional)
    mv: float | np.ndarray[float] = None # Vapor mass flow rate, kg/h!!

    def __post_init__(self) -> None:
        if self.mv is not None:
            return
        
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
            HR=df["HR_pct"].values,
            Tamb=df["Tamb_C"].values,
            Q=df["Q_kW"].values,
            Tv=df["Tv_C"].values,
            mv=df["mv_kgh"] if "mv_kgh" in df else None, 
            Pe=df["Ce_spot_market_price_eur_kWh"].values,
            Pw=df["water_price_morocco_eur_l"].values if "water_price_morocco_eur_l" in df else None,
            Pw_s1=df["water_price_morocco_eur_l"].values if "water_price_morocco_eur_l" in df else None,
            Pw_s2=df["water_price_morocco_alternative_eur_l"].values if "water_price_morocco_alternative_eur_l" in df else None,
            Vavail=df["Vavail_m3"].values if "Vavail_m3" in df else None,
            deltaV=df["deltaV_m3_h"].values if "deltaV_m3_h" in df else None 
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
            HR=ds["HR_pct"],
            Tamb=ds["Tamb_C"],
            Q=ds["Q_kW"],
            Tv=ds["Tv_C"],
            mv=ds["mv_kgh"] if "mv_kgh" in ds else None, 
            Pe=ds["Ce_spot_market_price_eur_kWh"],
            Pw=ds["water_price_morocco_eur_l"] if "water_price_morocco_eur_l" in ds else None,
            Pw_s1=ds["water_price_morocco_eur_l"] if "water_price_morocco_eur_l" in ds else None,
            Pw_s2=ds["water_price_morocco_alternative_eur_l"] if "water_price_morocco_alternative_eur_l" in ds else None,
            Vavail=ds["Vavail_m3"] if "Vavail_m3" in ds else None,
            deltaV=ds["deltaV_m3_h"] if "deltaV_m3_h" in ds else None 
        )
        
    def reduce_load(self, reduction_factor: float = 0.5) -> None:
        
        self.Q = self.Q * reduction_factor
        self.mv = self.mv * reduction_factor
        

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

        vars_dict = dump_in_span(vars_dict=asdict(self), span=span, return_format="values")
        
        return EnvironmentVariables(**vars_dict)

    def to_matlab(self) -> "EnvironmentVariables":
        """ Convert all attributes to matlab.double """
        
        return EnvironmentVariables(**{k: matlab.double(v) for k, v in asdict(self).items() if v is not None})

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
        

    @classmethod
    def from_multiple_sources(cls, dict_src: dict, env_vars: EnvironmentVariables) -> "OperationPoint":
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

        return cls(**data)
            
