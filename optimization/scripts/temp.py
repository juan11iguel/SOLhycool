import time
import numpy as np
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from dataclasses import asdict
from loguru import logger

import combined_cooler
from solhycool_modeling import EnvironmentVariables, OperationPoint
from solhycool_optimization import DecisionVariables, ValuesDecisionVariables
from solhycool_optimization.utils import pareto_front_indices

def evaluate_decision_variables(step_idx: int, ds_env: pd.Series, dv_values: ValuesDecisionVariables, total_num_evals: int) -> tuple[list[DecisionVariables], list[list[float], list[float]]]:
    """Evaluates decision variables for a given step."""
    
    cc_model = combined_cooler.initialize()
    
    # Prepare environment variables
    ev = EnvironmentVariables.from_series(ds_env).constrain_to_model()
    ev_m = ev.to_matlab()
    
    dv_list = []
    consumption_list = [[], []]
    
    with tqdm(total=total_num_evals, desc=f"Step {step_idx}", position=step_idx, leave=False) as pbar:
        for qc_val in dv_values.qc:
            for rp_val in dv_values.Rp:
                for rs_val in dv_values.Rs:
                    for wdc_val in dv_values.wdc:
                        dv = DecisionVariables(qc=qc_val, Rp=rp_val, Rs=rs_val, wdc=wdc_val).to_matlab()
                        Ce_kWe, Cw_lh, d, valid = cc_model.evaluate_operation(
                            ev_m.Tamb, ev_m.HR, ev_m.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, ev_m.Tv, nargout=4
                        )
                        if valid:
                            dv_list.append(DecisionVariables(qc=d["qc"], Rp=d["Rp"], Rs=d["Rs"], wdc=d["wdc"], wwct=d["wwct"]))
                            consumption_list[0].append(Cw_lh)
                            consumption_list[1].append(Ce_kWe)
                        
                        pbar.update(1)
                        pbar.set_postfix(valid_candidates=len(dv_list))
    
    return dv_list, consumption_list


def main():
    data_path: Path = Path("../../data")
    env_path: Path = data_path / "datasets/environment_data_20220101_20241231.h5"
    n_parallel_evals = 10
    selected_date_str: str = "20220103"

    cc_model = combined_cooler.initialize()

    # Load environment into EnvironmentVariables for the episode
    df_env = pd.read_hdf(env_path)
    df_day = df_env.loc[selected_date_str]

    # Generate decision variable arrays
    dv_values: ValuesDecisionVariables = ValuesDecisionVariables().generate_arrays()
    # Compute total number of evaluations
    total_num_evals = np.prod([len(value) for value in asdict(dv_values).values()])

    results = []
    start_time = time.time()

    with ProcessPoolExecutor(max_workers=n_parallel_evals) as executor:
        futures = {executor.submit(evaluate_decision_variables, step_idx, ds, dv_values, total_num_evals): step_idx for step_idx, (dt, ds) in enumerate(df_day.iterrows())}
        for future in as_completed(futures):
            step_idx = futures[future]
            
            dv_list, consumption_list = future.result()
            consumption_array = np.array(consumption_list).transpose()
            idxs = pareto_front_indices(consumption_array, objective="minimize")

            logger.info(f"Pareto front indices: {idxs}")

            # Generate operation points for the Pareto front
            ev = EnvironmentVariables.from_series(df_day.iloc[step_idx]).constrain_to_model()
            ev_m = ev.to_matlab()
            ops = [
                OperationPoint.from_multiple_sources(
                    dict_src=cc_model.evaluate_operation(ev_m.Tamb, ev_m.HR, ev_m.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, ev_m.Tv, nargout=3)[2],
                    env_vars=ev,
                    time=df_day.index[step_idx],
                )
                for dv in [dv_list[i] for i in idxs]
            ]
            df_paretos = [pd.DataFrame(asdict(op)) for op in ops]
            results.append((step_idx, df_paretos, consumption_array))
                

    # Save results to HDF5
    output_path = Path(".") / "results" / "pareto_fronts.h5"
    with pd.HDFStore(output_path, mode='w') as store:
        for step_idx, df_paretos, _ in results:
            store.put(f"step_{step_idx}", pd.concat(df_paretos))

    print(f"Completed evaluation in {time.time() - start_time:.1f} seconds")
    
if __name__ == "__main__":
    main()