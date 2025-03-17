from enum import Enum
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

def optimize(problem: BaseProblem, extra_outputs: bool = False,  
             algo_id: str = "compass_search", initial_pop_size: int = 20,
             n_trials: int = 5, log_verbosity: int = 1, 
             use_mbh: bool = True, use_cstrs: bool = False, wrapper_algo_iters: int = 3,
             max_iter: int = 200, tol: float = 1e-1
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
        else:
            algo_cls = getattr(pg, algo_id)
        algo_logs = pd.DataFrame(algo.extract(algo_cls).get_log(), columns=AlgoLogColumns[algo_id_].columns, dtype=float)
        
        fitness_history = np.interp(
            x=np.arange(pop.problem.get_fevals()), 
            xp=algo_logs["Fevals"], 
            fp=algo_logs[AlgoFitnessCol[algo_id_].value]
        )
        
        return op_pt, algo, pop, pop.champion_f, fitness_history
        
    # Outer function
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
        
    logger.info(f"Variance: {np.var(fitness_list[:, 0]):.3f} | {fitness_list[:, 0]}")
    
    if extra_outputs:
        return operation_pt_list, algo_list, pop_list, fitness_list, fitness_history_list
    else:
        return operation_pt_list