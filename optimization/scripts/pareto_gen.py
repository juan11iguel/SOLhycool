import pandas as pd
import numpy as np
from pathlib import Path
from solhycool_optimization import ValuesDecisionVariables, StaticResults, EvaluationConfig
from solhycool_modeling import EnvironmentVariables
from solhycool_optimization.problems.horizon.evaluation import generate_set_of_paretos
from phd_visualizations import save_figure

import combined_cooler
import matlab



if __name__ == "__main__":
    results_path = Path("../results")

    case_study_id = "andasol_pilot_plant_wct100_dc100" # Check case studies in `sim_config_path`

    case_studies_dict = {
        # "pilot_plant": {
        #     "Qnominal_kW": 200,
        #     "Tv_C": 42,
        # },
        # "andasol_wct100": {
        #     "Qnominal_kW": 95*10**3, # 95 MWth
        #     "Tv_C": 41.5,
        # },
        # "andasol_25_dc": {
        #     "Qnominal_kW": 95*10**3, # 95 MWth
        #     "Tv_C": 41.5,
        # },
        # "andasol_50_dc": {
        #     "Qnominal_kW": 95*10**3, # 95 MWth
        #     "Tv_C": 41.5,
        # },
        # "andasol_75_dc": {
        #     "Qnominal_kW": 95*10**3, # 95 MWth
        #     "Tv_C": 41.5,
        # },
        "andasol_pilot_plant_wct100_dc100":{
            "Qnominal_kW": 200,
            "Tv_C": 42,
        } 
    }

    sim_config_path = "/workspaces/SOLhycool/simulation/data/simulations_config.json"

    # Get simulation configuration
    sim_config: EvaluationConfig = EvaluationConfig.from_config_file(sim_config_path, case_study_id)
    cs = case_studies_dict[case_study_id]

    # Compute decision variable arrays
    dv_values=sim_config.vals_dec_vars.generate_arrays(sim_config.model_inputs_range)

    df_env = EnvironmentVariables(
        Tamb=[30, 30, 10, 10], #, 40, 40],
        HR=[40, 40, 70, 70], #, 50, 50],
        Q=np.array([1, 0.7, 1, 0.7])*cs["Qnominal_kW"], # 1, 0.6] 
        Tv=[cs["Tv_C"]]*4 # [42]*4 + [55]*2,
    ).to_dataframe(
        index=pd.to_datetime([
            '2005-06-23 13:00:00+02:00', 
            '2005-06-23 13:01:00+02:00', 
            '2005-12-21 14:00:00+02:00', 
            '2005-12-21 14:01:00+02:00',
            # '2005-07-23 13:01:00+02:00',
            # '2005-07-23 13:01:00+02:00',
        ])
    )

    paretos_set = generate_set_of_paretos(
        df_env=df_env,
        n_parallel_evals=20,
        dv_values=dv_values,
        eval_config=sim_config,
    )

    paretos_set.export(results_path / f"paretos_set_for_different_scenarios_{case_study_id}.h5")