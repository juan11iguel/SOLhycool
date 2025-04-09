from collections.abc import Iterable
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from phd_visualizations.constants import plt_colors, dash_types
from loguru import logger


def visualize_solutions_distribution(fitness_list: Iterable,  fitness_units: str = "kWe", **kwargs) -> go.Figure:
    # Create a histogram of the fitness_list
    fig = px.violin(fitness_list, box=True, # draw box plot inside the violin
                    points='all', # can be 'outliers', or False
                    # side="negative" # <- only available in the go.Violin object
                )
    
    kwargs.setdefault("title", f"<b>Distribution of solutions</b><br>Variance: {np.var(fitness_list):.3f}")
    kwargs.setdefault("xaxis_title", "Fitness",)
    fig.update_layout(
        yaxis_title = fitness_units,
        **kwargs,
    )
    
    return fig

def plot_obj_scape_comp_1d(fitness_history_list: list[np.ndarray[float]], algo_ids: list[str], **kwargs) -> go.Figure:
    logger.warning("plot_obj_scape_comp_1d is deprecated, use the one from phd_visualizations instead")
    
    assert len(fitness_history_list) == len(algo_ids), "fitness_history_list and algo_ids should have the same length"
    
    # First create the base plot calling plot_obj_space_1d_no_animation
    fig = plot_obj_space_1d_no_animation(fitness_history_list[0], algo_id=algo_ids[0])
    
    # And then add the other fitness histories
    for algo_id, fitness_history in zip(algo_ids[1:], fitness_history_list[1:]):
        avg_fitness = [np.mean(x) for x in fitness_history]
        generation = np.arange(len(fitness_history))
        
        fig.add_trace(go.Scatter(x=generation, y=avg_fitness, mode="lines", name=algo_id))
        
    fig.update_layout(**kwargs)
    
    return fig


def plot_algo_comparison(results: list[dict], **kwargs) -> go.Figure:
        
    rows, cols = len(results), 2

    # Create the subplot layout
    combined_fig = make_subplots(rows=rows, cols=cols, 
                                row_titles=np.arange(len(results)).tolist(),#[f"{dt:%h}" for dt in df_.index],
                                column_titles=["Fitness evolution", "Solutions distribution"],
                                shared_xaxes=True)

    algo_ids = list(set([values["algo_id"] for values in results[0].values()]))
    avg_fitness_per_algo = {algo_id: [] for algo_id in algo_ids}
    avg_fitness_per_alt = {cs_id: [] for cs_id in results[0].keys()}

    # Loop through and add traces
    for idx in range(len(results)): # len(results)
        result = results[idx]
        r = idx+1
        
        df_aux = pd.DataFrame.from_dict(result, orient='index')
        df_aux.reset_index(inplace=True)
        df_aux.rename(columns={'index': 'cs_id'}, inplace=True)
        
        # algo_ids = list(df["algo_id"].unique())
        for algo_id in algo_ids:
            avg_fitness_per_algo[algo_id].append(df_aux[df_aux["algo_id"]==algo_id]["avg_fitness"].values)
        for _, row in df_aux.iterrows():
            avg_fitness_per_alt[row["cs_id"]].append(row["avg_fitness"])
            
        # Solutions distribution
        fig = px.violin(df_aux, y="avg_fitness", x="algo_id", color="algo_id", box=True, points="all", hover_data=["cs_id"])
        for data in fig.data:
            data.update(xaxis=f"x2", yaxis=f"y{r}", showlegend=False if r > 1 else True)
            combined_fig.add_trace(data, row=r, col=2)
            # combined_fig.update_yaxes(range=fig.layout.yaxis.range, row=r, col=1)
                
        # Fitness evolution
        cnt=0
        selector_idx0=0
        for idx, row in df_aux.iterrows():
            selector_idx = algo_ids.index(row["algo_id"])
            if selector_idx0 != selector_idx:
                cnt=0
                selector_idx0 = selector_idx
            combined_fig.add_trace(
                go.Scatter(
                    x=np.arange(len(row["fitness_history"])),
                    y=row["fitness_history"],
                    mode="lines",
                    name=row["cs_id"],
                    line=dict(color=plt_colors[selector_idx], dash=dash_types[cnt]),
                    showlegend=False if r > 1 else True
                ),
                row=r, col=1
            )
            cnt+=1

    # Update the overall layout
    # fitness_text = ", ".join([f"{algo_id}: {np.mean(avg_fitness_per_algo[algo_id]):.3f}" for algo_id in avg_fitness_per_algo.keys()])
    # fitness_alt_text = ", ".join([f"{cs_id}: {np.mean(avg_fitness_per_alt[cs_id]):.3f}" for cs_id in avg_fitness_per_alt.keys()])
    # Find best algo (highest mean fitness)
    best_algo_id = min(avg_fitness_per_algo, key=lambda k: np.mean(avg_fitness_per_algo[k]))
    fitness_text = ", ".join([
        f"<b>{algo_id}: {np.mean(avg_fitness_per_algo[algo_id]):.3f}</b>" if algo_id == best_algo_id
        else f"{algo_id}: {np.mean(avg_fitness_per_algo[algo_id]):.3f}"
        for algo_id in avg_fitness_per_algo
    ])

    # Same for alt
    best_cs_id = min(avg_fitness_per_alt, key=lambda k: np.mean(avg_fitness_per_alt[k]))
    fitness_alt_text = ", ".join([
        f"<b>{cs_id}: {np.mean(avg_fitness_per_alt[cs_id]):.3f}</b>" if cs_id == best_cs_id
        else f"{cs_id}: {np.mean(avg_fitness_per_alt[cs_id]):.3f}"
        for cs_id in avg_fitness_per_alt
    ])
    
    combined_fig.update_layout(
        height=2000, 
        width=1000, 
        margin=dict(l=5, r=5, t=150, b=20),
        title=dict(
          text="<b>Algorithm comparison </b>for a full day of operation",
          x=0,
          subtitle=dict(
            text=f"Average fitness per algo | {fitness_text}<br>Average fitness per alternative | {fitness_alt_text}",
            font=dict(size=10, color="gray")
          )
        ),
        **kwargs
    )
    
    return combined_fig
        
"""
From here is basically copied from EvoX: https://github.com/EMI-Group/evox/blob/main/src/evox/vis_tools/plot.py#L4
Have to find a better way to import this without having to install the whole package nor copying code
"""
        
def plot_obj_space_1d(fitness_history: list[np.ndarray[float]], animation: bool = True, **kwargs) -> go.Figure:
    if animation:
        return plot_obj_space_1d_animation(fitness_history, **kwargs)
    else:
        return plot_obj_space_1d_no_animation(fitness_history, **kwargs)


def plot_obj_space_1d_no_animation(fitness_history: list[np.ndarray[float]], algo_id: str = None, **kwargs) -> go.Figure:

    avg_fitness = [np.mean(x) for x in fitness_history]
    generation = np.arange(len(fitness_history))

    additional_scatters = []
    if isinstance(np.asarray(fitness_history)[0], Iterable):
        min_fitness = [np.min(x) for x in fitness_history]
        max_fitness = [np.max(x) for x in fitness_history]
        median_fitness = [np.median(x) for x in fitness_history]
        
        additional_scatters = [
            go.Scatter(x=generation, y=min_fitness, mode="lines", name="Min"),
            go.Scatter(x=generation, y=max_fitness, mode="lines", name="Max"),
            go.Scatter(x=generation, y=median_fitness, mode="lines", name="Median"),
        ]
        
    # Layout defaults
    kwargs.setdefault("yaxis_title", "Fitness")
    kwargs.setdefault("xaxis_title", "Number of objective function evaluations")
    kwargs.setdefault("title_text", "<b>Fitness evolution</b><br>comparison between different algorithms")
        
    fig = go.Figure(
        [
            *additional_scatters,
            go.Scatter(x=generation, y=avg_fitness, mode="lines", name="Average" if algo_id is None else algo_id),
        ],
        layout=go.Layout(
            showlegend=True,
            # legend={
            #     "x": 1,
            #     "y": 1,
            #     "xanchor": "auto",
            # },
            # margin={"l": 0, "r": 0, "t": 0, "b": 0},
            **kwargs
        ),
    )

    return fig

def plot_obj_space_1d_animation(fitness_history: list[np.ndarray[float]], **kwargs) -> go.Figure:
    """

    Args:
        fitness_history (list[np.ndarray[float]]): List of fitness values for each individual per generation

    Returns:
        go.Figure: Figure object
        
    Example:
    # This is the last population, after evolution
    # pop = isl.get_population()
    # Properties
    # - best_idx
    # - worst_idx
    # - champion_f
    # - champion_x
    log = isl.get_algorithm().extract(type(algorithm)).get_log()

    # We only have information from the best individual per generation
    fitness_history = [l[2] for l in log]
    
    fig = plot_obj_space_1d_animation(fitness_history=fitness_history, title="Fitness evolution")
    fig

    """

    min_fitness = [np.min(x) for x in fitness_history]
    max_fitness = [np.max(x) for x in fitness_history]
    median_fitness = [np.median(x) for x in fitness_history]
    avg_fitness = [np.mean(x) for x in fitness_history]
    generation = np.arange(len(fitness_history))

    frames = []
    steps = []
    for i in range(len(fitness_history)):
        frames.append(
            go.Frame(
                data=[
                    go.Scatter(
                        x=generation[: i + 1],
                        y=min_fitness[: i + 1],
                        mode="lines",
                        name="Min",
                        showlegend=True,
                    ),
                    go.Scatter(
                        x=generation[: i + 1],
                        y=max_fitness[: i + 1],
                        mode="lines",
                        name="Max",
                    ),
                    go.Scatter(
                        x=generation[: i + 1],
                        y=median_fitness[: i + 1],
                        mode="lines",
                        name="Median",
                    ),
                    go.Scatter(
                        x=generation[: i + 1],
                        y=avg_fitness[: i + 1],
                        mode="lines",
                        name="Average",
                    ),
                ],
                name=str(i),
            )
        )

        step = {
            "label": i,
            "method": "animate",
            "args": [
                [str(i)],
                {
                    "frame": {"duration": 200, "redraw": False},
                    "mode": "immediate",
                    "transition": {"duration": 200},
                },
            ],
        }
        steps.append(step)

    sliders = [
        {
            "currentvalue": {"prefix": "Generation: "},
            "pad": {"b": 1, "t": 10},
            "len": 0.8,
            "x": 0.2,
            "y": 0,
            "yanchor": "top",
            "xanchor": "left",
            "steps": steps,
        }
    ]
    lb = min(min_fitness)
    ub = max(max_fitness)
    fit_range = ub - lb
    lb = lb - 0.05 * fit_range
    ub = ub + 0.05 * fit_range
    fig = go.Figure(
        data=frames[-1].data,
        layout=go.Layout(
            legend={
                "x": 1,
                "y": 1,
                "xanchor": "auto",
            },
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            sliders=sliders,
            xaxis={"range": [0, len(fitness_history)], "autorange": False},
            yaxis={"range": [lb, ub], "autorange": False},
            updatemenus=[
                {
                    "type": "buttons",
                    "buttons": [
                        {
                            "args": [
                                None,
                                {
                                    "frame": {"duration": 200, "redraw": False},
                                    "fromcurrent": True,
                                },
                            ],
                            "label": "Play",
                            "method": "animate",
                        },
                        {
                            "args": [
                                [None],
                                {
                                    "frame": {"duration": 0, "redraw": False},
                                    "mode": "immediate",
                                },
                            ],
                            "label": "Pause",
                            "method": "animate",
                        },
                    ],
                    "x": 0.2,
                    "xanchor": "right",
                    "y": 0,
                    "yanchor": "top",
                    "direction": "left",
                    "pad": {"r": 10, "t": 30},
                },
            ],
            **kwargs,
        ),
        frames=frames,
    )

    return fig

def plot_dec_space(population_history, **kwargs,) -> go.Figure:
    """A Built-in plot function for visualizing the population of single-objective algorithm.
    Use plotly internally, so you need to install plotly to use this function.

    If the problem is provided, we will plot the fitness landscape of the problem.
    """

    all_pop = np.concatenate(population_history, axis=0)
    x_lb = np.min(all_pop[:, 0])
    x_ub = np.max(all_pop[:, 0])
    x_range = x_ub - x_lb
    x_lb = x_lb - 0.1 * x_range
    x_ub = x_ub + 0.1 * x_range
    y_lb = np.min(all_pop[:, 1])
    y_ub = np.max(all_pop[:, 1])
    y_range = y_ub - y_lb
    y_lb = y_lb - 0.1 * y_range
    y_ub = y_ub + 0.1 * y_range

    frames = []
    steps = []
    for i, pop in enumerate(population_history):
        frames.append(
            go.Frame(
                data=[
                    go.Scatter(
                        x=pop[:, 0],
                        y=pop[:, 1],
                        mode="markers",
                        marker={"color": "#636EFA"},
                    ),
                ],
                name=str(i),
            )
        )
        step = {
            "label": i,
            "method": "animate",
            "args": [
                [str(i)],
                {
                    "frame": {"duration": 200, "redraw": False},
                    "mode": "immediate",
                    "transition": {"duration": 200},
                },
            ],
        }
        steps.append(step)

    sliders = [
        {
            "currentvalue": {"prefix": "Generation: "},
            "pad": {"b": 1, "t": 10},
            "len": 0.8,
            "x": 0.2,
            "y": 0,
            "yanchor": "top",
            "xanchor": "left",
            "steps": steps,
        }
    ]

    fig = go.Figure(
        data=frames[0].data,
        layout=go.Layout(
            legend={
                "x": 1,
                "y": 1,
                "xanchor": "auto",
            },
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            sliders=sliders,
            xaxis={"range": [x_lb, x_ub]},
            yaxis={"range": [y_lb, y_ub]},
            updatemenus=[
                {
                    "type": "buttons",
                    "buttons": [
                        {
                            "args": [
                                None,
                                {
                                    "frame": {"duration": 200, "redraw": False},
                                    "fromcurrent": True,
                                    "transition": {
                                        "duration": 200,
                                        "easing": "linear",
                                    },
                                    "mode": "immediate",
                                },
                            ],
                            "label": "Play",
                            "method": "animate",
                        },
                        {
                            "args": [
                                [None],
                                {
                                    "frame": {"duration": 0, "redraw": False},
                                    "mode": "immediate",
                                    "transition": {"duration": 0},
                                },
                            ],
                            "label": "Pause",
                            "method": "animate",
                        },
                    ],
                    "x": 0.2,
                    "xanchor": "right",
                    "y": 0,
                    "yanchor": "top",
                    "direction": "left",
                    "pad": {"r": 10, "t": 30},
                },
            ],
            **kwargs,
        ),
        frames=frames,
    )

    return fig