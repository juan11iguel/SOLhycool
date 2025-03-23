import copy
from typing import Literal
from pathlib import Path
from collections import deque
from dataclasses import asdict
import numpy as np
import pandas as pd
from loguru import logger
import pygmo as pg
import datetime
import time
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

from solhycool_modeling import EnvironmentVariables
from solhycool_optimization.utils.evaluation import optimize
from solhycool_evaluation.utils.serialization import export_evaluation_results

logger.disable("phd_visualizations")
np.set_printoptions(precision=2)

params_per_problem = {
    "dc": {
        "algo_params": dict(
            initial_pop_size=400,
            log_verbosity=5,
            algo_id="sea",
            use_mbh=False,
            use_cstrs=True,
            n_trials=1,
            wrapper_algo_iters=10,
            max_iter=80,
        ),
        "reduce_load": True,
    },
}

def evaluate_day(single_date, df_day, params, problem_cls):
    date_str = single_date.strftime("%Y%m%d")
    logger.info(f"Evaluating day: {date_str}")
    start_time = time.time()

    results = []
    x_list = []
    fitness_list = []

    pop0 = deque(maxlen=10)  # Each day gets a fresh deque

    for idx, (dt, ds) in enumerate(df_day.iterrows()):
        logger.info(f"Step {idx+1}/{len(df_day)}: {dt}")
        env_vars = EnvironmentVariables.from_series(ds)
        if params["reduce_load"]:
            env_vars.reduce_load(0.5)

        problem = problem_cls(env_vars=env_vars)
        operation_points, _, pop_list, fitness_list_, _ = optimize(
            problem,
            **params["algo_params"],
            evaluate_global_with_local=True,
            extra_outputs=True,
            pop0=pop0 if len(pop0) > 0 else None,
        )
        best_idx = np.argmin(fitness_list_[:, 0])
        results.append(asdict(operation_points[best_idx]))
        pop0.append(pop_list[best_idx].champion_x)
        x_list.append(pop_list[best_idx].champion_x)
        fitness_list.append(fitness_list_[best_idx])

    evaluation_time = int(time.time() - start_time)
    logger.info(f"Completed day {date_str} in {evaluation_time:.0f} sec")

    df_sim = pd.DataFrame(results, index=df_day.index)
    return date_str, df_sim, x_list, fitness_list, evaluation_time


def main(problem_id: Literal["dc", "wct", "cc"], n_parallel_evals: int, base_path: Path, env_path: Path, date_span: tuple[str, str]):
    if problem_id == "dc":
        from solhycool_optimization.problems.static import DryCoolerProblem as Problem
    elif problem_id == "wct":
        from solhycool_optimization.problems.static import WetCoolerProblem as Problem
    elif problem_id == "cc":
        from solhycool_optimization.problems.static import CombinedCoolerProblem as Problem
    else:
        raise ValueError(f"Invalid problem_id: {problem_id}")
    
    env_path = base_path / env_path
    base_output_path = base_path / "simulation/results"
    date_span_str = f"{date_span[0]}_{date_span[1]}"
    output_path = base_output_path / date_span_str
    output_path.mkdir(parents=True, exist_ok=True)

    params = params_per_problem[problem_id]
    metadata = {
        "date_span": date_span,
        "problem_id": problem_id,
        **params["algo_params"],
    }
    file_id = f"eval_at_{datetime.datetime.now():%Y%m%dT%H%M}"

    start_date = datetime.datetime.strptime(date_span[0], "%Y%m%d").replace(hour=0)
    end_date = datetime.datetime.strptime(date_span[1], "%Y%m%d").replace(hour=23)

    df_env = pd.read_hdf(env_path).loc[date_span[0]:date_span[1]]
    all_dates = list(pd.date_range(start=start_date, end=end_date, freq='D', tz='UTC'))

    results_futures = []
    df_sim_all = []
    start_time = time.time()
    with ProcessPoolExecutor(max_workers=n_parallel_evals) as executor:
        future_to_date = {}

        for date in all_dates:
            df_day = df_env.loc[date.strftime("%Y%m%d")]
            future = executor.submit(evaluate_day, date, df_day, params, Problem)
            results_futures.append(future)
            future_to_date[future] = date.strftime("%Y%m%d")

        with tqdm(total=len(all_dates), desc="Evaluating days", unit="day") as pbar:
            for future in as_completed(results_futures):
                date_str = future_to_date.get(future, "unknown")
                try:
                    date_str, df_sim, x_list, fitness_list, eval_time = future.result()
                    logger.info(f"[{date_str}] Evaluation complete, saving results")

                    results_dict = {
                        date_str: {
                            "x": x_list,
                            "fitness": fitness_list,
                            "evaluation_time_sec": eval_time,
                        }
                    }

                    df_sim_all.append(df_sim)

                    export_evaluation_results(
                        results_dict=results_dict,
                        metadata=metadata,
                        df_opt=None,
                        df_sim=df_sim,
                        algo_logs=None,
                        algo_table_ids=[f"{date_str}T{hour:02d}" for hour in range(24)],
                        output_path=output_path,
                        file_id=file_id,
                        fitness_history=None,
                    )
                except Exception as e:
                    logger.error(f"[{date_str}] Failed to process: {e}")
                pbar.update(1)

    # Combine all simulations into one DataFrame
    final_df_sim = pd.concat(df_sim_all).sort_index()
    final_df_sim.to_hdf(output_path / f"simulation_results_{file_id}.h5",)
    logger.info(f"All evaluations completed. Results saved to {output_path}. Total time: {int(time.time() - start_time)/3600} hours")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--problem_id', type=str, required=True)
    parser.add_argument('--n_parallel_evals', type=int, default=10)
    parser.add_argument('--base_path', type=str, default="/workspaces/SOLhycool")
    parser.add_argument('--env_path', type=str, default="data/datasets/environment_data_20220101_20241231.h5")
    parser.add_argument('--date_span', nargs=2, default=["20220101", "20221231"])

    args = parser.parse_args()

    main(
        problem_id=args.problem_id,
        n_parallel_evals=args.n_parallel_evals,
        base_path=Path(args.base_path),
        env_path=Path(args.env_path),
        date_span=tuple(args.date_span),
    )
