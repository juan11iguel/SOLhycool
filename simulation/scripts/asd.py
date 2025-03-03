from pathlib import Path
from dataclasses import asdict
import numpy as np
import pandas as pd
# from IPython.display import SVG
from loguru import logger
import pygmo as pg
import hjson

import combined_cooler_model
from solhycool_modeling import OperationPoint

from solhycool_modeling import EnvironmentVariables
from solhycool_optimization.problems.horizon import WctRestrictedProblem as Problem
from solhycool_optimization.utils.evaluation import optimize

# Visualization packages
from solhycool_optimization.visualization import plot_obj_scape_comp_1d
# from solhycool_visualization.operation import plot_hydraulic_distribution
# from solhycool_visualization.diagrams import WascopStateVisualizer
from solhycool_optimization.visualization import visualize_solutions_distribution
from solhycool_visualization.operation import plot_results

logger.disable("phd_visualizations")

data_path: Path = Path("../../data")
env_path: Path = data_path / "datasets/environment_data_20220101_20241231.h5"
base_output_path: Path = Path("../results")
diagram_path: Path = Path("/workspaces/SOLhycool/data/assets/base_diagram.svg")
date_span: tuple[str, str] = ("20220101", "20221231")

cc_model = combined_cooler_model.initialize()
np.set_printoptions(precision=2)