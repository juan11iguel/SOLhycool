from typing import Optional
from collections.abc import Iterable
import copy
import math
from dataclasses import dataclass, asdict
import pygmo as pg
import numpy as np
from loguru import logger
import pandas as pd

import combined_cooler
import matlab

from solhycool_modeling import EnvironmentVariables, OperationPoint, ModelInputsRange
from solhycool_optimization import RealDecVarsBoxBounds, DecisionVariables

""" Global variables """
# cc_model = combined_cooler.initialize()  # Could we get away initiating this only once at the beginning?

class CombinedCoolerProblem:
    """ Combined cooler problem with two sources of water: a cheaper and a
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
    use_constraints: bool # 
    x_evaluated: list[list[float]]  # Decision variables vector evaluated (i.e. sent to the fitness function)
    fitness_history: list[float]  # Fitness record of decision variables sent to the fitness function
    Vavail0: float  # Available volume of the cheaper water source
    n_evals: int  # Number of evaluations in the prediction horizon
    size_dec_vector: int  # Size of the decision vector
    dec_var_ids: list[str] = ["qc", "Rp", "Rs", "wdc", "wwct"]  # Decision variables ids
    deltaTcv_min: float = 2 # Minimum temperature difference between cooling fluid outlet and vapor (ºC) 
    c_tol_base: list[float] = [0.1, 1e-3, 10]  # Base constraint tolerance values
    c_tol: list[float] = None  # Constraint tolerances
    Qmax: float = 230 # kWth
    model_inputs_range: ModelInputsRange = ModelInputsRange()
    use_multiple_sources: bool = None # Use multiple sources of water
    sample_time: float = None # Sample time (h)
    penalization_factor: float = 0.2 # Penalization factor to apply when flow is circulated on a stoped system (1 would equal doubling the cost)
    
    @property
    def cc_model(self):
        # Lazy loading of cc_model so it's only initialized when used for the first time
        # print("I was called!")
        if not hasattr(self, "_cc_model"):
            self._cc_model = combined_cooler.initialize()
            # print("I was initialized!")
        return self._cc_model
    
    def __deepcopy__(self, memo):
        """Custom deepcopy to ensure `_cc_model` is reinitialized."""
        copied_obj = self.__class__.__new__(self.__class__)
        memo[id(self)] = copied_obj  # Prevent infinite recursion
        
        keys_to_not_copy = ["_cc_model"]
        [setattr(copied_obj, key, copy.deepcopy(value, memo)) for key, value in self.__dict__.items() if key not in keys_to_not_copy]

        return copied_obj
    
    def __getstate__(self):
        """Remove non-picklable attributes before pickling"""
        state = self.__dict__.copy()
        if "_cc_model" in state:
            del state["_cc_model"]  # Remove the MATLAB object before pickling
        return state
    
    def __init__(self, 
                 env_vars: EnvironmentVariables, 
                 store_x: bool = False,
                 store_fitness: bool = False,
                 real_dec_vars_box_bounds: RealDecVarsBoxBounds = RealDecVarsBoxBounds.from_model_inputs_range(),
                 sample_time: int = 1,
                 debug_mode: bool = False,
                 use_constraints: bool = False,
                 ) -> None:
        
        # Validation
        assert self.penalization_factor >= 0, f"Penalization factor needs to be a number greater or equal to zero, not {self.penalization_factor}"
        if np.any(env_vars.Q > self.Qmax):
            logger.warning(f"Asked to cool a load larger than the maximum for the system: {env_vars.Q:} > {self.Qmax}")

        self.real_dec_vars_box_bounds = real_dec_vars_box_bounds
        self.env_vars = env_vars
        self.store_x = store_x
        self.store_fitness = store_fitness
        self.debug_mode = debug_mode
        self.sample_time = sample_time
        self.use_constraints = use_constraints
        
        # Update environment variables to remove Pw data
        self.env_vars.Pw = None
        
        self.Vavail0 = env_vars.Vavail[0]
        self.n_evals: int = len(list(asdict(env_vars).values())[0])
        self.size_dec_vector = len(self.dec_var_ids) * self.n_evals
        self.c_tol = self.c_tol_base * self.n_evals
        
        # Validate range of inputs
        var_ids = ["Tamb", "HR"]
        for var_id in var_ids:
            values = np.asarray(getattr(env_vars, var_id))  # ensure it's an array
            bounds = getattr(self.model_inputs_range, var_id)
            lower, upper = bounds

            # Find values outside the bounds
            out_of_bounds = (values < lower) | (values > upper)

            if np.any(out_of_bounds):
                corrected_values = np.clip(values, lower, upper)
                logger.warning(
                    f"{var_id} contains values outside range {bounds}. "
                    f"Clipping values: original={values[out_of_bounds]}, "
                    f"corrected={corrected_values[out_of_bounds]}"
                )
                setattr(env_vars, var_id, corrected_values)
        
        # Initialize decision vector history
        self.x_evaluated = []
        self.fitness_history = []   
    
    def get_nic(self) -> int:
        if self.use_constraints:
            return len(self.c_tol)
        else:
            return 0
        # return len(self.c_tol) * self.n_evals  # Two inequality constraints per evaluation in the prediction horizon
    
    def decision_vector_to_decision_variables(self, x: np.ndarray[float]) -> DecisionVariables:
        """ Convert decision vector to decision variables """
        dec_var_dict = {}
        for idx, var_id in enumerate(self.dec_var_ids):
            dec_var_dict[var_id] = x[idx*self.n_evals:(idx+1)*self.n_evals]
        
        # return DecisionVariables(
        #     qc=dec_var_dict["qc"],
        #     Rp=np.full((self.n_evals, ), 1.0, dtype=float),
        #     Rs=np.full((self.n_evals, ), 0.0, dtype=float),
        #     wdc=np.full((self.n_evals, ), 0.0, dtype=float),
        #     wwct=dec_var_dict["wwct"]
        # )
        return DecisionVariables(
            qc=dec_var_dict["qc"],
            Rp=dec_var_dict["Rp"],
            Rs=dec_var_dict["Rs"],
            wdc=dec_var_dict["wdc"],
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
        
        Vavail = self.Vavail0  # m³
        ops: list[OperationPoint] = []
        for step_idx in range(self.n_evals):
            dv = dec_vars.dump_at_index(step_idx)
            ev = copy.deepcopy(self.env_vars.dump_at_index(step_idx))
            dv_m = dv.to_matlab()
            ev_m = ev.to_matlab()
            
            _, Cw_lh, detailed = self.cc_model.combined_cooler_model(ev_m.Tamb, ev_m.HR, ev_m.mv, dv_m.qc, dv_m.Rp, dv_m.Rs, dv_m.wdc, dv_m.wwct, ev_m.Tv, nargout=3)
            
            Cw_s1 = min( Cw_lh*self.sample_time, Vavail * 1e3) / self.sample_time
            Cw_s2 = Cw_lh - Cw_s1
            Vavail = max(0, Vavail - Cw_s1*1e-3*self.sample_time)
            # print(f"{ev.Vavail=}")
            
            # Update outputs before creating the operation point
            ev.Vavail = Vavail  # m³
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
        Vavail = self.Vavail0  # m³
        for step_idx in range(self.n_evals):
            dv = dec_vars.dump_at_index(step_idx)
            ev = self.env_vars.dump_at_index(step_idx)
            dv_m = dv.to_matlab()
            ev_m = ev.to_matlab()
            b = self.real_dec_vars_box_bounds

            Ce_kWe, Cw_lh, detailed = self.cc_model.combined_cooler_model(ev_m.Tamb, ev_m.HR, ev_m.mv, dv_m.qc, dv_m.Rp, dv_m.Rs, dv_m.wdc, dv_m.wwct, ev_m.Tv, nargout=3)
            
            Cw_s1 = min( Cw_lh*self.sample_time, Vavail*1e3) / self.sample_time
            Cw_s2 = Cw_lh - Cw_s1
            Vavail = max(0, Vavail-Cw_s1*1e-3*self.sample_time)

            J_ = Ce_kWe * ev.Pe + Cw_s1 * ev.Pw_s1 + Cw_s2 * ev.Pw_s2
            
            # ecs.append(ecs_)
            # ics.extend([
            ics_ = [
                abs( detailed["Tcc_out"] - detailed["Tc_in"] ),          # Tcc,out == Tc,in
                detailed["Tc_out"] - (ev.Tv - self.deltaTcv_min),    # Tc,out < Tv-ΔTc-v,min 
                abs( detailed["Qdc"] + detailed["Qwct"] - detailed["Qc_released"] ), # Qdc + Qwct == Qc
            ]
            
            if self.use_constraints:
                ics.extend(ics_)
            else:
                J_pen = 0
                for idx, (c_tol, ic) in enumerate(zip(self.c_tol_base, ics_)):
                    if ic > c_tol:
                        # Just penalize the same amount times the number of violations
                        J_pen += 1 # self.penalization_factor*J_ #  * (abs(ic-c_tol) / c_tol)
                        # J_pen += self.penalization_factor*J_ * (abs(ic-c_tol) / c_tol)
                        # print(f"[{idx}] Penalizado!: {ic:.2f} > {c_tol:.5f}, penalize={self.penalization_factor*J_ * (abs(ic-c_tol) / c_tol):.2f}")
                J_ += J_pen
            # ])
            # print(J)
            
            # Penalize water circulation on stopped system (w=0)
            if detailed["wdc"] <= b.wdc[0]:
                # qdc should be zero
                # J = J + J * penalization factor / qc_max * qdc
                J_ += self.penalization_factor*J_/b.qc[-1] * detailed["qdc"]
                if self.debug_mode:
                    print(f"Penalizado!: dc {self.penalization_factor*J_/b.qc[-1] * detailed['qdc']}")
            if detailed["wwct"] <= b.wwct[0]:
                # qwct should be zero
                # J = J + J * penalization factor / qc_max * qwct
                J_ += self.penalization_factor*J_/b.qc[-1] * detailed["qwct"]
                if self.debug_mode:
                    print(f"Penalizado!: wct {self.penalization_factor*J_/b.qc[-1] * detailed['qwct']}")
            
            J += J_
            
        self.store_results(fitness=J, x=x)
        
        # print(f"J={J:.2f}, {time.time()-start_time:.2f} s")
        
        return [J, *ecs, *ics]


class CombinedCoolerPathFinderProblem:
    """ Combined cooler problem with two sources of water: a cheaper and a
    more expensive one, with volume restriction on the cheaper one
    
    Two initialization options are available:
    1. A list of DataFrames, each containing the pareto front for a given time 
    step. Then a sample time must be provided and it is assumed that the time 
    steps are evenly spaced.
    2. A pandas Series with a DatetimeIndex, where each value is a DataFrame 
    containing the pareto front for that date. The time dependent components 
    are calculated based on the time between each date in the index, i.e. a variable 
    elapsed time between each step is permitted.
    
    Optimization problem type: receding horizon optimization
    x: decision vector.
    - shape: ( n steps, )
    - structure:
        X = [x[step0], x[step1], ..., x[stepN]]
    - Decision vector components: index of the pareto front to select for each step
    """
    df_paretos: list[pd.DataFrame]  # Pareto fronts for each step
    Vavail0: float
    n_steps: int = None
    elapsed_time_between_steps: Iterable[float] = None  # Elapsed time between each step in hours
    
    def __init__(self, df_paretos: list[pd.DataFrame] | pd.Series, Vavail0: float, sample_time_h: Optional[int] = None) -> None:
        self.Vavail0 = Vavail0
        self.n_steps = len(df_paretos)
        
        if isinstance(df_paretos, pd.Series):
            # must be datetime index
            assert isinstance(df_paretos.index, pd.DatetimeIndex), "The index of the pareto front series must be a DatetimeIndex."
            assert df_paretos.index.is_monotonic_increasing, "The index of the pareto front series must be monotonic increasing."
            
            # Calculate elapsed time between steps
            self.elapsed_time_between_steps = pd.Series(np.diff(df_paretos.index)).dt.total_seconds().div(3600).tolist()
            # Add the last step duration with the same as the previous one
            self.elapsed_time_between_steps.append(self.elapsed_time_between_steps[-1])
        else:
            assert sample_time_h is not None, "If df_paretos is a list of DataFrames, sample_time_h must be provided."
        
            self.elapsed_time_between_steps = [sample_time_h] * (self.n_steps)
        
        # No need for the series index in this case, just the dataframes
        self.df_paretos = df_paretos if not isinstance(df_paretos, pd.Series) else df_paretos.tolist()
        
    def get_nc(self) -> int:
        return 0
    
    def get_nix(self) -> int:
       return self.n_steps 
        
    def get_bounds(self, ) -> tuple[Iterable, Iterable]:
        return ([0] * self.n_steps, [len(df_pareto)-1 for df_pareto in self.df_paretos])
    
    def evaluate(self, ops: list[OperationPoint], update_operation_pts: bool = False) -> float | tuple[float, list[OperationPoint]]:
        J = 0
        Vavail = self.Vavail0  # m³
        for op_idx, op in enumerate(ops):
            elapsed_time = self.elapsed_time_between_steps[op_idx]

            # Ce_kWe, Cw_lh, _ = self.cc_model.combined_cooler_model(op.Tamb, op.HR, op.mv, op.qc, op.Rp, op.Rs, op.wdc, op.wwct, op.Tv, nargout=3)
            
            Ce_kWe, Cw_lh = op.Ce, op.Cw
            
            Cw_s1 = min( Cw_lh*elapsed_time, Vavail*1e3 ) / elapsed_time
            Cw_s2 = Cw_lh - Cw_s1
            Vavail = Vavail-(Cw_s1*1e-3*elapsed_time)

            J += Ce_kWe * op.Pe + Cw_s1 * op.Pw_s1 + Cw_s2 * op.Pw_s2
            
            if update_operation_pts:
                op.Cw_s1 = Cw_s1
                op.Cw_s2 = Cw_s2
                op.Vavail = Vavail
                # Nullify so they are re-calculated
                op.Vavail_s1 = None
                op.Jw_s1 = None
                op.Jw_s2 = None
                op.J = None
                ops[op_idx] = OperationPoint(**asdict(op))
            
        if update_operation_pts:
            return J, ops
        return J
    
    def fitness(self, x: np.ndarray[int], ) -> float:
        
        ops = [self.df_paretos[step_idx].iloc[int(selected_idx)] for step_idx, selected_idx in enumerate(x)]
            
        # assert Vavail >= 0, f"Vavail < 0: {Vavail} m³"
            
        return [self.evaluate(ops)]
    
    

@dataclass
class AlgoParams:
    algo_id: str = "sga"
    max_n_obj_fun_evals: int = 20_000
    max_n_logs: int = 300
    pop_size: int = 80
    # Vavail0: list[float] = None
    
    params_dict: dict = None
    log_verbosity: int = None
    gen: int = None

    def __post_init__(self, ):

        if self.algo_id in ["gaco", "sga", "pso_gen"]:
            self.gen = self.max_n_obj_fun_evals // self.pop_size
            self.params_dict = {
                "gen": self.gen,
            }
        elif self.algo_id == "simulated_annealing":
            self.gen = self.max_n_obj_fun_evals // self.pop_size
            self.params_dict = {
                "bin_size": self.pop_size,
                "n_T_adj": self.gen
            }
        else:
            self.pop_size = 1
            self.gen = self.max_n_obj_fun_evals
            self.params_dict = { "gen": self.max_n_obj_fun_evals // self.pop_size }
        
        if self.log_verbosity is None:
            self.log_verbosity = math.ceil( self.gen / self.max_n_logs)
    # def add_water_available_from_env(self, df_env: pd.DataFrame) -> None:
    #     self.Vavail0 = [df_env.loc[date_str].iloc[0]["Vavail_m3"] for date_str in self.date_strs]