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

    
def add_aggretated_variables(
    df: pd.DataFrame, 
    ev: Optional[EnvironmentVariables] = None, 
    scada_to_model_units: bool = True, 
    eval_times: list[datetime] | list[str] | None = None
) -> pd.DataFrame:
    """
    Add aggregated variables to the DataFrame.
    Mainly: thermal powers, costs

    Args:
        df: A pandas DataFrame containing the timeseries data.

    Returns:
        A DataFrame with additional aggregated variables.
    """
    
    dt_formats_to_try = ["%Y%m%d_%H%M", "%Y%m%dT%H%M", "%Y%m%d %H%M"]
    
    df = df.copy()
    
    if eval_times is not None:
        df["optim_eval"] = 0  # default value
        if isinstance(eval_times[0], str):
            for fmt in dt_formats_to_try:
                try:
                    event_times = pd.to_datetime(eval_times, format=fmt, utc=True)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"None of the provided formats matched: {dt_formats_to_try}")
        # Set 'event' to 1 for each 5-minute window starting at each event time
        for t in event_times:
            df.loc[t : t + pd.Timedelta(minutes=4), "optim_eval"] = 1

    # Convert units
    if scada_to_model_units:
        df["Cw"] = df["Cw"].ewm(alpha=0.04, adjust=False).mean() * 60 # Convert l/min to l/h
    
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
        df["qwct_s"] = df["qdc"]*df["Rs"]
        
    if ev is not None and ev.Pe is not None:
        df["Pe"] = ev.Pe
        # calculate the associated cost of operation
        # TODO: Create a function that reads the coefficients and uses np.polyval
        # if ev.Pe is not None:
        #     df["Je"] = ev.Pe * df[""]
    if ev is not None and ev.Pw_s1 is not None and ev.Pw_s2 is not None:
        df["Pw_s1"] = ev.Pw_s1
        df["Pw_s2"] = ev.Pw_s2
    
    # calculate the available water evolution
    if ev is not None and ev.Vavail is not None:
        elapsed_time_between_steps = pd.Series(np.diff(df.index)).dt.total_seconds().div(3600).tolist() # hours
        Cw_s1 = []
        Cw_s2 = []
        Jw_s1 = []
        Jw_s2 = []
        
        # From the first non-NaN index to the end of the DataFrame
        i0 = np.where(~np.isnan(ev.Vavail))[0][0] # Initial available water volume
        Vavail = [ev.Vavail[i0]] 
        for i in range(i0, len(df)):
            ds = df.iloc[i]
            elapsed_time = elapsed_time_between_steps[i] if i < len(elapsed_time_between_steps) else 1e-3
            
            Cw_s1.append( min( ds["Cw"]*elapsed_time, Vavail[-1]*1e3 ) / elapsed_time )
            Cw_s2.append( ds["Cw"] - Cw_s1[-1] )
            Vavail.append(
                Vavail[-1]-(Cw_s1[-1]*1e-3*elapsed_time)
            )
            if ev.Pw_s1 is not None and ev.Pw_s2 is not None:
                Pw_s1 = ev.Pw_s1 if np.ndim(ev.Pw_s1) == 0 else ev.Pw_s1[i]
                Pw_s2 = ev.Pw_s2 if np.ndim(ev.Pw_s2) == 0 else ev.Pw_s2[i]
            
                Jw_s1.append( Cw_s1[-1] * Pw_s1 )
                Jw_s2.append( Cw_s2[-1] * Pw_s2 )
            
            i += 1

        # Left pad with nans
        nans_to_add = np.array([np.nan] * (len(df) - len(Cw_s1)))
        df["Cw_s1"] = np.concatenate((nans_to_add, Cw_s1))
        df["Cw_s2"] = np.concatenate((nans_to_add, Cw_s2))
        df["Jw_s1"] = np.concatenate((nans_to_add, Jw_s1)) if Jw_s1 else np.array([np.nan] * len(df))
        df["Jw_s2"] = np.concatenate((nans_to_add, Jw_s2)) if Jw_s2 else np.array([np.nan] * len(df))
        df["Vavail"] = np.concatenate((nans_to_add, Vavail[:-1])) # Remove the last value as it is not needed

    return df