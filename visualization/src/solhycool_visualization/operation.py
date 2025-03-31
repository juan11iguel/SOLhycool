import copy
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from typing import Literal

from phd_visualizations.test_timeseries import experimental_results_plot

from solhycool_visualization import ComponentColors
from solhycool_visualization.optimization import plot_pareto_front


def plot_hydraulic_distribution(qc: np.ndarray, Rp: np.ndarray, Rs: np.ndarray, x: np.ndarray = None) -> go.Figure:
    qdc = qc * (1 - Rp)
    qwct_p = qc * Rp
    qwct_s = qdc * Rs
    qdc_only = qdc-qwct_s
    x = np.arange(len(qc)) if x is None else x
    
    # print(f"{qc=}, \n{qwct_p=}, \n{qdc=}, \n{qwct_s=}")

    fig = go.Figure()

    # Add stacked bars for qdc and qwct_p
    fig.add_trace(go.Bar(
        x=x,
        y=qdc_only,
        name='DC //',
        marker=dict(color=ComponentColors.DC.value)
    ))
    
    fig.add_trace(go.Bar(
        x=x,
        y=qwct_s,
        name='DC 🠒 WCT',
        marker=dict(
            color=ComponentColors.DC.value, 
            pattern=dict(shape="/", 
                         fgcolor=ComponentColors.WCT.value, 
                         size=15,
                         fgopacity=1,
                         solidity=0.5)
            ),
        # marker_pattern_shape
    ))

    fig.add_trace(go.Bar(
        x=x,
        y=qwct_p,
        name='WCT //',
        marker=dict(color=ComponentColors.WCT.value)
    ))
    
    # Determine a reasonable x offset for bar width
    if len(x) > 1:
        dx = 0.8* np.min(np.diff(x)) / 2  # Use half the minimum spacing between x-values
    else:
        dx = 0.4  # Default offset if only one x value exists


    # Add shape for qwct_s starting from the end of qdc
    # for i in range(len(qc)):
    #     # print(f"{qc[i]=:.0f}, {qdc[i]=:.0f}, {qwct_p[i]=:.0f}, {qwct_s[i]=:.0f}, {Rp[i]=}, {Rs[i]=}")
    #     fig.add_shape(
    #         type="rect",
    #         xref="x",
    #         yref="y",
    #         x0=x[i] - dx, x1=x[i] + dx,  # Dynamically computed x-range
    #         y0=qdc[i] - qwct_s[i], y1=qdc[i],
    #         line=dict(color=ComponentColors.WCT.value, width=5),
    #         # fillcolor="red",
    #         opacity=1,
    #         layer="above",
    #         name="DC 🠒 WCT",
    #         showlegend=True if i == 0 else False,
    #     )

    fig.update_layout(
        barmode='stack', 
        title=dict(text='<b>Hydraulic Distribution</b>', subtitle_text="of combined cooler"),
        yaxis_title='Flow rate (m³/h)',
        template='plotly_white',
        yaxis_range=[0, max(qc) * 1.1], # So it can be used when integrating in other figures
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
        trace.showlegend = placeholder_trace.showlegend
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
        {name: value for name, value in fig_aux.layout.xaxis.to_plotly_json().items() if name not in xaxis_fields_to_not_copy}
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


def plot_results(plot_config: dict, df: pd.DataFrame, df_comp: pd.DataFrame = None,
                 df_paretos: list[pd.DataFrame] = None, pareto_idxs:  list[int] | list[list[int]] = None, ) -> go.Figure:
    
    supported_transplants = ["hydraulic_distribution", "paretos"]
    
    fig = experimental_results_plot(plot_config, df=df, df_comp=df_comp, resample=False)
    
    # for plot_id in plot_config["plots"]:
    #     assert plot_id in supported_transplants, f"Supported plot types are: {supported_transplants}, not {plot_id}"
    
    for plot_id in plot_config["plots"]:
        if plot_id not in supported_transplants:
            continue
        
        placeholder_trace = [data for data in fig.data if data.name == plot_id]
        assert len(placeholder_trace) == 1, f"Placeholder trace not found in figure, ensure `{plot_id}` is in plot config"
        placeholder_trace = placeholder_trace[0]
        
        # Join hydraulic distribution plot
        if plot_id == "hydraulic_distribution":
            fig = organ_transplant(
                fig=fig, 
                fig_aux = plot_hydraulic_distribution(df["qc"].values, df["Rp"].values, df["Rs"].values, x=df.index), 
                plot_id=plot_id
            )
            
        # Join paretos plot
        if plot_id == "paretos":
            assert df_paretos is not None, "Pareto front dataframes must be provided"
            assert pareto_idxs is not None, "Pareto front indices must be provided"
            
            fig = organ_transplant(
                fig=fig,
                fig_aux=plot_pareto_front(
                    ops_list=df_paretos,
                    objective_keys=('Cw', 'Ce'),
                    mode="side_by_side",
                    selected_idxs=pareto_idxs,
                    showlegend=False
                ),
                plot_id=plot_id,
                transplant_xaxis=True,
            )
            
    return fig