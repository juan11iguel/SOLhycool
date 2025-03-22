import copy
import plotly.graph_objects as go
import numpy as np
import pandas as pd

from phd_visualizations.test_timeseries import experimental_results_plot

from solhycool_visualization import ComponentColors


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


def organ_transplant(fig: go.Figure, fig_aux: go.Figure, plot_id: str) -> go.Figure:

    fig_out = copy.deepcopy(fig)
    placeholder_trace = [data for data in fig_out.data if data.name == plot_id][0]

    # Ensure traces inherit the correct axis assignments
    for trace in fig_aux.data:
        trace.xaxis = placeholder_trace.xaxis
        trace.yaxis = placeholder_trace.yaxis
        trace.x = placeholder_trace.x
        trace.showlegend = True
        trace.legend = placeholder_trace.legend
        fig_out.add_trace(trace)

    # xaxis_long_id = placeholder_trace.xaxis.replace("x", "xaxis") # Example: "x2" → "xaxis2"
    yaxis_long_id = placeholder_trace.yaxis.replace("y", "yaxis") # Example: "y3" → "yaxis3"

    # Adjust y-axis range
    fig_out.layout[yaxis_long_id].range = fig_aux.layout.yaxis.range

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
    
    return fig_out


def plot_results(plot_config: dict, df: pd.DataFrame) -> go.Figure:
    
    fig = experimental_results_plot(plot_config, df=df, resample=False)
    
    # Join hydraulic distribution plot
    placeholder_plot_id = "hydraulic_distribution"
    placeholder_trace = [data for data in fig.data if data.name == placeholder_plot_id]
    assert len(placeholder_trace) == 1, f"Placeholder trace not found in figure, ensure `{placeholder_plot_id}` is in plot config"
    placeholder_trace = placeholder_trace[0]
    fig_aux = plot_hydraulic_distribution(df["qc"].values, df["Rp"].values, df["Rs"].values, x=df.index)
    fig = organ_transplant(fig=fig, fig_aux=fig_aux, plot_id=placeholder_plot_id)
    
    return fig