from dataclasses import dataclass
from typing import Literal
import plotly.graph_objects as go
from pathlib import Path
from loguru import logger

from phd_visualizations import save_figure
from phd_visualizations.optimization import plot_obj_scape_comp_1d
from phd_visualizations.test_timeseries import experimental_results_plot

from solhycool_optimization import HorizonResults, AlgoParamsHorizon as AlgoParams
from solhycool_visualization.optimization import plot_pareto_front
from solhycool_visualization.operation import plot_results
from solhycool_visualization.analysis import year_pie_plot

@dataclass
class HorizonResultsVisualizer:
    """
    Class to visualize the results of the horizon optimization.
    """
    day_results: HorizonResults
    results_plot_config: dict
    output_path: Path | None = None
    
    def __post_init__(self):
        if isinstance(self.results_plot_config, Path):
            import hjson
            self.results_plot_config = hjson.loads(self.results_plot_config.read_text())
            
        if self.output_path is not None:
            self.output_path.mkdir(parents=True, exist_ok=True)
    
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
        
    def plot_results(self, save: bool = False) -> go.Figure:
        """
        Plot the timeseries results of the optimization.
        """
        return plot_results(
            self.results_plot_config, 
            day_results=self.day_results, 
            template="plotly_white", 
            comp_trace_labels=None
        )
    
    def plot_year_overview(self, save: bool = False) -> go.Figure:
        
        df_year = self.day_results.df_results.copy()
        df_year.drop("Qc_transfered", inplace=True, axis=1)
        indexer = df_year["Qc_released"] > 0
        df_year = df_year[indexer].mean()
        
        fig = year_pie_plot(df_year, )
        
        if save:
            if self.output_path is not None:
                save_figure(
                    fig,
                    figure_name="year_overview",
                    figure_path=self.output_path,
                    formats=["png", "html"],
                )
                logger.info(f"Year overview saved to {self.output_path}")
            else:
                logger.warning("Output path is not set. Year overview not saved.")
        
        return fig
    
    def visualize_resampled(self, plot_config: dict,) -> go.Figure:
        """
        Resample the dataframe and visualize the results.
        """
        # Resample results monthly
        df = self.day_results.df_results.copy()
        
        df_numeric = df.select_dtypes(include=['number'])  # Keeps int, float, complex
        df_resampled = df_numeric.resample("SME").mean()

        # plot_config = hjson.load(open(data_path / "plot_config_year.hjson"))
        plot_config["subtitle"] = "Evaluation results" # for {results_path.parts[-2].replace('_', ' ')}

        # Move contents of load conditions to cooling power and remove it
        plot_config["plots"]["cooling_power_distribution"]["ylims_left"] = [0,250]
        plot_config["plots"]["cooling_power_distribution"]["traces_right"] = plot_config["plots"]["load_conditions"]["traces_right"]
        plot_config["plots"]["cooling_power_distribution"].update({param_id: plot_config["plots"]["load_conditions"][param_id] for param_id in ["ylabels_right", "ylims_right"]})
        plot_config["plots"].pop("load_conditions")

        return experimental_results_plot(
            plot_config, 
            df=df_resampled,
            resample=False,
        )
        
    def generate_all(
        self,
        output_path: Path | None = None, 
        formats: list[Literal["png", "html", "svg"]] = ["png", "html"]
    ) -> None:
        """
        Generate all visualizations and save them to the output path.
        """
        
        if output_path is None:
            if self.output_path is None:
                raise ValueError("Output path must be specified.")
            output_path = self.output_path
        output_path.mkdir(parents=True, exist_ok=True)
        
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