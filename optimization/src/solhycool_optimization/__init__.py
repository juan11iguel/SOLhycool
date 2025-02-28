from dataclasses import dataclass


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
    qc: float
    Rp: float
    Rs: float
    wdc: float
    wwct: float
    
