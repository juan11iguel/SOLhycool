from dataclasses import dataclass
from loguru import logger
import copy

import combined_cooler
import matlab

from solhycool_modeling import EnvironmentVariables, OperationPoint, ModelInputsRange

@dataclass
class MedProblem:
    env_vars: EnvironmentVariables
    
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
    
    def __init__(self, ):
        pass
    
    def evaluate(self, ):
        pass