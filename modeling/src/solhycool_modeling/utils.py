from typing import Literal, Optional, Iterable
from datetime import datetime
import numpy as np
import pandas as pd
from iapws import IAPWS97 as w_props

from solhycool_modeling import EnvironmentVariables


def dump_in_span(vars_dict: dict, span: tuple[int, int] | tuple[datetime, datetime], return_format: Literal["values", "series"] = "values") -> dict:
        """
        Dump variables within a given span.

        Args:
            vars_dict: A dictionary containing the variables to dump.
            span: A tuple representing the range (indices or datetimes).
            return_format: Format of the returned values ("values" or "series").

        Returns:
            A new dictionary containing the filtered data.
        """
        if isinstance(span[0], datetime):
            # Ensure all attributes are pd.Series for datetime filtering
            for name, value in vars_dict.items():
                if not isinstance(value, pd.Series) and value is not None:
                    raise TypeError(f"All attributes must be pd.Series for datetime indexing: {name} is {type(value)}")

            # Extract the range
            dt_start, dt_end = span
            span_vars_dict = {
                name: value[(value.index >= dt_start) & (value.index < dt_end)]
                for name, value in vars_dict.items() if value is not None
            }
        else:
            # Assume numeric indices
            idx_start, idx_end = span
            span_vars_dict = {
                name: value[idx_start:idx_end]
                if isinstance(value, (pd.Series, np.ndarray)) else value
                for name, value in vars_dict.items()
            }

        if return_format == "values":
            span_vars_dict = {name: value.values if isinstance(value, pd.Series) else value for name, value in span_vars_dict.items()}

        return span_vars_dict
    
def flows_to_ratios(qc: float, qdc: float, qwct: float) -> tuple[float, float]:
    """
    Convert flow values to Rp and Rs ratios.

    Parameters:
    - qc: float, must be > 0
    - qdc: float, must be >= 0
    - qwct: float, must be >= 0

    Returns:
    - Rp: float
    - Rs: float
    """
    # Handle NaN values
    if pd.isna(qc) or pd.isna(qdc) or pd.isna(qwct):
        return 0.0, 0.0
    
    # Convert to float to handle potential numpy types
    qc = float(qc)
    qdc = float(qdc)
    qwct = float(qwct)

    # Handle edge case where qc is zero or negative
    if qc <= 0:
        return 0.0, 0.0
    
    # Validate inputs with more lenient handling
    if qdc < 0:
        qdc = 0.0  # Clamp negative values to zero
    if qwct < 0:
        qwct = 0.0  # Clamp negative values to zero

    # Calculate Rp with bounds checking
    Rp = max(0.0, min(1.0, round(1 - qdc / qc, 3)))

    # Calculate Rs with robust handling
    if qdc < 1e-6:  # Very small threshold to avoid floating point issues
        Rs = 0.0
    else:
        denominator = 1 - Rp
        if abs(denominator) < 1e-10:  # Avoid division by very small numbers
            Rs = 0.0
        else:
            numerator = qwct / qc - Rp
            Rs = max(0.0, min(1.0, round(numerator / denominator, 3)))

    return Rp, Rs

    
def add_aggretated_variables(df: pd.DataFrame, ev: Optional[EnvironmentVariables] = None) -> pd.DataFrame:
    """
    Add aggregated variables to the DataFrame.
    Mainly: thermal powers, costs

    Args:
        df: A pandas DataFrame containing the timeseries data.

    Returns:
        A DataFrame with additional aggregated variables.
    """
    
    # Calculate thermal powers
    # w_props(T=df["Tdc_in"] + 273.15, P=1.6).cp
    df["Qc_released"] = df["mv"] * (df["Tv"] + 273.15).apply(lambda T: w_props(T=T, x=1).h - w_props(T=T, x=0).h) / 3600  # kWth
    df["Qc_absorbed"] = df["qc"] / 3.6 * 4.18 * (df["Tc_out"] - df["Tc_in"])  # m³/h -> kg/s * [kJ/kg·K] * K => kWth
    df["Qdc"] = df["qdc"] / 3.6 * 4.18 * (df["Tdc_in"] - df["Tdc_out"])  # m³/h -> kg/s * [kJ/kg·K] * K => kWth
    df["Qwct"] = df["qwct"] / 3.6 * 4.18 * (df["Twct_in"] - df["Twct_out"])  # m³/h -> kg/s * [kJ/kg·K] * K => kWth
    
    # Estimate state variables if not logged
    df["dc_active"] = df["Qdc"] > 5 # kW, Threshold to consider the DC active
    df["wct_active"] = df["Qwct"] > 5 # kW, Threshold to consider the WCT active
    
    # Calculate the hydraulic distribution with error handling
    try:
        ratios_result = df.apply(lambda row: flows_to_ratios(row["qc"], row["qdc"], row["qwct"]), axis=1)
        df["Rp"], df["Rs"] = zip(*ratios_result)
    except Exception as e:
        # If there's any error, fall back to safe defaults
        print(f"Warning: Error calculating hydraulic ratios: {e}")
        df["Rp"] = 0.0
        df["Rs"] = 0.0
    
    # Add qwct_s
    if "qwct_s" not in df.columns:
        df["qwct_s"] = df["qwct"] + df["qdc"]*df["Rs"]
    
    # If environment variables are provided
    if ev is not None:
        # calculate the associated cost of operation
        if ev.Pe is not None:
            ...
        if ev.Cw is not None:
            ...
        
        # calculate the available water evolution
        if ev.Vavail is not None:
            elapsed_time_between_steps = pd.Series(np.diff(df.index)).dt.total_seconds().div(3600).tolist()
            Vavail = [ev.Vavail if ev.Vavail is not Iterable else ev.Vavail[0]]
            for elapsed_time, Cw in zip(elapsed_time_between_steps, df["Cw"].values):
                Vavail.append(
                    max(0, Vavail[-1] - Cw * elapsed_time)
                )
            df["Vavail"] = Vavail
            
    return df