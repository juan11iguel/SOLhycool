from pathlib import Path
import pandas as pd
from solhycool_optimization import DayResults  # adjust this import
from loguru import logger

def export_results_day(day_results: DayResults, output_path: Path) -> None:
    with pd.HDFStore(output_path, mode='a') as store:
        for dt, df_pareto, consumption_array in zip(
            day_results.index, day_results.df_paretos, day_results.consumption_arrays
        ):
            table_key = dt.strftime("%Y%m%dT%H%M")

            # Save pareto front for this timestep
            store.put(f"/pareto/{table_key}", df_pareto)

            # Save consumption array for this timestep
            df_consumption = pd.DataFrame(consumption_array, columns=["Cw", "Ce"])
            store.put(f"/consumption/{table_key}", df_consumption)

        # Append df_results (path of selected solutions)
        if "/results" in store:
            existing = store["/results"]
            combined = pd.concat([existing, day_results.df_results])
            combined = combined.sort_index()
            store.put("/results", combined)
        else:
            store.put("/results", day_results.df_results.sort_index())

        # Save  paths
        store.put("/paths/pareto_idxs", pd.Series(day_results.pareto_idxs, index=day_results.index))
        store.put("/paths/selected_pareto_idxs", pd.Series(day_results.selected_pareto_idxs, index=day_results.index))

    logger.info(f"Results saved to {output_path}")

def import_results_day(input_path: Path, date_str: str) -> DayResults:
    with pd.HDFStore(input_path, mode='r') as store:
        # Find all pareto keys for the given date
        all_keys = store.keys()
        date_keys = [
            key for key in all_keys
            if key.startswith("/pareto/") and key.split("/")[-1].startswith(date_str)
        ]
        
        if not date_keys:
            raise ValueError(f"No pareto results found for date {date_str} in {input_path}")
        
        # Extract and sort datetime index
        time_index = sorted([
            pd.to_datetime(key.split("/")[-1], format="%Y%m%dT%H%M").tz_localize("UTC")
            for key in date_keys
        ])

        # Load data for the selected date
        df_paretos = []
        consumption_arrays = []

        for dt in time_index:
            key = dt.strftime("%Y%m%dT%H%M")
            df_paretos.append(store[f"/pareto/{key}"])
            df_consumption = store[f"/consumption/{key}"]
            consumption_arrays.append(df_consumption.to_numpy())

        # Load df_results (subset for the day)
        df_results = store["/results"]
        df_results = df_results.loc[
            (df_results.index >= time_index[0]) & (df_results.index <= time_index[-1])
        ]

        # Load path indices (subset for the day)
        pareto_idxs_series = store["/paths/pareto_idxs"]
        selected_pareto_idxs_series = store["/paths/selected_pareto_idxs"]

        pareto_idxs = [pareto_idxs_series.loc[dt] for dt in time_index]
        selected_pareto_idxs = [selected_pareto_idxs_series.loc[dt] for dt in time_index]

    logger.info(f"DayResults loaded for {date_str} from {input_path}")

    return DayResults(
        index=time_index,
        df_paretos=df_paretos,
        consumption_arrays=consumption_arrays,
        df_results=df_results,
        pareto_idxs=pareto_idxs,
        selected_pareto_idxs=selected_pareto_idxs
    )
