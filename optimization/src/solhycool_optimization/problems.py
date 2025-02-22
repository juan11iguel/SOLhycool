from collections.abc import Iterable
import numpy as np
from abc import ABC, abstractmethod
import pygmo as pg
import combined_cooler_model
import matlab

from solhycool_optimization import (RealDecVarsBoxBounds, 
                                    EnvironmentVariables, 
                                    DecisionVariables)


cc_model = combined_cooler_model.initialize() # Could we get away initiating this only once at the beginning?

class BaseProblem(ABC):
    env_vars: EnvironmentVariables # Environment variables
    store_x: bool # Store decision variables
    store_fitness: bool # Store fitness values
    real_dec_vars_box_bounds: RealDecVarsBoxBounds
    x_evaluated: list[list[float]] # Decision variables vector evaluated (i.e. sent to the fitness function)
    fitness_history: list[float] # Fitness record of decision variables sent to the fitness function
    dec_var_ids: list[str] # Decision variables ids
    size_dec_vector: int # Size of the decision vector
    c_tol: float = 2.3 # Constraint tolerance (ºC)
    
    @abstractmethod
    def get_nic(self) -> int:
        pass
    
    @abstractmethod
    def gradient(self, x) -> np.ndarray[float]:
        pass
    
    @abstractmethod
    def decision_vector_to_decision_variables(self, x: np.ndarray[float]) -> DecisionVariables:
        pass
    
    @abstractmethod
    def get_bounds(self, ) -> tuple[Iterable, Iterable]:
        pass
    
    @abstractmethod
    def fitness(self, x: np.ndarray[float], ) -> list[float]:
        pass
    
    @abstractmethod
    def evaluate(self, x: np.ndarray[float]) -> dict:
        pass

class DCProblem(BaseProblem):
    dec_var_ids: list[str] = ["qc", "wdc"] # Decision variables ids
    size_dec_vector: int = 2 # Size of the decision vector
    c_tol: float = 2.3 # Constraint tolerance (ºC)
    
    def __init__(self, 
                 env_vars: EnvironmentVariables, 
                 store_x: bool = False,
                 store_fitness: bool = False,
                 real_dec_vars_box_bounds: RealDecVarsBoxBounds = RealDecVarsBoxBounds(),
                 debug_mode: bool = False,
                ) -> None:
        
        self.real_dec_vars_box_bounds = real_dec_vars_box_bounds
        self.env_vars = env_vars
        self.store_x = store_x
        self.store_fitness = store_fitness
        self.debug_mode = debug_mode
        
        # self.cc_model.warning('off', 'all', nargout=0)  # Turns off all warnings
    
    def get_nic(self) -> int:
        return 1
    
    def gradient(self, x) -> np.ndarray[float]:
        return pg.estimate_gradient(lambda x: self.fitness(x), x) # we here use the low precision gradient
    
    def decision_vector_to_decision_variables(self, x: np.ndarray[float]) -> DecisionVariables:
        
        return DecisionVariables(
            qc=matlab.double([x[0]]),
            Rp=matlab.double([0.0]),
            Rs=matlab.double([0.0]),
            wdc=matlab.double([x[1]]),
            wwct=matlab.double([0])
        )
    
    def get_bounds(self, ) -> tuple[Iterable, Iterable]:
        
        lb = [self.real_dec_vars_box_bounds.qc[0], self.real_dec_vars_box_bounds.wdc[0]]
        ub = [self.real_dec_vars_box_bounds.qc[1], self.real_dec_vars_box_bounds.wdc[1]]
        
        return lb, ub
    
    def fitness(self, x: np.ndarray[float], ) -> list[float]:
        
        dv = self.decision_vector_to_decision_variables(x)
        ev = self.env_vars.to_matlab()

        Ce_kWe, _, detailed = cc_model.combined_cooler_model(ev.Tamb, ev.HR, ev.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, dv.wwct, ev.Tv, nargout=3)
        
        # Calculate thermal power using Tc_in and Tc_out, and return difference with the setpoint
        # Pth = 4.186 * detailed["qc"][0][0]/3600 * (detailed["Tc_in"][0][0] - detailed["Tc_out"][0][0])
        
        # Store decision vector and fitness value
        if self.store_x:
            self.x_evaluated.append(x.tolist())
        if self.store_fitness:
            self.fitness_history.append(Ce_kWe)
   
        outputs = [Ce_kWe, abs(detailed["Tcc_out"] - detailed["Tc_in"])]
        if self.debug_mode:
            print(outputs)
            
        return outputs
        # return [Ce_kWe, abs(detailed["Pth"] - Pth)]
        # return [Ce_kWe, abs(detailed["Tv"] - ev.Tv[0][0])]
        
    def evaluate(self, x: np.ndarray[float]) -> dict:
        
        dv = self.decision_vector_to_decision_variables(x)
        ev = self.env_vars.to_matlab()
        _, _, detailed = cc_model.combined_cooler_model(ev.Tamb, ev.HR, ev.mv, dv.qc, dv.Rp, dv.Rs, dv.wdc, dv.wwct, ev.Tv, nargout=3)
        
        return detailed