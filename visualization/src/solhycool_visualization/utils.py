from pathlib import Path
import hjson
import pandas as pd

from solhycool_optimization import HorizonResults

def generate_visualizations(
    day_results: HorizonResults, 
    output_path: Path,
    plot_config_path = Path("/workspaces/SOLhycool/data/plot_config_day_horizon.hjson")
) -> None:
    
    from solhycool_visualization.objects import HorizonResultsVisualizer
    
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
    
def adapt_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Make some variables that are filled traces NaN to 0 so gaps are not filled
    for var_id in ["Qc_released", "Vavail", "Jw_s1", "Jw_s2", "Je_dc", "Je_wct", "Je_c", "Qdc", "Qwct"]:
        if var_id in df.columns:
            df.loc[df[var_id].isna()] = 0
        
    for var_id in ["wdc", "wwct"]:
        df.loc[df[var_id] < 1e-3, var_id] = None
        
    for system_id in ["dc", "wct"]:
        df.loc[ df[f"T{system_id}_in"] - df[f"T{system_id}_out"] < 0.5 , [f"T{system_id}_out", f"T{system_id}_in"]] = None
        
    for var_id in list(df.columns):
        if var_id.startswith("T") or var_id in ["HR"]:
            df.loc[ df[var_id] < 1e-3 , var_id] = None
    
    return df
                