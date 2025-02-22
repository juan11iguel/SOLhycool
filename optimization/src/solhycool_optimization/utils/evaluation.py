import pygmo as pg
from solhycool_optimization.problems import BaseProblem

def optimize(problem: BaseProblem, extra_outputs: bool = False) -> dict | tuple[dict, pg.algorithm, pg.population]:
    prob = pg.problem(problem)
    prob.c_tol = problem.c_tol
    ip = pg.ipopt()
    ip.set_numeric_option("tol", 1E-1) # Change the relative convergence tolerance
    ip.set_integer_option("max_iter", 200) # Change the maximum number of iterations
    # ip.set_numeric_options({}) #})

    algo = pg.algorithm(ip)
    algo.set_verbosity(1)

    pop = pg.population(prob, 1)
    pop = algo.evolve(pop)
    
    
    detailed = problem.evaluate(pop.champion_x)
    if not extra_outputs:
        return detailed
    else:
        return detailed, algo, pop