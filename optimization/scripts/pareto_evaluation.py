import argparse
import time
import numpy as np
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from dataclasses import asdict

# Placeholder imports (ensure these are correctly imported from your project)
from solhyccool_modeling.models import DecisionVariables, ValuesDecisionVariables, EnvironmentVariables, cc_model
from solhyccool_optimization.utils import pareto_front_indices, evaluate_day


def evaluate_decision_variables(step_idx, df_day):
    """Evaluates decision variables for a given time step."""
    # Generate decision variable arrays
    dv_values = ValuesDecisionVariables().generate_arrays()
    total_num_evals = np.prod([len(value) for value in asdict(dv_values).values()])
    
    # Prepare environment variables
    ev = EnvironmentVariables.from_series(df_day.iloc[step_idx]).contrain_to_model()
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
                            consumption_list[0].append(Ce_kWe)
                            consumption_list[1].append(Cw_lh)
                        
                        pbar.update(1)
                        pbar.set_postfix(valid_candidates=len(dv_list))
    
    return dv_list, consumption_list


def main(n_parallel_evals, base_path, env_path, date_span):
    """Main function to evaluate decision variables in parallel."""
    df_day = pd.read_hdf(env_path, key="environment_data")
    step_indices = range(len(df_day))
    
    results = []
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=n_parallel_evals) as executor:
        futures = {executor.submit(evaluate_decision_variables, step_idx, df_day): step_idx for step_idx in step_indices}
        for future in as_completed(futures):
            step_idx = futures[future]
            try:
                dv_lists, consumption_list = future.result()
                consumption_array = np.array(consumption_list).transpose()
                idxs = pareto_front_indices(consumption_array, objective="minimize")
                df_paretos = [pd.DataFrame(asdict(dv_lists[idx])) for idx in idxs]
                results.append((step_idx, df_paretos))
            except Exception as e:
                print(f"Error in step {step_idx}: {e}")
    
    # Save results to HDF5
    output_path = Path(base_path) / "results" / "pareto_fronts.h5"
    with pd.HDFStore(output_path, mode='w') as store:
        for step_idx, df_paretos in results:
            store.put(f"step_{step_idx}", pd.concat(df_paretos))
    
    print(f"Completed evaluation in {time.time() - start_time:.1f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_parallel_evals', type=int, default=16, help="Number of parallel evaluations")
    parser.add_argument('--base_path', type=str, default="/workspaces/SOLhycool", help="Base path for storing results")
    parser.add_argument('--env_path', type=str, default="data/datasets/environment_data_20220101_20241231.h5", help="Path to environment data")
    parser.add_argument('--date_span', nargs=2, default=["20220101", "20221231"], help="Date range for evaluation")
    
    args = parser.parse_args()
    
    main(
        n_parallel_evals=args.n_parallel_evals,
        base_path=Path(args.base_path),
        env_path=Path(args.env_path),
        date_span=args.date_span
    )
