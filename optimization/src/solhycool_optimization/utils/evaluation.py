import numpy as np
import pygmo as pg
from loguru import logger
# TODO: We should be able to use a generic Problem class not specifically the static
from solhycool_optimization.problems.static import BaseProblem

def optimize(problem: BaseProblem, extra_outputs: bool = False, max_iter: int = 200, 
             use_mbh: bool = True, algo_id: str = "compass_search", initial_pop_size: int = 20,
             n_trials: int = 5, log_verbosity: int = 1) -> list[dict] | tuple[list[dict], list[pg.algorithm], list[pg.population], np.ndarray]:
    
    def optimize_single():
    
        prob = pg.problem(problem)
        prob.c_tol = problem.c_tol
        
        if algo_id == "ipopt":
            internal_algo = pg.ipopt()
            internal_algo.set_numeric_option("tol", 1E-1) # Change the relative convergence tolerance
            internal_algo.set_integer_option("max_iter", max_iter) # Change the maximum number of iterations
            # ip.set_numeric_options({}) #})
            
        elif algo_id == "compass_search":
            internal_algo = pg.compass_search(max_fevals=max_iter)
            
        else:
            internal_algo = getattr(pg, algo_id)

        if use_mbh:
            algo = pg.algorithm(
                pg.mbh(internal_algo)
            )
        else:
            algo = pg.algorithm(internal_algo)
            
        algo.set_verbosity(log_verbosity)

        pop = pg.population(prob, initial_pop_size)
        pop = algo.evolve(pop)
        
        op_pt = problem.evaluate(pop.champion_x)
        # if not extra_outputs:
        #     return op_pt
        # else:
        return op_pt, algo, pop, pop.champion_f
        
    # Outer function
    fitness_list: list[float] = []
    algo_list: list = []
    operation_pt_list = []
    pop_list = []
    
    for eval_idx in range(n_trials):
        if log_verbosity > 0:
            logger.info(f"Iteration {eval_idx+1} out of {n_trials}")
        
        op_pt, algo, pop, fitness = optimize_single()
        fitness_list.append(fitness)
        operation_pt_list.append(op_pt)
        algo_list.append(algo)
        pop_list.append(pop)
        
    fitness_list = np.array(fitness_list)
        
    logger.info(f"Variance: {np.var(fitness_list[:, 0]):.3f} | {fitness_list[:, 0]}")
    
    if extra_outputs:
        return operation_pt_list, algo_list, pop_list, fitness_list
    else:
        return operation_pt_list