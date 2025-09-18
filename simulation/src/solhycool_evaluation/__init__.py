import datetime as dt
from enum import Enum
from dataclasses import dataclass
from pydantic import Field, model_validator

# Some extra imports just to be able to import everything from a single module
from solhycool_modeling import ModelInputsRange, MatlabOptions
from solhycool_optimization import EvaluationConfig, ValuesDecisionVariables, AlgoParamsHorizon


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
       
class SimulationConfig(EvaluationConfig):
    
    env_id: str = Field(..., description="ID of the environment to use (its filename)", example="environment_data_andasol_20220101_20241231")
