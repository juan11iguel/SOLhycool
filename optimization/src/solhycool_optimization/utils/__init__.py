import json
import numpy as np
from enum import Enum

#TODO: Move this to phd_utils
class CustomEncoder(json.JSONEncoder):
    """ Custom JSON encoder supporting NumPy arrays and Enums
        Example usage: json.dumps(array, cls=NumpyEncoder)
    """
    def default(self, obj):
        if isinstance(obj, np.ndarray):  # Handle NumPy arrays
            return obj.tolist()
        elif isinstance(obj, Enum):  # Handle Enums
            return obj.value
        return super().default(obj)