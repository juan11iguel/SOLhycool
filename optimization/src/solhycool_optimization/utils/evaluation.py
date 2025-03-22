import itertools
from enum import Enum
from dataclasses import asdict
import numpy as np
import pandas as pd
import pygmo as pg
from loguru import logger
# TODO: We should be able to use a generic Problem class not specifically the static
from solhycool_optimization.problems.static import BaseProblem

class AlgoLogColumns(Enum):
    """Enum for the algorithm logs columns."""
    
    GACO = ["Gen", "Fevals", "Best", "Kernel", "Oracle", "dx", "dp"]
    SGA = ["Gen", "Fevals", "Best", "Improvement", "Mutations"]
    NSGA2 = ["Gen", "Fevals", "ideal_point"]
    SIMULATED_ANNEALING = ["Fevals", "Best", "Current", "Mean range", "Temperature"]
    DE = ["Gen", "Fevals", "Best", "dx", "df"]
    CMAES = ["Gen", "Fevals", "Best", "dx", "df", "sigma"]
    SEA = ["Gen", "Fevals", "Best", "Improvement", "Mutations"]
    PSO_GEN = ["Gen", "Fevals", "gbest", "Mean Vel.", "Mean lbest", "Avg. Dist."]
    SADE = ["Gen", "Fevals", "Best", "F", "CR", "dx", "df"]
    IHS = ["Fevals", "ppar", "bw", "dx", "df", "Violated", "Viol. Norm", "ideal1"]
    MBH = ["Fevals", "Best", "Violated", "Viol. Norm", "Trial"]
    CSTRS_SELF_ADAPTIVE = ["Iter", "Fevals", "Best", "Infeasibility", "Violated", "Viol. Norm", "N. Feasible"]
    SLSQP = ["Fevals", "objval", "violated", "viol. norm", "feasible"] 
    
    @property
    def columns(self) -> list[str]:
        return self.value
    
class AlgoFitnessCol(Enum):
    """Enum for the algorithm logs columns."""
    
    GACO = "Best"
    SGA = "Best"
    NSGA2 = "ideal_point"
    SIMULATED_ANNEALING = "Best"
    DE = "Best"
    CMAES = "Best"
    SEA = "Best"
    PSO_GEN = "gbest"
    SADE = "Best"
    IHS = "ideal1"
    MBH = "Best"
    CSTRS_SELF_ADAPTIVE = "Best"
    SLSQP = "objval"

def optimize(problem: BaseProblem, extra_outputs: bool = False,  
             algo_id: str = "compass_search", initial_pop_size: int = 20,
             n_trials: int = 5, log_verbosity: int = 1, 
             use_mbh: bool = False, use_cstrs: bool = False, wrapper_algo_iters: int = 3,
             max_iter: int = 200, tol: float = 1e-1, 
             pop0: list[list[float]] = None, evaluate_global_with_local: bool = False,
            ) -> list[dict] | tuple[list[dict], list[pg.algorithm], list[pg.population], np.ndarray, list[np.ndarray]]:
    
    def optimize_single() -> tuple[dict, pg.algorithm, pg.population, np.ndarray]:
    
        prob = pg.problem(problem)
        prob.c_tol = problem.c_tol
        
        # Internal algorithms
        if algo_id == "ipopt":
            internal_algo = pg.ipopt()
            internal_algo.set_numeric_options({
                "bound_relax_factor": 0.0, 
                "tol": tol
            })
            # internal_algo.set_numeric_options({"constr_viol_tol":0})
            # internal_algo.set_numeric_option("tol", 1E-1) # Change the relative convergence tolerance
            internal_algo.set_integer_option("max_iter", max_iter) # Change the maximum number of iterations
            # ip.set_numeric_options({}) #})
        elif algo_id == "slsqp":
            internal_algo = pg.nlopt('slsqp')
            internal_algo.ftol_abs = tol
            internal_algo.maxeval = max_iter
            
        elif algo_id == "compass_search":
            internal_algo = pg.compass_search(max_fevals=max_iter)
            
        elif algo_id in ["ihs", "gaco", "sea", "de"]:
            internal_algo = getattr(pg, algo_id)(gen=max_iter)
            
        else:
            internal_algo = getattr(pg, algo_id)

        # Wrapper algorithms
        if use_mbh:
            algo = pg.algorithm(
                pg.mbh(algo=internal_algo, stop=wrapper_algo_iters)
            )
            algo_id_ = "MBH"
        elif use_cstrs:
            algo = pg.algorithm(
                pg.cstrs_self_adaptive(iters=wrapper_algo_iters, algo=internal_algo)
            )
            algo_id_ = "CSTRS_SELF_ADAPTIVE"
        else:
            algo = pg.algorithm(internal_algo)
            algo_id_ = algo_id.upper()
            
        algo.set_verbosity(log_verbosity)

        pop = pg.population(prob, initial_pop_size)
        
        if pop0 is not None:
            [pop.push_back(x0) for x0 in pop0]
        
        pop = algo.evolve(pop)
        
        op_pt = problem.evaluate(pop.champion_x)
        # fitness_history = pop.problem.extract(object).fitness_history
        # if not extra_outputs:
        #     return op_pt
        # else:
        if use_mbh:
            algo_cls = pg.mbh
        elif use_cstrs:
            algo_cls = pg.cstrs_self_adaptive
        elif algo_id in ["slsqp", ]:
            algo_cls = pg.nlopt
        else:
            algo_cls = getattr(pg, algo_id)
        algo_logs = pd.DataFrame(algo.extract(algo_cls).get_log(), columns=AlgoLogColumns[algo_id_].columns, dtype=float)
        
        if log_verbosity > 0:
            fitness_history = np.interp(
                x=np.arange(pop.problem.get_fevals()), 
                xp=algo_logs["Fevals"], 
                fp=algo_logs[AlgoFitnessCol[algo_id_].value]
            )
        else:
            fitness_history = []
        
        return op_pt, algo, pop, pop.champion_f, fitness_history
        
    # Outer function
    if pop0 is not None:
        for idx_x0, x0 in enumerate(pop0):
            assert len(x0) == problem.size_dec_vector, f"Input decision vector at position {idx_x0} length does not match problem decision vector size: {len(x0)=} vs {problem.size_dec_vector=}"
    
    fitness_list: list[float] = []
    algo_list: list = []
    operation_pt_list = []
    pop_list = []
    fitness_history_list = []
    # problem.store_fitness = True
    
    for eval_idx in range(n_trials):
        if log_verbosity > 0:
            logger.info(f"Iteration {eval_idx+1} out of {n_trials}")
        
        op_pt, algo, pop, fitness, fitness_history = optimize_single()
        fitness_list.append(fitness)
        operation_pt_list.append(op_pt)
        algo_list.append(algo)
        pop_list.append(pop)
        fitness_history_list.append(fitness_history)
        
    fitness_list = np.array(fitness_list)

    # Evaluate the best solution with a local optimizer
    if evaluate_global_with_local:
        best_idx = np.argmin(fitness_list[:, 0])
        algo_id = "slsqp"
        tol=1e-9
        pop0 = [pop_list[best_idx].champion_x]
        use_cstrs = False
        use_mbh = False
        op_pt, algo, pop, fitness, fitness_history = optimize_single()
        
        logger.info(f"After evaluting best solution with local optimizer: {fitness[0]}, before {fitness_list[best_idx][0]}")
        
        # Replace the best solution
        fitness_list[best_idx] = fitness
        operation_pt_list[best_idx] = op_pt
        algo_list[best_idx] = algo
        pop_list[best_idx] = pop
        fitness_history_list[best_idx] = fitness_history
        
    logger.info(f"Variance: {np.var(fitness_list[:, 0]):.3f} | {fitness_list[:, 0]}")
    
    if extra_outputs:
        return operation_pt_list, algo_list, pop_list, fitness_list, fitness_history_list
    else:
        return operation_pt_list
    
    

def evaluate_global_algos(
    problem,
    n_trials: int = 1,
    max_n_obj_fun_evals: int = 1000,
    algo_ids: list[str] = ["ihs", "sea", "de", ],
    use_cstr: list[bool] = [False, True, True,],
    pop_size: list[int] = [50, 100, 400],
    wrapper_algo_iters: int = 10,
    log_verbosity: list[int] = [100, 1, 1],
) -> dict:
    
    results = {}
    # {case_study_id: {parameters: ..., avg_fitness: x, var_fitness: x}}

    for algo_id, pop_size in itertools.product(algo_ids, pop_size):
        idx = algo_ids.index(algo_id)
        max_iter = max_n_obj_fun_evals
        if use_cstr[idx]:
            max_iter = max_iter // wrapper_algo_iters
        
        if algo_id not in ["sea", "ihs"]: # Evolves only one individual
            max_iter = max_iter // pop_size
        
        logger.info(f"Running {algo_id} with cstr={use_cstr[idx]}, pop_size={pop_size} and max_iter={max_iter}")
        
        algo_str = f"{algo_id}_cstr" if use_cstr[idx] else algo_id
        case_study_id = f"{algo_str}_{pop_size}_{max_iter}"
        
        operation_pt_list, algo_list, pop_list, fitness_list, fitness_history_list = optimize(
            problem, algo_id=algo_id, 
            n_trials = n_trials, log_verbosity = log_verbosity[idx], extra_outputs=True, 
            max_iter=max_iter, use_mbh=False, use_cstrs=use_cstr[idx],
            initial_pop_size=pop_size, wrapper_algo_iters=wrapper_algo_iters, 
        )
        best_idx = np.argmin(fitness_list[:, 0])

        results[case_study_id] = dict(
            algo_id=algo_id,
            params = dict(pop_size = pop_size, max_iter = max_iter, cstr_sa = use_cstr[idx], wrapper_algo_iters = wrapper_algo_iters),
            avg_fitness = np.mean(fitness_list[:, 0]),
            var_fitness = np.var(fitness_list[:, 0]),
            best_op_pt = asdict(operation_pt_list[best_idx]),
            avg_n_obj_fun_evals = np.floor(np.mean([len(fitness_history) for fitness_history in fitness_history_list])),
            fitness_history = fitness_history_list[best_idx]
        )
        
    return results

def evaluate_local_algos(
    problem,
    n_trials: int = 1,
    algo_ids: list[str] = ["ipopt", "slsqp", "compass_search"],
    pop_size: list[int] = [50, 100, 400],
    wrapper_algo_iters: int = 5,
) -> dict:
    pass