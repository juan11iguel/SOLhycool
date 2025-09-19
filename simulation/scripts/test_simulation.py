from solhycool_evaluation.evaluation import evaluate_optimization_robust


if __name__ == "__main__":
    
    evaluate_optimization_robust(
        sim_id="andasol_pilot_plant_wct100",
        sim_config_path = "/workspaces/SOLhycool/simulation/data/simulations_config.json",
        env_path = "/workspaces/SOLhycool/data/datasets/",
        output_path = "/workspaces/SOLhycool/simulation/results/", 
        date_span= ("20220601", "20220630"),
        n_parallel_steps = 24,
        n_parallel_days = 5,
        # file_id="results_eval_at_20250918T1816_sim_results"
    )