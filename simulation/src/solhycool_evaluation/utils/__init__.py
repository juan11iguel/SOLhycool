from pathlib import Path
import pandas as pd
from loguru import logger

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