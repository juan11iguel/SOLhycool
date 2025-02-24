from dataclasses import dataclass, field



from dataclasses import dataclass, field
from typing import Optional

@dataclass
class OperationPoint:
    # Ambient conditions
    Tamb: float = field(metadata={"description": "Ambient temperature", "units": "ºC"})
    HR: float = field(metadata={"description": "Relative humidity", "units": "%"})

    # Load conditions
    mv: float = field(metadata={"description": "Vapor mass flow rate", "units": "kg/s"})
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

    # Combined cooler and totals
    Ce: float = field(metadata={"description": "Total electrical consumption", "units": "kWe"})
    Cw: float = field(metadata={"description": "Total water consumption", "units": "l/h"})
    qcc: float = field(metadata={"description": "Combined cooler flow rate", "units": "m³/h"})
    Tcc_out: float = field(metadata={"description": "Combined cooler outlet temperature", "units": "ºC"})

    # Optional fields
    qdc_only: Optional[float] = field(default=None, metadata={"description": "DC only cooling flow rate", "units": "m³/h"})
    Tcc_in: Optional[float] = field(default=None, metadata={"description": "Combined cooler inlet temperature", "units": "ºC"})
    Ce_cc: Optional[float] = field(default=None, metadata={"description": "Combined cooler electrical consumption", "units": "kWe"})
    Cw_cc: Optional[float] = field(default=None, metadata={"description": "Combined cooler water consumption", "units": "l/h"})
    Qcc: Optional[float] = field(default=None, metadata={"description": "Combined cooler heat transfer", "units": "kWth"})

    # limits: OperationLimits = field(default=OperationLimits())
    
    def __post_init__(self) -> None:
        
        # Fill not provided computable values
        if self.Tcc_in is None:
            self.Tcc_in = self.Tc_out
            
        if self.Ce_cc is None:
            self.Ce_cc = self.Ce_dc + self.Ce_wct
            
        if self.Cw_cc is None:
            self.Cw_cc = self.Cw_wct
            
        if self.Qcc is None:
            self.Qcc = self.Qdc + self.Qwct
            
        if self.qdc_only is None:
            self.qdc_only = self.qdc * (1-self.Rs)
        