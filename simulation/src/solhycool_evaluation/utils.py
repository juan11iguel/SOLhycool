from pathlib import Path
import pandas as pd

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
        " Ta": "Tamb",
        " RH": "HR",
        "RR": "precip"
    }

    env_df = env_df.rename(columns=new_columns)
    # display(env_df)

    # Save the pre-processed data
    env_df.to_csv(txt_file_path.with_suffix(".csv"), index=True)
    
    return pd.read_csv(txt_file_path.with_suffix(".csv"), index_col=0)