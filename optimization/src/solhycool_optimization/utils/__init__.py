from typing import Literal
import json
import numpy as np
from enum import Enum
from dataclasses import is_dataclass, asdict


#TODO: Move this to phd_utils
def extract_prefix(text: str) -> str:
    return "_".join(text.split("_pop")[0].split("_"))

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
    
    
def pareto_front_indices(points: np.ndarray[float], objective: Literal["maximize", "minimize"] = "minimize") -> np.ndarray[int]:
    """
    Computes the Pareto front for a set of 2D points with a specified objective.
    
    Parameters:
        points (np.ndarray): A (N, 2) array where each row is a point (x, y).
        objective (str): "minimize" (default) or "maximize".
    
    Returns:
        np.ndarray: Indices of the Pareto-optimal points.
        
    Example:
        points = np.array([[1, 2], [2, 1], [2, 3], [3, 2], [3, 4], [4, 3]])

        pareto_min = pareto_front_indices(points, "minimize")
        print("Pareto front (minimize):", pareto_min)

        pareto_max = pareto_front_indices(points, "maximize")
        print("Pareto front (maximize):", pareto_max)
    """
    if objective not in {"minimize", "maximize"}:
        raise ValueError("Objective must be 'minimize' or 'maximize'")
    
    # Determine sorting order based on objective
    x_order = points[:, 0]  # Always sort x in ascending order
    y_order = points[:, 1] if objective == "minimize" else -points[:, 1]
    
    # Sort points by x (ascending), then by y based on objective
    sorted_indices = np.lexsort((y_order, x_order))
    sorted_points = points[sorted_indices]
    
    pareto_front = []
    best_y = np.inf if objective == "minimize" else -np.inf  # Track best y value
    
    for i, (_, y) in enumerate(sorted_points):
        if (objective == "minimize" and y < best_y) or (objective == "maximize" and y > best_y):
            pareto_front.append(sorted_indices[i])
            best_y = y  # Update the best y
    
    return np.array(pareto_front)