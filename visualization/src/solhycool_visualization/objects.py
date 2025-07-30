from dataclasses import dataclass
from typing import Literal
import plotly.graph_objects as go
from pathlib import Path
from loguru import logger

from phd_visualizations.optimization import plot_obj_scape_comp_1d
from phd_visualizations import save_figure

from solhycool_optimization import DayResults
from solhycool_optimization.problems.horizon import AlgoParams
from solhycool_visualization.optimization import plot_pareto_front
from solhycool_visualization.operation import plot_results

@dataclass
class HorizonResultsVisualizer:
    """
    Class to visualize the results of the horizon optimization.
    """
    day_results: DayResults
    results_plot_config: dict
    
    def plot_pareto_fronts(self) -> list[go.Figure]:
        """
        Plot the Pareto front of the optimization results.
        """
        title_text=f"<b>Pareto front for</b> {self.day_results.index[0].strftime('%Y%m%d %H:%M')} - {self.day_results.index[-1].strftime('%Y%m%d %H:%M')}"
        margin=dict(t=50, b=5, l=5, r=5)
        ops_list=self.day_results.df_paretos
        full_legend=True,
        showlegend=True
        objective_keys=('Cw', 'Ce')

        figs = []
        
        figs.append(
            plot_pareto_front(
                ops_list=ops_list,
                objective_keys=objective_keys,
                mode="overlap",
                showlegend=showlegend,
                full_legend=full_legend,
                title_text=title_text,
                margin=margin,
                
                highlight_idx=0,
            )
        )
        
        figs.append(
            plot_pareto_front(
                ops_list=ops_list,
                objective_keys=objective_keys,
                mode="overlap",
                showlegend=showlegend,
                full_legend=full_legend,
                title_text=title_text,
                margin=margin,
            )
        )
        
        figs.append(
            plot_pareto_front(
                ops_list=ops_list,
                objective_keys=objective_keys,
                mode="side_by_side",
                showlegend=showlegend,
                full_legend=full_legend,
                title_text=title_text,
                margin=margin,
                
                selected_idxs=self.day_results.selected_pareto_idxs,
            )
        )
        
        return figs
        
    def plot_fitness_history(self) -> go.Figure | None:
        """
        Plot the fitness history of the optimization results.
        """
        if self.day_results.fitness_history is None or len(self.day_results.fitness_history) == 0:
            return
        
        return plot_obj_scape_comp_1d(
            fitness_history_list=[self.day_results.fitness_history], 
            algo_ids=[AlgoParams.algo_id],
            title_text=f"<b>Fitness Evolution</b><br>Path selection subproblem {self.day_results.index[0].strftime('%Y%m%d')}"
        )
        
    def plot_results(self) -> go.Figure:
        """
        Plot the timeseries results of the optimization.
        """
        return plot_results(self.results_plot_config, day_results=self.day_results, template="plotly_white", comp_trace_labels=None)
        
    def generate_all(
        self,
        output_path: Path, 
        formats: list[Literal["png", "html", "svg"]] = ["png", "html"]
    ) -> None:
        """
        Generate all visualizations and save them to the output path.
        """
        for idx, fig in enumerate(self.plot_pareto_fronts()):
            save_figure(
                fig,
                figure_name=f"pareto_front_{idx}",
                figure_path=output_path,
                formats=formats,
            )
        fig = self.plot_fitness_history()
        if fig:
            save_figure(
                fig,
                figure_name="fitness_history_path_selection",
                figure_path=output_path,
                formats=formats,
            )
            
        save_figure(
            self.plot_results(),
            figure_name="results",
            figure_path=output_path,
            formats=formats,
        )
        
        logger.info(f"Visualizations saved to {output_path}")