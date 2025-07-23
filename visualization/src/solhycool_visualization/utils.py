from pathlib import Path
import hjson
from solhycool_optimization import DayResults
from solhycool_visualization.objects import HorizonResultsVisualizer

def generate_visualizations(
    day_results: DayResults, 
    output_path: Path,
    plot_config_path = Path("/workspaces/SOLhycool/data/plot_config_day_horizon.hjson")
) -> None:
    
    # Load plot configuration
    plot_config = hjson.loads(plot_config_path.read_text())
    
    # Create visualizer and generate figures
    visualizer = HorizonResultsVisualizer(
        results_plot_config=plot_config,
        day_results=day_results,
    )
    
    # Generate all visualization figures
    visualizer.generate_all(
        output_path=output_path,
        formats=["png", "html"]
    )