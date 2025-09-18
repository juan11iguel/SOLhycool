from solhycool_evaluation.evaluation import evaluate_optimization


if __name__ == "__main__":
    
    evaluate_optimization(
        sim_id="pilot_plant_wct100",
        sim_config_path = "/workspaces/SOLhycool/simulation/data/simulations_config.json",
        env_path = "/workspaces/SOLhycool/data/datasets/",
        output_path = "/workspaces/SOLhycool/simulation/results/", 
        date_span= ("20220505", "20220514"),
        n_parallel_steps = 24,
        n_parallel_days = 5,
    )