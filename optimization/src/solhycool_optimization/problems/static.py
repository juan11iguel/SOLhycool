from abc import ABC, abstractmethod
from collections.abc import Iterable
import copy
import numpy as np
import pygmo as pg
from loguru import logger

import combined_cooler_model
import matlab

from solhycool_modeling import EnvironmentVariables, OperationPoint, ModelInputsRange
from solhycool_optimization import DecisionVariables, RealDecVarsBoxBounds


""" Global variables """
# cc_model = combined_cooler_model.initialize()
# def initialize_matlab_model():
#     return combined_cooler_model.initialize()  # Could we get away initiating this only once at the beginning?


class BaseProblem(ABC):
    env_vars: EnvironmentVariables  # Environment variables
    store_x: bool # Store decision variables
    store_fitness: bool  # Store fitness values
    real_dec_vars_box_bounds: RealDecVarsBoxBounds
    x_evaluated: list[list[float]] # Decision variables vector evaluated (i.e. sent to the fitness function)
    fitness_history: list[float] # Fitness record of decision variables sent to the fitness function
    dec_var_ids: list[str] # Decision variables ids
    size_dec_vector: int # Size of the decision vector
    deltaTcv_min: float = 2 # Minimum temperature difference between cooling fluid outlet and vapor (ºC) 
    c_tol: list[float] = 0.5 # [0.5, 0.5] # Constraint tolerances (ºC, ºC)
    Qmax: float = 150 # kWth
    model_inputs_range: ModelInputsRange = ModelInputsRange()
    
    @property
    def cc_model(self):
        # Lazy loading of cc_model so it's only initialized when used for the first time
        # print("I was called!")
        if not hasattr(self, "_cc_model"):
            self._cc_model = combined_cooler_model.initialize()
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
                 debug_mode: bool = False,
                ) -> None:

        self.real_dec_vars_box_bounds = real_dec_vars_box_bounds
        self.env_vars = env_vars
        self.store_x = store_x
        self.store_fitness = store_fitness
        self.debug_mode = debug_mode
        
        # self.cc_model = combined_cooler_model.initialize()
        
        # Initialize decision vector history
        self.x_evaluated = []
        self.fitness_history = []

        if env_vars.Q > self.Qmax:
            logger.warning(f"Asked to cool a load larger than the maximum for the system: {env_vars.Q:.2f} > {self.Qmax}")
            
        # Validate range of inputs
        var_ids = ["Tamb", "HR"]
        for var_id in var_ids:
            value = getattr(env_vars, var_id)
            bounds = getattr(self.model_inputs_range, var_id)
            if value > bounds[1] or value < bounds[0]:
                new_value = max(min(bounds[1], value), bounds[0])
                logger.warning(f"{var_id}={value} outside range: {bounds}, setting to: {new_value}")
                setattr(env_vars, var_id, new_value)
            
        
        # TODO: Add a flag to operation point so that the output from the optimizer can be analysed to check for unfeasible operation
        # If found, set the flat to some value so it's easy to identify points where there is no feasible solution

    @abstractmethod
    def get_nic(self) -> int:
        pass

    def gradient(self, x) -> np.ndarray[float]:
        return pg.estimate_gradient(lambda x: self.fitness(x), x) # we here use the low precision gradient

    @abstractmethod
    def decision_vector_to_decision_variables(self, x: np.ndarray[float]) -> DecisionVariables:
        pass

    def get_bounds_static_problem(self) -> tuple[Iterable, Iterable]:
        """ Returns bounds for the decision variables when the optimization is static.
        That is, there is no prediction horizon and thus the decision vector only contains
        a single element per decision variable """

        bounds = [getattr(self.real_dec_vars_box_bounds, dec_var_id) for dec_var_id in self.dec_var_ids]
        lb = [bound[0] for bound in bounds]
        ub = [bound[1] for bound in bounds]

        return lb, ub

    @abstractmethod
    def get_bounds(self, ) -> tuple[Iterable, Iterable]:
        pass

    @abstractmethod
    def fitness(self, x: np.ndarray[float], ) -> list[float]:
        pass

    def evaluate_static_problem(self, x: np.ndarray[float]) -> OperationPoint:

        dv = self.decision_vector_to_decision_variables(x)
        ev = self.env_vars.to_matlab()
        
        _, _, detailed = self.cc_model.combined_cooler_model(ev.Tamb, ev.HR, ev.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, dv.wwct, ev.Tv, nargout=3)

        return OperationPoint.from_multiple_sources(detailed, env_vars=self.env_vars)

    @abstractmethod
    def evaluate(self, x: np.ndarray[float]) -> dict:
        pass

    def store_results(self, fitness: float, x: np.ndarray[float]) -> None:
        if self.store_x:
            self.x_evaluated.append(x.tolist())
        if self.store_fitness:
            self.fitness_history.append(fitness)


class DcProblem(BaseProblem):
    """  
    Dry cooler problem 

    Optimization problem type: static optimization 
    """
    dec_var_ids: list[str] = ["qc", "wdc"] # Decision variables ids
    size_dec_vector: int = 2 # Size of the decision vector

    def __init__(self,
                 env_vars: EnvironmentVariables,
                 store_x: bool = False,
                 store_fitness: bool = False,
                 real_dec_vars_box_bounds: RealDecVarsBoxBounds = RealDecVarsBoxBounds.from_model_inputs_range(),
                 debug_mode: bool = False,
                 ) -> None:

        super().__init__(
            env_vars=env_vars,
            store_x=store_x,
            store_fitness=store_fitness,
            real_dec_vars_box_bounds=real_dec_vars_box_bounds,
            debug_mode=debug_mode,
        )

        # self.initialize_matlab_model().warning('off', 'all', nargout=0)  # Turns off all warnings

    # def get_nec(self) -> int:
    #     return 1

    def get_nic(self) -> int:
        return 5

    def decision_vector_to_decision_variables(self, x: np.ndarray[float]) -> DecisionVariables:
        # TODO: Do not always convert to matlab
        return DecisionVariables(
            qc=matlab.double([x[0]]),
            Rp=matlab.double([0.0]),
            Rs=matlab.double([0.0]),
            wdc=matlab.double([x[1]]),
            wwct=matlab.double([0])
        )

    def get_bounds(self, ) -> tuple[Iterable, Iterable]:
       return self.get_bounds_static_problem()

    def fitness(self, x: np.ndarray[float], ) -> list[float]:

        dv = self.decision_vector_to_decision_variables(x)
        ev = self.env_vars.to_matlab()

        Ce_kWe, _, detailed = self.cc_model.combined_cooler_model(ev.Tamb, ev.HR, ev.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, dv.wwct, ev.Tv, nargout=3)

        ecs = [
        #     detailed["Tcc_out"] - detailed["Tc_in"],
        ]
        ics = [
            abs( detailed["Tcc_out"] - detailed["Tc_in"] ),        # Tcc,out == Tc,in
            detailed["Tc_out"] - ev.Tv[0][0] - self.deltaTcv_min,  # Tc,out < Tv-ΔTc-v,min 
            detailed["Tdc_in"] - self.model_inputs_range.Tdc_in[1],# Tdc < Tdc,max
            self.model_inputs_range.Tdc_in[0] - detailed["Tdc_in"],# Tdc > Tdc,min
            detailed["Tdc_out"]+1 - detailed["Tdc_in"]             # Tdc,in > Tdc,out+1
        ]
        outputs = [Ce_kWe, *ecs, *ics]

        if self.debug_mode:
            print(outputs)
        # Store decision vector and fitness value
        self.store_results(fitness=Ce_kWe, x=x)

        return outputs

    def evaluate(self, x: np.ndarray[float]) -> OperationPoint:
        return self.evaluate_static_problem(x)


class WctProblem(BaseProblem):
    """
    Wet cooling tower problem with no water consumption restriction
    and only one source of water

    Optimization problem type: static optimization
    """

    dec_var_ids: list[str] = ["qc", "wwct"] # Decision variables ids
    size_dec_vector: int = 2 # Size of the decision vector

    def __init__(self,
                 env_vars: EnvironmentVariables,
                 store_x: bool = False,
                 store_fitness: bool = False,
                 real_dec_vars_box_bounds: RealDecVarsBoxBounds = RealDecVarsBoxBounds.from_model_inputs_range(),
                 debug_mode: bool = False,
                ) -> None:

        super().__init__(
            env_vars = env_vars,
            store_x = store_x,
            store_fitness = store_fitness,
            real_dec_vars_box_bounds = real_dec_vars_box_bounds,
            debug_mode = debug_mode,
        )

    # def get_nec(self) -> int:
    #     return 1

    def get_nic(self) -> int:
        return 5

    def decision_vector_to_decision_variables(self, x: np.ndarray[float]) -> DecisionVariables:

        return DecisionVariables(
            qc=matlab.double([x[0]]),
            Rp=matlab.double([1.0]),
            Rs=matlab.double([0.0]),
            wdc=matlab.double([0.0]),
            wwct=matlab.double([x[1]])
        )

    def get_bounds(self, ) -> tuple[Iterable, Iterable]:
        return self.get_bounds_static_problem()

    def evaluate(self, x: np.ndarray[float]) -> OperationPoint:
        return self.evaluate_static_problem(x)

    def fitness(self, x: np.ndarray[float], ) -> list[float]:

        dv = self.decision_vector_to_decision_variables(x)
        ev = self.env_vars.to_matlab()

        Ce_kWe, Cw_lh, detailed = self.cc_model.combined_cooler_model(ev.Tamb, ev.HR, ev.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, dv.wwct, ev.Tv, nargout=3)

        ecs = [
        #     detailed["Tcc_out"] - detailed["Tc_in"],
        ]
        ics = [
            abs( detailed["Tcc_out"] - detailed["Tc_in"] ),          # Tcc,out == Tc,in
            detailed["Tc_out"] - ev.Tv[0][0] - self.deltaTcv_min,    # Tc,out < Tv-ΔTc-v,min 
            detailed["Twct_in"] - self.model_inputs_range.Twct_in[1],# Twct,in < Twct,in,,max
            self.model_inputs_range.Twct_in[0] - detailed["Twct_in"],# Twct,in > Twct,in,min
            detailed["Twct_out"]+1 - detailed["Twct_in"]               # Twct,in > Twct,out+1
        ]

        J = Ce_kWe * ev.Pe[0][0] + Cw_lh * ev.Pw[0][0] # u.m./l
        outputs = [J, *ecs, *ics]

        self.store_results(fitness=J, x=x)

        if self.debug_mode:
            print(f"{Ce_kWe=:.2f} x {ev.Pe[0][0]=:.3f} + {Cw_lh=:.2f} x {ev.Pw[0][0]=:.3f} = {J:.2f} | {ics=}")

        return outputs