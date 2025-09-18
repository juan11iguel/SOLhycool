from pathlib import Path
from solhycool_modeling.evaluation import WCTModelEvaluator


def main():
    """Main function to run the evaluation."""
    # Configuration
    case_study_id = "andasol_90MW"  # or "pilot_plant_200kW"
    timeout = 3.0  # seconds
    n_processes = None  # Auto-detect
    base_path = Path(f"/workspaces/SOLhycool/modeling/results/model_inputs_sampling/{case_study_id}")
    
    # Create evaluator
    evaluator = WCTModelEvaluator(
        case_study_id=case_study_id,
        timeout=timeout,
        n_processes=n_processes,
        base_path=base_path,
        timeout_duration=10
    )
    
    # Run evaluation
    evaluator.run_evaluation()


if __name__ == "__main__":
    main()