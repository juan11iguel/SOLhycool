import numpy as np
import pandas as pd

def process_dfs_for_exp_visualization(df_exp: pd.DataFrame, df_opt: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Process the experimental and optimization DataFrames for visualization.
    
    Args:
        df_exp: Experimental DataFrame.
        df_opt: Optimization DataFrame.
        
    Returns:
        Tuple of processed DataFrames (df_exp_plot, df_opt_plot).
    """
    
    # Make NaNs component values when the component is not active

    df_exp_plot = df_exp.copy()
    df_opt_plot = df_opt.copy()

    # Make NaNs component values when the component is not active
    # TODO: This should be a function
    df_exp_plot = df_exp_plot.loc[df_opt_plot.first_valid_index():] # Start plot from the first operation set by optimization result
    df_opt_plot = df_opt_plot.loc[df_exp_plot.first_valid_index():] # Start plot from the first operation set by experimental data
    df_exp_plot.loc[df_exp_plot["Qdc"] < 15, ["Tdc_in", "Tdc_out", "wdc", "Tdc_out_sp"]] = np.nan
    df_exp_plot.loc[df_exp_plot["Qwct"] < 15, ["Twct_in", "Twct_out", "wwct", "Twct_out_sp", ]] = np.nan
    df_opt_plot.loc[(df_exp_plot["Qdc"] < 15).values, ["Tdc_in", "Tdc_out", "wdc"]] = np.nan
    df_opt_plot.loc[(df_exp_plot["Qwct"] < 15).values, ["Twct_in", "Twct_out", "wwct"]] = np.nan
    
    return df_exp_plot, df_opt_plot