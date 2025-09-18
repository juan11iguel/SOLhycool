from typing import Optional
import time
import numpy as np
import pandas as pd
from tqdm.auto import tqdm
import pygmo as pg
import billiard as multiprocessing  # replaces standard multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from solhycool_modeling import EnvironmentVariables, OperationPoint, MatlabOptions
from solhycool_optimization import (AlgoParamsHorizon, 
                                    DecisionVariables, 
                                    ValuesDecisionVariables, 
                                    HorizonResults,
                                    StaticResults,
                                    EvaluationConfig)
from solhycool_optimization.utils import pareto_front_indices
from solhycool_optimization.utils.evaluation import optimize
from solhycool_optimization.utils.serialization import get_fitness_history
from solhycool_optimization.problems.horizon import CombinedCoolerPathFinderProblem
from solhycool_optimization.problems.static import CombinedCoolerProblem

def evaluate_decision_variables(
    step_idx: int, 
    ds_env: pd.Series, 
    dv_values: ValuesDecisionVariables, 
    total_num_evals: int, 
    date_str: str,
    config: EvaluationConfig,
    # models_input_range: ModelInputsRange,
    # matlab_options: Optional[MatlabOptions] = None,
    # load_factor: float = 1.0,
) -> tuple[list[DecisionVariables], list[list[float], list[float]]]:
    """Evaluates decision variables for a given step."""
    
    # logger.info(f"Starting evaluation for step {step_idx}")
    
    import combined_cooler
    cc_model = combined_cooler.initialize()
    
    # Prepare environment variables
    ev = EnvironmentVariables.from_series(ds_env).reduce_load(reduction_factor=config.load_factor).constrain_to_model(config.model_inputs_range)
    ev_m = ev.to_matlab()
    if config.matlab_options is None:
        matlab_options = []
    else:
        matlab_options = config.matlab_options.to_matlab_dict()
    
    # Evaluate different combination of decision variables
    dv_list = []
    consumption_list = [[], []]
    with tqdm(total=total_num_evals, desc=f"{date_str} | Step {step_idx:02d}", position=step_idx, leave=False) as pbar:
        for qc_val in dv_values.qc:
            for rp_val in dv_values.Rp:
                for rs_val in dv_values.Rs:
                    for wdc_val in dv_values.wdc:
                        # print(f"Evaluating: qc={qc_val}, Rp={rp_val}, Rs={rs_val}, wdc={wdc_val}")
                        dv = DecisionVariables(qc=qc_val, Rp=rp_val, Rs=rs_val, wdc=wdc_val).to_matlab()
                        
                        Ce_kWe, Cw_lh, d, valid = cc_model.evaluate_operation(
                            ev_m.Tamb, ev_m.HR, ev_m.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, ev_m.Tv, matlab_options, nargout=4
                        )
                        
                        if valid:
                            dv_list.append(DecisionVariables(qc=d["qc"], Rp=d["Rp"], Rs=d["Rs"], wdc=d["wdc"], wwct=d["wwct"]))
                            consumption_list[0].append(Cw_lh)
                            consumption_list[1].append(Ce_kWe)
                        
                pbar.update(len(dv_values.Rs) * len(dv_values.wdc)) # len(dv_values.Rp)
                pbar.set_postfix(valid_candidates=len(dv_list))
            
    # At least one point should be found, otherwise fallback
    # to static optimization
    if len(dv_list) < 1:
        raise ValueError(f"{date_str} - step {step_idx:02d} | Not a single point was found during decision variables evaulation")
        # problem = CombinedCoolerProblem(env_vars=ev)
        # logger.warning(f"{date_str} - step {step_idx:02d} | Not a single point was found during decision variables evaulation. Trying to find one by performing a static optimization")
        # # Parameters taken from simulation/scripts/yearly_simulation_static.py
        # operation_points, _, pop_list, fitness_list, _ = optimize(
        #     problem,
        #     initial_pop_size=1000,
        #     log_verbosity=0,
        #     algo_id="sea",
        #     use_mbh=False, 
        #     use_cstrs=True,
        #     n_trials=1,
        #     wrapper_algo_iters=50,
        #     max_iter=100,
        #     evaluate_global_with_local=False,
        #     extra_outputs=True,
        # )
        # best_idx = np.argmin(fitness_list[:, 0])
        # dv_list.append(
        #     DecisionVariables(**{
        #         var_id: value for var_id, value in zip(problem.dec_var_ids, 
        #                                                pop_list[best_idx].champion_x)
        #     })
        # )
        # consumption_list[0].append(operation_points[best_idx].Cw)
        # consumption_list[1].append(operation_points[best_idx].Ce)
        
    return dv_list, consumption_list

def evaluate_decision_variables_matlab(
    step_idx: int, 
    ds_env: pd.Series, 
    dv_values: ValuesDecisionVariables, 
    total_num_evals: int, # Not really used here
    date_str: str,
    config: EvaluationConfig,
) -> tuple[list[DecisionVariables], list[list[float], list[float]]]:
    """Evaluates decision variables for a given step."""
        
    import combined_cooler
    cc_model = combined_cooler.initialize()
    
    # Prepare environment variables
    ev = EnvironmentVariables.from_series(ds_env).reduce_load(reduction_factor=config.load_factor).constrain_to_model(config.model_inputs_range)
    if config.matlab_options is None:
        matlab_options = []
    else:
        matlab_options = config.matlab_options.to_matlab_dict()
        
    dv_list, consumption_list = cc_model.evaluate_decision_variables(step_idx, ev.to_matlab_dict(), dv_values.to_matlab_dict(), date_str, matlab_options)
    
    return dv_list, consumption_list

def get_pareto_front(
    dv_list: list[DecisionVariables], 
    consumption_array: np.ndarray[float], 
    df_day: pd.DataFrame, 
    step_idx: int,
    matlab_options: Optional[MatlabOptions] = None,
) -> tuple[list[int], pd.DataFrame]:
    """ Generate pareto front """
    
    import combined_cooler
    cc_model = combined_cooler.initialize()
    
    if matlab_options is None:
        matlab_options = []
    else:
        matlab_options = matlab_options.to_matlab_dict()
    
    pareto_idxs = pareto_front_indices(consumption_array, objective="minimize")
    logger.debug(f"{df_day.index[step_idx].strftime('%Y%m%dT%H%M')} | Pareto front indices: {pareto_idxs}")
        
    # Generate operation points for the Pareto front
    ev = EnvironmentVariables.from_series(df_day.iloc[step_idx]).constrain_to_model()
    ev_m = ev.to_matlab()
    ops = [
        OperationPoint.from_multiple_sources(
            dict_src=cc_model.evaluate_operation(ev_m.Tamb, ev_m.HR, ev_m.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, ev_m.Tv, matlab_options, nargout=3)[2],
            env_vars=ev,
            time=df_day.index[step_idx],
        )
        for dv in [dv_list[i] for i in pareto_idxs]
    ]
    df_paretos = pd.DataFrame([asdict(op) for op in ops])
    
    return pareto_idxs, df_paretos

# TODO: This should not be in this module
@retry(
    stop=stop_after_attempt(3),  # Retry up to 3 times
    wait=wait_exponential(multiplier=2, min=1, max=10),  # Exponential backoff
    retry=retry_if_exception_type(SystemError),  # Retry only on MATLAB runtime errors
)
def generate_set_of_paretos(
    n_parallel_evals: int,
    df_env: pd.DataFrame, 
    dv_values: ValuesDecisionVariables, 
    matlab_options: Optional[MatlabOptions] = None,
) -> StaticResults:
    """ Generate pareto fronts for the given environment """
    
    multiprocessing.set_start_method("spawn", force=True) # MATLAB Engine Cannot Be Used in Forked Processes
    
    date_str = df_env.index[0].strftime("%Y%m%d")
    start_time = time.time()
    
    # Compute total number of evaluations
    total_num_evals = np.prod([len(value) for value in asdict(dv_values).values()])
    
    # 1. Evaluate decision variables
    df_paretos = []
    consumption_arrays = []
    pareto_idxs_list = []
    with ProcessPoolExecutor(max_workers=n_parallel_evals) as executor:
        futures = {
            executor.submit(
                evaluate_decision_variables, step_idx, ds, dv_values, total_num_evals, date_str, matlab_options
            ): step_idx 
            for step_idx, (dt, ds) in enumerate(df_env.iterrows())
        }
        
        for future in as_completed(futures):
            step_idx = futures[future]
            dv_list, consumption_list = future.result()
            
            # 2. Generate pareto front
            consumption_array = np.array(consumption_list).transpose()
            pareto_idxs, df_pareto = get_pareto_front(dv_list, consumption_array, df_env, step_idx)
            df_paretos.append(df_pareto) 
            consumption_arrays.append(consumption_array)
            pareto_idxs_list.append(pareto_idxs)
    
    # Sort the pareto fronts and consumption arrays by time
    # Step 1: Get the time keys for sorting
    time_keys = [df["time"].min() for df in df_paretos]
    # Step 2: Get the sorted indices based on the time keys
    sorted_indices = sorted(range(len(time_keys)), key=lambda i: time_keys[i])
    # Step 3: Apply sorted indices to all parallel lists
    df_paretos = [df_paretos[i] for i in sorted_indices]
    consumption_arrays = [consumption_arrays[i] for i in sorted_indices]
    pareto_idxs_list = [pareto_idxs_list[i] for i in sorted_indices]
    
    logger.info(f"{date_str} | Completed evaluation in {time.time() - start_time:.1f} seconds")

    return StaticResults(
        index=df_env.index,
        df_paretos=df_paretos,
        consumption_arrays=consumption_arrays,
        pareto_idxs=pareto_idxs_list,
    )

def path_selector(
    params: AlgoParamsHorizon, 
    problem: CombinedCoolerPathFinderProblem
) -> tuple[list[int], pd.Series]:
    """ Select points in the pareto fronts """
    
    # Initialize problem instance
    prob = pg.problem(problem)
        
    # Initialize population
    pop = pg.population(prob, size=params.pop_size, seed=0)

    algo = pg.algorithm(getattr(pg, params.algo_id)(**params.params_dict))
    algo.set_verbosity( params.log_verbosity )
    
    pop = algo.evolve(pop)
    
    x = pop.champion_x.astype(int).tolist()
    fitness_history = get_fitness_history(params.algo_id, algo)
    
    return x, fitness_history

@retry(
    stop=stop_after_attempt(3),  # Retry up to 3 times
    wait=wait_exponential(multiplier=2, min=1, max=10),  # Exponential backoff
    retry=retry_if_exception_type(SystemError),  # Retry only on MATLAB runtime errors
)
def evaluate_day(
    n_parallel_evals: int,
    df_day: pd.DataFrame, 
    dv_values: ValuesDecisionVariables, 
    total_num_evals: int, 
    config: EvaluationConfig,
    # path_selector_params: AlgoParamsHorizon,
    # models_input_range: ModelInputsRange,
    # matlab_options: Optional[MatlabOptions] = None,
    # load_factor: float = 1.0,
) -> HorizonResults:
    """ Evaluate optimization for a given day """
    
    multiprocessing.set_start_method("spawn", force=True) # MATLAB Engine Cannot Be Used in Forked Processes
    
    date_str = df_day.index[0].strftime("%Y%m%d")
    start_time = time.time()

    # 1. Evaluate decision variables
    df_paretos = []
    consumption_arrays = []
    pareto_idxs_list = []
    with ProcessPoolExecutor(max_workers=n_parallel_evals) as executor:
        futures = {
            executor.submit(
                evaluate_decision_variables, step_idx, ds, dv_values, total_num_evals, date_str, config
            ): step_idx 
            for step_idx, (dt, ds) in enumerate(df_day.iterrows())
        }
        
        for future in as_completed(futures):
            step_idx = futures[future]
            dv_list, consumption_list = future.result()
            
            # 2. Generate pareto front
            consumption_array = np.array(consumption_list).transpose()
            pareto_idxs, df_pareto = get_pareto_front(dv_list, consumption_array, df_day, step_idx, config.matlab_options)
            df_paretos.append(df_pareto) 
            consumption_arrays.append(consumption_array)
            pareto_idxs_list.append(pareto_idxs)
    
    # Sort the pareto fronts and consumption arrays by time
    # Step 1: Get the time keys for sorting
    time_keys = [df["time"].min() for df in df_paretos]
    # Step 2: Get the sorted indices based on the time keys
    sorted_indices = sorted(range(len(time_keys)), key=lambda i: time_keys[i])
    # Step 3: Apply sorted indices to all parallel lists
    df_paretos = [df_paretos[i] for i in sorted_indices]
    consumption_arrays = [consumption_arrays[i] for i in sorted_indices]
    pareto_idxs_list = [pareto_idxs_list[i] for i in sorted_indices]
    
    # 3. Select points in the pareto fronts

    problem = CombinedCoolerPathFinderProblem(
        # Attach index to df_paretos so time between steps can be calculated
        df_paretos=pd.Series(df_paretos, index=df_day.index),
        Vavail0=df_day.iloc[0]["Vavail_m3"]
    )
    logger.info(f"{date_str} | Started evaluation of best path of pareto front points")
    selected_pareto_idxs, fitness_history = path_selector(config.algo_params, problem)
    logger.info(f"{date_str} | Selected pareto front indices: {selected_pareto_idxs}")

    # 4. Generate results dataframe for the day
    _, ops = problem.evaluate(
        [
            OperationPoint(**problem.df_paretos[step_idx].iloc[selected_idx]) 
            for step_idx, selected_idx in enumerate(selected_pareto_idxs)
        ],
        update_operation_pts=True
    )
    df_results = pd.DataFrame([asdict(op) for op in ops],).set_index("time", drop=True)
    logger.info(f"{date_str} | Completed evaluation in {time.time() - start_time:.1f} seconds")
    
    return HorizonResults(
        index=df_day.index,
        df_paretos=df_paretos,
        consumption_arrays=consumption_arrays,
        pareto_idxs=pareto_idxs_list,
        fitness_history=fitness_history,
        selected_pareto_idxs=selected_pareto_idxs,
        df_results=df_results
    )