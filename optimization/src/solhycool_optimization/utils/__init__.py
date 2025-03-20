import json
import numpy as np
from enum import Enum
from dataclasses import is_dataclass, asdict

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
        elif is_dataclass(obj): # Handle dataclasses
            return asdict(obj)
        elif isinstance(obj, complex):  # Handle complex numbers
            return {"__complex__": True, "real": obj.real, "imag": obj.imag}
        return super().default(obj)