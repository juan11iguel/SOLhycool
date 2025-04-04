from dataclasses import dataclass, asdict
from loguru import logger
import copy

import combined_cooler
import matlab

from solhycool_modeling import EnvironmentVariables, OperationPoint, ModelInputsRange

@dataclass
class Parameters:
    condenser_A: float = 18.3
    condenser_option: float = 9.0

class MedProblem:
    env_vars: EnvironmentVariables
    model_options: dict
    
    model_inputs_range: ModelInputsRange = ModelInputsRange()
    
    @property
    def cc_model(self):
        # Lazy loading of cc_model so it's only initialized when used for the first time
        # print("I was called!")
        if not hasattr(self, "_cc_model"):
            self._cc_model = combined_cooler.initialize()
            # print("I was initialized!")
        return self._cc_model
    
    def __deepcopy__(self, memo):
        """Custom deepcopy to ensure `_cc_model` is reinitialized."""
        copied_obj = self.__class__.__new__(self.__class__)
        memo[id(self)] = copied_obj  # Prevent infinite recursion
        
        keys_to_not_copy = ["_cc_model"]
        [setattr(copied_obj, key, copy.deepcopy(value, memo)) for key, value in self.__dict__.items() if key not in keys_to_not_copy]

        return copied_obj
    
    def __getstate__(self):
        """Remove non-picklable attributes before pickling"""
        state = self.__dict__.copy()
        if "_cc_model" in state:
            del state["_cc_model"]  # Remove the MATLAB object before pickling
        return state
    
    def __init__(self, env_vars: EnvironmentVariables, parameters: Parameters = Parameters()):
        
        self.env_vars = env_vars
        
        # Validate range of inputs
        var_ids = ["Tamb", "HR"]
        for var_id in var_ids:
            value = getattr(env_vars, var_id)
            bounds = getattr(self.model_inputs_range, var_id)
            if value > bounds[1] or value < bounds[0]:
                new_value = max(min(bounds[1], value), bounds[0])
                logger.warning(f"{var_id}={value} outside range: {bounds}, setting to: {new_value}")
                setattr(env_vars, var_id, new_value)
        
        parameters_ = self.cc_model.default_parameters()
        parameters_.update(asdict(parameters))
        
        self.model_options = {
            'model_type': "data",
            'parameters': parameters_,
            'silence_warnings': True, 
        }
    
    def evaluate(self, qc: float, Rp: float, Rs: float, wdc: float = None) -> OperationPoint:
        
        # if wdc is not None:
        _, _, detailed = self.cc_model.fans_calculator(
            self.env_vars.Tamb, 
            self.env_vars.HR, 
            self.env_vars.mv, 
            qc, 
            Rp, 
            Rs, 
            self.env_vars.Tv, 
            self.model_options, 
            nargout=3
        )
        # else:
        #     _, _, detailed, valid = cc_model.evaluate_operation(
        #         self.env_vars.Tamb, 
        #         self.env_vars.HR, 
        #         self.env_vars.mv, 
        #         qc, 
        #         Rp, 
        #         Rs, 
        #         wdc, 
        #         self.env_vars.Tv,
        #         self.model_options,
        #         nargout=4
        #     )
        #     if not valid:
        #         logger.warning("Invalid operation point")
        #         return None

        return OperationPoint.from_multiple_sources(detailed, env_vars=self.env_vars)