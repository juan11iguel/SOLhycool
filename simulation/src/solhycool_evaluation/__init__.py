import datetime as dt
from enum import Enum
from dataclasses import dataclass

PeriodType = list[tuple[dt.time, dt.time]]
OpValuesType = list[float]

class OperationValues(Enum):
    OFF = 0.0
    PARTIAL = 0.6
    PEAK = 1.0

@dataclass
class OperationPlan:
    period: PeriodType
    values: OpValuesType
    
    def __post_init__(self):
        assert len(self.period) == len(self.values), "Period and values must have the same length"