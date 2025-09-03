from pathlib import Path
import pandas as pd
from loguru import logger
import pytz
import calendar

from solhycool_evaluation import OperationPlan, OperationValues

def preprocess_meteonorm_txt_data(txt_file_path: Path) -> pd.DataFrame:
    """
    Preprocesses a Meteonorm text file and converts it into a pandas DataFrame.
    This function reads a Meteonorm text file, processes the data by combining date columns into a single datetime column,
    sets the datetime column as the index, renames specific columns, and saves the pre-processed data to a CSV file.
    Args:
        txt_file_path (Path): The path to the Meteonorm text file.
    Returns:
        pd.DataFrame: A pandas DataFrame containing the pre-processed data with the datetime index and renamed columns.
    """
    
    env_df = pd.read_csv(txt_file_path, sep="\t", skiprows=2, encoding="latin1")
    # display(env_df)

    # Combine the date columns into a single datetime column
    env_df[" h"] = env_df[" h"] - 1
    env_df['time'] = pd.to_datetime(env_df[[' y', ' m', ' dm', ' h']].astype(str).agg('-'.join, axis=1) + ':00', format='%Y-%m-%d-%H:%M')
    env_df['time'] = env_df['time'].dt.tz_localize('UTC')
    # Set the datetime column as the index
    env_df.set_index('time', inplace=True)
    # Drop the original date columns if no longer needed
    env_df.drop(columns=[' y', ' m', ' dm', ' h'], inplace=True)

    # Rename the columns
    new_columns = {
        " Ta": "Tamb_C",
        " RH": "HR_pct",
        "RR": "precip_mm"
    }

    env_df = env_df.rename(columns=new_columns)
    # display(env_df)

    # Save the pre-processed data
    env_df.to_csv(txt_file_path.with_suffix(".csv"), index=True)
    env_df.to_hdf(txt_file_path.with_suffix(".h5"), key="data")
    
    logger.info(f"Pre-processed data saved to {txt_file_path.with_suffix('.csv')} and {txt_file_path.with_suffix('.h5').name}")
    
    return pd.read_csv(txt_file_path.with_suffix(".csv"), index_col=0)


def repeat_and_align_index(
    df: pd.DataFrame | pd.Series, 
    new_index: pd.DatetimeIndex, 
    year_range: tuple[int, int]
) -> pd.DataFrame:
    """
    Expand df by repeating its index for each year in the given range,
    then align it with df's index using forward and backward fill.

    Args:
        df (pd.DataFrame): The input dataframe with one year of data.
        df (pd.DataFrame): The reference dataframe for alignment.
        year_range (Tuple[int, int]): The start and end year (inclusive).

    Returns:
        pd.DataFrame: The expanded and aligned dataframe.
    """
    year_start, year_end = year_range
    
    if isinstance(df, pd.Series):
        df = df.to_frame()
    
    # Ensure the index is timezone-aware and set to UTC
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    
    # Generate repeated data for each year in the range
    
    # Generate repeated data for each year in the range
    dfs = [
        df.copy().set_index(
            df.index.map(lambda dt: dt.replace(year=year))
        )
        for year in range(year_start, year_end + 1)
    ]
    df = pd.concat(dfs)
    
    # Adapt provided data index to generated data index
    start_idx = new_index.get_loc(df.index[0])
    df = (
        df.set_index(new_index[start_idx : start_idx + len(df.index)])
        .reindex(new_index)
        .ffill()
        .bfill()
    )
    
    return df


def generate_operation_value(timestamp: pd.Timestamp, operation_plan: OperationPlan) -> float:
    """
    Generate operation value for a given timestamp based on the operation plan.
    
    Args:
        timestamp: pandas timestamp with timezone info
        operation_plan: OperationPlan object containing periods and values
    
    Returns:
        float: Operation value for the given timestamp
    """
    time_of_day = timestamp.time()
    
    for i, (start_time, end_time) in enumerate(operation_plan.period):
        # Handle overnight periods (e.g., 21:30 to 07:00)
        if start_time > end_time:
            if time_of_day >= start_time or time_of_day < end_time:
                return operation_plan.values[i]
        else:
            if start_time <= time_of_day < end_time:
                return operation_plan.values[i]
    
    # Default case (shouldn't happen if periods cover full day)
    return 0.0

def generate_annual_operation_table(
    op_plans: list[OperationPlan],
    year: int = 2025,
    freq: str = '10m',
    timezone: str = 'Europe/Madrid',
    extra_cols: bool = False
) -> pd.DataFrame:
    """
    Generate annual operation table with multiple operation plans.
    
    Example usage:
    # Generate the annual operation table
    op_plans: list[OperationPlan] = [
        OperationPlan(periods, [ov.PEAK.value, ov.OFF.value, ov.PEAK.value, ov.PARTIAL.value]),
        OperationPlan(periods, [ov.PEAK.value, ov.OFF.value, ov.PEAK.value, ov.PEAK.value]),
        OperationPlan(periods, [ov.PEAK.value, ov.PARTIAL.value, ov.PEAK.value, ov.PEAK.value]),
        OperationPlan(periods, [ov.PEAK.value, ov.PEAK.value, ov.PEAK.value, ov.PEAK.value]),
    ]
    
    # You can change the frequency as needed: 'h' (hourly), '30min' (30 min), '15min' (15 min), etc.
    annual_table = generate_annual_operation_table(op_plans, year=2025, freq='10min', extra_cols=False)
    
    Args:
        year: Year for which to generate the table
        freq: Pandas frequency string (e.g., 'H' for hourly, '30T' for 30 minutes)
        timezone: Timezone string (default: 'Europe/Madrid')
    
    Returns:
        DataFrame with datetime index and columns for each operation plan
    """
    # Create timezone object
    tz = pytz.timezone(timezone)
    
    # Create date range for the entire year
    start_date = pd.Timestamp(f'{year}-01-01', tz=tz)
    end_date = pd.Timestamp(f'{year+1}-01-01', tz=tz)
    
    # Generate datetime index with specified frequency
    datetime_index = pd.date_range(
        start=start_date,
        end=end_date,
        freq=freq,
        inclusive='left',  # Exclude the end date
        tz=tz
    )
    
    # Create DataFrame
    df = pd.DataFrame(index=datetime_index)
    
    # Add columns for each operation plan
    for i, op_plan in enumerate(op_plans):
        column_name = f'operation_plan_{i+1}'
        df[column_name] = [generate_operation_value(ts, op_plan) for ts in datetime_index]
    
    # Add additional useful columns
    if extra_cols:
        df['date'] = df.index.date
        df['time'] = df.index.time
        df['day_of_year'] = df.index.dayofyear
        df['weekday'] = df.index.day_name()
        
    # Display basic info about the table
    print(f"Table shape: {df.shape}")
    print(f"Date range: {df.index.min()} to {df.index.max()}")
    print(f"Frequency: {df.index.freq}")
    print("\nColumn names:")
    print(df.columns.tolist())
    
    return df

def generate_operation_rules_table(
    op_plans: list[OperationPlan],
    year: int = 2025,
) -> dict[str, pd.DataFrame]:
    """
    Generate period-based operation rules table for each operation plan.
    
    Instead of generating rows at fixed frequency intervals, this function generates
    one row per period per day, directly representing the operation periods and values.
    
    The output format for each operation plan is:
    - Column 1: Month (1-12)
    - Column 2: Day (1-31)
    - Column 3: Start hour (0-23.99)
    - Column 4: End hour (0-23.99)
    - Column 5: Operation value
    
    Example output:
    
    month | day | start_hour | end_hour | value
    ------|-----|------------|----------|------
      6   | 20  |    9.0     |   12.0   | 0.5
      6   | 20  |   12.0     |   17.0   | 0.9
      6   | 20  |   17.0     |   18.0   | 0.7
      1   | 15  |   10.0     |   15.0   | 0.6
    
    Args:
        op_plans: List of OperationPlan objects
        year: Year for which to generate the rules
        timezone: Timezone string (default: 'Europe/Madrid')
    
    Returns:
        Dictionary with operation plan names as keys and DataFrames as values.
        Each DataFrame has columns: ['month', 'day', 'start_hour', 'end_hour', 'value']
    """
        
    results = {}
    
    for plan_idx, op_plan in enumerate(op_plans):
        rules_data = []
        
        # Iterate through each day of the year
        for month in range(1, 13):
            # Get number of days in this month
            days_in_month = calendar.monthrange(year, month)[1]
            
            for day in range(1, days_in_month + 1):
                # Convert operation plan periods to hour-based rules
                for i, (start_time, end_time) in enumerate(op_plan.period):
                    start_hour = start_time.hour + start_time.minute / 60.0
                    end_hour = end_time.hour + end_time.minute / 60.0
                    operation_value = op_plan.values[i]
                    
                    # Handle overnight periods (e.g., 21:30 to 07:00)
                    if start_time > end_time:
                        # Split into two rules: start_time to 24:00 and 00:00 to end_time
                        # First rule: start_time to midnight
                        rules_data.append([
                            month, day, start_hour, 24.0, operation_value
                        ])
                        # Second rule: midnight to end_time (next day)
                        next_day = day + 1
                        next_month = month
                        if next_day > days_in_month:
                            next_day = 1
                            next_month = month + 1 if month < 12 else 1
                        rules_data.append([
                            next_month, next_day, 0.0, end_hour, operation_value
                        ])
                    else:
                        # Normal case: start_time to end_time within same day
                        rules_data.append([
                            month, day, start_hour, end_hour, operation_value
                        ])
        
        # Create DataFrame for this operation plan
        df = pd.DataFrame(
            rules_data,
            columns=['month', 'day', 'start_hour', 'end_hour', 'value']
        )
        
        # Sort by month, day, start_hour for cleaner output
        df = df.sort_values(['month', 'day', 'start_hour']).reset_index(drop=True)
        
        plan_name = f'operation_plan_{plan_idx + 1}'
        results[plan_name] = df
        
        # Display basic info about this operation plan
        print(f"\n{plan_name}:")
        print(f"  Total rules: {len(df)}")
        print(f"  Rules per day: {len(op_plan.period)}")
        print(f"  Unique operation values: {sorted(df['value'].unique())}")
        print(f"  Date range: {year}-{df['month'].min():02d}-{df['day'].min():02d} to {year}-{df['month'].max():02d}-{df['day'].max():02d}")
        print("  Sample periods for Jan 1st:")
        jan_1_sample = df[(df['month'] == 1) & (df['day'] == 1)]
        for _, row in jan_1_sample.head().iterrows():
            print(f"    {row['start_hour']:4.1f}h - {row['end_hour']:4.1f}h: {row['value']}")
    
    return results

