"""
Example script to evaluate single or multiple decision variable sets for the combined cooler.
"""
from dataclasses import asdict
import numpy as np

from solhycool_optimization import ValuesDecisionVariables, EvaluationConfig, DecisionVariables
from solhycool_modeling import EnvironmentVariables
from solhycool_optimization.problems.horizon.evaluation import evaluate_decision_variables

import combined_cooler

if __name__ == "__main__":
    
    eval_config_path = "/workspaces/SOLhycool/simulation/data/simulations_config.json"
    case_study_id = "pilot_plant_wct100_dc100"

    cc_model = combined_cooler.initialize()
    
    # Get simulation configuration
    eval_config: EvaluationConfig = EvaluationConfig.from_config_file(eval_config_path, case_study_id)

    # Example (minimal) environment. Elements can be lists 
    ev = EnvironmentVariables(
        Tamb=[30.8],
        HR=[39.3],
        Q=[200],
        Tv=[45],
    )
    
    """ Example single decision variables set """
    # Example decision variables
    dv = DecisionVariables(qc=20, Rp=0.5, Rs=0.5, wdc=80)
    
    # Convert to matlab compatible types
    ev_m = ev.to_matlab()
    dv_m = dv.to_matlab()
    matlab_options = eval_config.matlab_options.to_matlab_dict()

    # Evaluate the operation
    Ce_kWe, Cw_lh, d, valid = cc_model.evaluate_operation(
        ev_m.Tamb, ev_m.HR, ev_m.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, ev_m.Tv, matlab_options, nargout=4
    )
    
    print(f"Single evaluation results:\n{Ce_kWe=:.2f}\n{Cw_lh=:.2f}\nd: {d}\nvalid: {valid}\n\n")
    
    """ Example multiple decision variables sets """
    # Generate a set of decision variables to evaluate
    # dv_values = ValuesDecisionVariables.initialize(5).generate_arrays()
    dv_values=ValuesDecisionVariables(
        qc=3, Rp=3, Rs=3, wdc=3
    ).generate_arrays(
        inputs_range=eval_config.model_inputs_range
    )
    
    print("Evaluating multiple decision variable sets...")
    print(f"{dv_values=}\n")
    
    dv_list, consumption_list = evaluate_decision_variables(
        step_idx=0, # Does not matter
        ds_env=ev.to_dataframe().iloc[0],
        dv_values=dv_values,
        total_num_evals=np.prod([len(value) for value in asdict(dv_values).values()]), # Probably should be optional
        date_str="20251212", # Probably should be optional
        config=eval_config,
    )
    
    for dv_item, consumption in zip(dv_list, consumption_list):
        print(f"Feasible dec. vars: {dv_item}, Ce: {consumption[0]:.2f}, Cw: {consumption[1]:.2f}")