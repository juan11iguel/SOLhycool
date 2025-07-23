import copy
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from typing import Literal, Optional
import string
from loguru import logger

from phd_visualizations.test_timeseries import experimental_results_plot
from solhycool_optimization import DayResults, MultipleDayResults
from solhycool_visualization import ComponentColors
from solhycool_visualization.optimization import plot_pareto_front


def plot_hydraulic_distribution(
    qc: list[np.ndarray] | np.ndarray, 
    Rp: list[np.ndarray] | np.ndarray, 
    Rs: list[np.ndarray] | np.ndarray, 
    x: np.ndarray = None,
    labels: list[str] = None,
    legend_id: str = "hydraulic_distribution",
    showticklabels: bool = True,
) -> go.Figure:
    
    if isinstance(qc, np.ndarray):
        qc = [qc]
        Rp = [Rp]
        Rs = [Rs]
    
    n_series = len(qc)
    assert all(len(lst) == n_series for lst in [Rp, Rs]), "All input lists must have the same length"
    n_points = len(qc[0])
    assert all(len(q) == n_points for q in qc), "Each series must have the same number of points"
    
    if x is None:
        x = np.arange(n_points)
    if labels is None:
        labels = list(string.ascii_uppercase[:n_series])

    fig = go.Figure()

    for i, (qc_, Rp_, Rs_, label) in enumerate(zip(qc, Rp, Rs, labels)):
        qdc = qc_ * (1 - Rp_)
        qwct_p = qc_ * Rp_
        qwct_s = qdc * Rs_
        qdc_only = qdc - qwct_s

        fig.add_trace(go.Bar(
            x=x,
            y=qdc_only,
            showlegend=True if i == 0 else False,
            # legendgroup=legend_id,
            name='DC //',
            offsetgroup=label,
            marker=dict(color=ComponentColors.DC.value),
            hovertemplate = f'DC // ({label}) | %{{y:.2f}}<extra></extra>' if i == 0 else f'{label} | %{{y:.2f}}<extra></extra>',
        ))
        
        fig.add_trace(go.Bar(
            x=x,
            y=qwct_s,
            name='DC 🠒 WCT',
            showlegend=True if i == 0 else False,
            # legendgroup=legend_id,
            offsetgroup=label,
            base=qdc_only,
            marker=dict(
                color=ComponentColors.DC.value,
                pattern=dict(
                    shape="/",
                    fgcolor=ComponentColors.WCT.value,
                    size=15,
                    fgopacity=1,
                    solidity=0.5,
                ),
            ),
            hovertemplate = f'DC 🠒 WCT ({label}) | %{{y:.2f}}<extra></extra>' if i == 0 else f'{label} | %{{y:.2f}}<extra></extra>',
        ))
        
        fig.add_trace(go.Bar(
            x=x,
            y=qwct_p,
            name='WCT //',
            showlegend=True if i == 0 else False,
            # legendgroup="hydraulic_distribution",
            offsetgroup=label,
            base=qdc_only + qwct_s,
            marker=dict(color=ComponentColors.WCT.value),
            
            text=[label] + [None]* n_points if n_series > 1 else [None]* n_points,
            # textfont_size=12, textangle=0, textposition="outside", cliponaxis=False),
            textposition='outside',
            textangle=-90,
            outsidetextfont=dict(size=11),  # Increase text size
            # textfont=dict(size=20),  # Increase text size
            cliponaxis=False,         # Prevent text from being clipped
            hovertemplate = f'WCT // ({label}) | %{{y:.2f}}<extra></extra>' if i == 0 else f'{label} | %{{y:.2f}}<extra></extra>',
        ))

    if n_series == 1:
        title = dict(text='<b>Hydraulic Distribution</b> of combined cooler',)
    else:
        title = dict(text='<b>Hydraulic Distribution</b> of combined cooler', subtitle_text=f"comparison between {', '.join(label for label in labels) if labels is not None else n_series} alternatives")

    fig.update_layout(
        barmode='group',
        title=title,
        yaxis_title='Flow rate (m³/h)',
        xaxis_title='Index',
        template='plotly_white',
        xaxis=dict(
            # type='category',
            tickvals=x,  # Specify your custom ticks
            tickformat="%H:%M",  # Format as YYYYMMDD Hour:Minute (e.g., 00:00, 06:00) %Y%m%d 
            showticklabels=showticklabels,  # Ensure the labels are shown
            tickangle=90,  # Optionally rotate labels for better readability
            showgrid=False, # Hide grid lines, creates visual artifacts when coupled to other figures
            minor=dict(
                showgrid=False,  # Hide minor grid lines
            ),
        ) if len(x) < 24 and not isinstance(x[0], int) else None,
        yaxis_range=[0, max(q.max() for q in qc) * 1.1],
        uniformtext_minsize=12, 
        uniformtext_mode='show',
        hovermode="x unified",
        hoverlabel_align = 'right',
    )

    return fig


def organ_transplant(fig: go.Figure, fig_aux: go.Figure, plot_id: str, transplant_xaxis: bool = False, ydomain_offset: float = 0.0) -> go.Figure:
    xaxis_fields_to_not_copy = ["anchor", "domain", "title"]

    fig_out = copy.deepcopy(fig)
    placeholder_trace = [data for data in fig_out.data if data.name == plot_id][0]

    # Ensure traces inherit the correct axis assignments
    for trace in fig_aux.data:
        trace.xaxis = placeholder_trace.xaxis
        trace.yaxis = placeholder_trace.yaxis
        if not transplant_xaxis:
            trace.x = placeholder_trace.x
        # trace.showlegend = placeholder_trace.showlegend
        trace.legend = placeholder_trace.legend
        fig_out.add_trace(trace)

    xaxis_long_id = placeholder_trace.xaxis.replace("x", "xaxis") # Example: "x2" → "xaxis2"
    yaxis_long_id = placeholder_trace.yaxis.replace("y", "yaxis") # Example: "y3" → "yaxis3"

    # Adjust y-axis range
    fig_out.layout[yaxis_long_id].range = fig_aux.layout.yaxis.range
    fig_out.layout[yaxis_long_id].domain = [
        fig_out.layout[yaxis_long_id].domain[0] + ydomain_offset,
        fig_out.layout[yaxis_long_id].domain[1] + ydomain_offset
    ]

    # Copy xaxis properties
    fig_out.layout[xaxis_long_id] = fig_out.layout[xaxis_long_id].update(
        {
            name: value for name, value in fig_aux.layout.xaxis.to_plotly_json().items() 
            if name not in xaxis_fields_to_not_copy
        }
    )

    # Transfer shapes while correcting axis references
    for shape in fig_aux.layout.shapes:
        shape.xref = f"{placeholder_trace.xaxis}"  
        shape.yref = f"{placeholder_trace.yaxis}"  
        shape.legend = placeholder_trace.legend
        fig_out.add_shape(shape)

    # Ensure bar mode settings are consistent
    fig_out.update_layout(
        barmode=fig_aux.layout.barmode,
        bargap=fig_aux.layout.bargap,
    )

    # display(fig_out.layout)
    # display(fig_out.data)
    
    return fig_out


def plot_results(plot_config: dict, df: pd.DataFrame = None, df_comp: pd.DataFrame = None,
                 day_results: DayResults | MultipleDayResults = None, template: Optional[str] = None) -> go.Figure:
                #  df_paretos: list[pd.DataFrame] = None, pareto_idxs:  list[int] | list[list[int]] = None, ) -> go.Figure:
    
    supported_transplants = ["hydraulic_distribution", "paretos"]
    assert df is not None or day_results is not None, "Either `df` Dataframe or a `DayResults` instance must be provided"
    
    if df is None:
        df = day_results.df_results
    
    fig = experimental_results_plot(plot_config, df=df, df_comp=df_comp, resample=False, template=template)
    
    # for plot_id in plot_config["plots"]:
    #     assert plot_id in supported_transplants, f"Supported plot types are: {supported_transplants}, not {plot_id}"
    
    for plot_idx, plot_id in enumerate(plot_config["plots"]):
        if plot_id not in supported_transplants:
            continue
        
        placeholder_trace = [data for data in fig.data if data.name == plot_id]
        assert len(placeholder_trace) == 1, f"Placeholder trace not found in figure, ensure `{plot_id}` is in plot config"
        placeholder_trace = placeholder_trace[0]
        
        # Join hydraulic distribution plot
        if plot_id == "hydraulic_distribution":
            
            qc = df["qc"].values if df_comp is None else [df["qc"].values, df_comp["qc"].values]
            Rp = df["Rp"].values if df_comp is None else [df["Rp"].values, df_comp["Rp"].values]
            Rs = df["Rs"].values if df_comp is None else [df["Rs"].values, df_comp["Rs"].values]
            # legend_id = f"legend{plot_idx if plot_idx > 0 else ''}"

            fig = organ_transplant(
                fig=fig,
                fig_aux=plot_hydraulic_distribution(qc, Rp, Rs, x=df.index, showticklabels=False), #, legend_id=legend_id),
                plot_id=plot_id
            )
                    
        # Join paretos plot
        if plot_id == "paretos":
            # TODO: For some reason the pareto plot breaks when a discontinuous optimization is provided
            # assert df_paretos is not None, "Pareto front dataframes must be provided"
            # assert pareto_idxs is not None, "Pareto front indices must be provided"
            assert day_results is not None, "DayResults object must be provided"
            
            if isinstance(day_results, MultipleDayResults):
                logger.warning("currently not supported for multiple days")
                continue
            
            fig = organ_transplant(
                fig=fig,
                fig_aux=plot_pareto_front(
                    ops_list=day_results.df_paretos,
                    objective_keys=('Cw', 'Ce'),
                    mode="side_by_side",
                    selected_idxs=day_results.selected_pareto_idxs,
                    showlegend=False
                ),
                plot_id=plot_id,
                transplant_xaxis=True,
            )
            
    return fig