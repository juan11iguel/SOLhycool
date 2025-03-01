from collections.abc import Iterable
from dataclasses import asdict
import pygmo as pg
import numpy as np
from loguru import logger
import pandas as pd
import matlab

import combined_cooler_model

from solhycool_modeling import EnvironmentVariables, OperationPoint
from solhycool_optimization import (RealDecVarsBoxBounds,
                                    DecisionVariables)
""" Global variables """
cc_model = combined_cooler_model.initialize()  # Could we get away initiating this only once at the beginning?


class WctRestrictedProblem:
    """ Wet cooling tower problem with two sources of water: a cheaper and a
    more expensive one, with volume restriction on the cheaper one 
    
    Optimization problem type: receding horizon optimization
    
    x: decision vector.
    - shape: ( n inputs x n horizon,  )
    - structure:
        X = [x[input0,step0] x[input0,step1],, ..., x[input0,stepN], ..., x[inputN,step0], x[inputN,step1], ..., x[inputN,stepN]]
    
    - Decision vector components: See `DecisionVariables`  
    - Environment variables: See `EnvironmentVariables`
    """

    env_vars: EnvironmentVariables  # Environment variables
    store_x: bool # Store decision variables
    store_fitness: bool  # Store fitness values
    real_dec_vars_box_bounds: RealDecVarsBoxBounds
    x_evaluated: list[list[float]]  # Decision variables vector evaluated (i.e. sent to the fitness function)
    fitness_history: list[float]  # Fitness record of decision variables sent to the fitness function
    sample_time: float  # Sample time, hours
    Vavail0: float  # Available volume of the cheaper water source
    dec_var_ids: list[str] = ["qc", "wwct"]  # Decision variables ids
    
    n_evals: int  # Number of evaluations in the prediction horizon
    size_dec_vector: int  # Size of the decision vector
    
    deltaTcv_min: float = 2 # Minimum temperature difference between cooling fluid outlet and vapor (ºC) 
    # c_tol: list[float] = [0.5, 0.5] # Constraint tolerances (ºC, ºC)
    c_tol: float = 0.5  # Constraint tolerances (ºC)
    
    Qmax: float = 150 # kWth
    
    def __init__(self, 
                 env_vars: EnvironmentVariables, 
                 store_x: bool = False,
                 store_fitness: bool = False,
                 real_dec_vars_box_bounds: RealDecVarsBoxBounds = RealDecVarsBoxBounds(),
                 sample_time: int = 1,
                 debug_mode: bool = False,
                 ) -> None:
        
        self.real_dec_vars_box_bounds = real_dec_vars_box_bounds
        self.env_vars = env_vars
        # Update environment variables to remove Pw data
        self.env_vars.Pw = None
        self.store_x = store_x
        self.store_fitness = store_fitness
        self.debug_mode = debug_mode
        self.sample_time = sample_time
        
        if np.any(env_vars.Q > self.Qmax):
            logger.warning(f"Asked to cool a load larger than the maximum for the system: {env_vars.Q:} > {self.Qmax}")
            
        self.Vavail0 = env_vars.Vavail[0]
        self.n_evals: int = len(list(asdict(env_vars).values())[0])
        self.size_dec_vector = len(self.dec_var_ids) * self.n_evals 
        
        # Initialize decision vector history
        self.x_evaluated = []
        self.fitness_history = []   
    
    def get_nic(self) -> int:
        return 2 * self.n_evals  # Two inequality constraints per evaluation in the prediction horizon
    
    def decision_vector_to_decision_variables(self, x: np.ndarray[float]) -> DecisionVariables:
        """ Convert decision vector to decision variables """
        dec_var_dict = {}
        for idx, var_id in enumerate(self.dec_var_ids):
            dec_var_dict[var_id] = x[idx*self.n_evals:(idx+1)*self.n_evals]
        
        return DecisionVariables(
            qc=dec_var_dict["qc"],
            Rp=np.full((self.n_evals, ), 1.0, dtype=float),
            Rs=np.full((self.n_evals, ), 0.0, dtype=float),
            wdc=np.full((self.n_evals, ), 0.0, dtype=float),
            wwct=dec_var_dict["wwct"]
        )
        
    def store_results(self, fitness: float, x: np.ndarray[float]) -> None:
        if self.store_x:
            self.x_evaluated.append(x.tolist())
        if self.store_fitness:
            self.fitness_history.append(fitness)
            
    def gradient(self, x) -> np.ndarray[float]:
        return pg.estimate_gradient(lambda x: self.fitness(x), x) # we here use the low precision gradient
    
    def get_bounds(self, ) -> tuple[Iterable, Iterable]:
        
        bounds = [getattr(self.real_dec_vars_box_bounds, dec_var_id) for dec_var_id in self.dec_var_ids]
        lb = [[bound[0]]*self.n_evals for bound in bounds]
        ub = [[bound[1]]*self.n_evals for bound in bounds]

        return np.concatenate(lb), np.concatenate(ub)

    def evaluate(self, x: np.ndarray[float], return_dataframe: bool = False) -> list[OperationPoint] | pd.DataFrame:
        """ Evaluate the decision vector and return an operation point """
        
        dec_vars = self.decision_vector_to_decision_variables(x)
        
        Vavail = self.Vavail0 * 1e3  # m³ -> l
        ops: list[OperationPoint] = []
        for step_idx in range(self.n_evals):
            dv = dec_vars.dump_at_index(step_idx)
            ev = self.env_vars.dump_at_index(step_idx)
            dv_m = dv.to_matlab()
            ev_m = ev.to_matlab()
            
            _, Cw_lh, detailed = cc_model.combined_cooler_model(ev_m.Tamb, ev_m.HR, ev_m.mv, dv_m.qc, dv_m.Rp, dv_m.Rs, dv_m.wdc, dv_m.wwct, ev_m.Tv, nargout=3)
            
            Cw_s1 = min( Cw_lh*self.sample_time, Vavail) / self.sample_time
            Cw_s2 = Cw_lh - Cw_s1
            Vavail = Vavail - Cw_s1*self.sample_time
            # print(f"{ev.Vavail=}")
            
            # Update outputs before creating the operation point
            ev.Vavail = Vavail / 1e3  # l -> m³
            detailed.update({"Cw_s1": Cw_s1, "Cw_s2": Cw_s2})

            ops.append(OperationPoint.from_multiple_sources(detailed, env_vars=ev))
            
        if return_dataframe:
            return pd.DataFrame([asdict(op) for op in ops])
        return ops
    
    def fitness(self, x: np.ndarray[float], ) -> list[float]:
        
        dec_vars = self.decision_vector_to_decision_variables(x)
        
        # Every field in the objects should be a numpy array with values for each time step
        # in the prediction horizon
        
        J = 0
        ecs = []
        ics = []
        Vavail = self.Vavail0 * 1e3  # m³ -> l
        for step_idx in range(self.n_evals):
            dv = dec_vars.dump_at_index(step_idx)
            ev = self.env_vars.dump_at_index(step_idx)
            dv_m = dv.to_matlab()
            ev_m = ev.to_matlab()
            
            Ce_kWe, Cw_lh, detailed = cc_model.combined_cooler_model(ev_m.Tamb, ev_m.HR, ev_m.mv, dv_m.qc, dv_m.Rp, dv_m.Rs, dv_m.wdc, dv_m.wwct, ev_m.Tv, nargout=3)
            
            Cw_s1 = min( max(Cw_lh, 0)*self.sample_time, Vavail) / self.sample_time
            Cw_s2 = Cw_lh - Cw_s1
            Vavail = Vavail - Cw_s1*self.sample_time

            J += Ce_kWe * ev.Pe + Cw_s1 * ev.Pw_s1 + Cw_s2 * ev.Pw_s2
            # ecs.append(ecs_)
            ics.extend([
                abs( detailed["Tcc_out"] - detailed["Tc_in"] ),
                detailed["Tc_out"] - ev.Tv - self.deltaTcv_min,
            ])
        # print(J)
            
        self.store_results(fitness=J, x=x)
        return [J, *ecs, *ics]