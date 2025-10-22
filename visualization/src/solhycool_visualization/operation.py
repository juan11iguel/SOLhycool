import copy
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from typing import Literal, Optional
import string
from loguru import logger
import datetime

from phd_visualizations.test_timeseries import experimental_results_plot
from solhycool_optimization import HorizonResults
from solhycool_visualization import ComponentColors
from solhycool_visualization.utils import adapt_dataframe
from solhycool_visualization.optimization import plot_pareto_front



def plot_hydraulic_distribution(
    qc: list[np.ndarray] | np.ndarray | pd.Series | list[pd.Series], 
    Rp: list[np.ndarray] | np.ndarray | pd.Series | list[pd.Series],
    Rs: list[np.ndarray] | np.ndarray | pd.Series | list[pd.Series],
    x: Optional[np.ndarray] = None,
    labels: list[str] = None,
    legend_id: str = "hydraulic_distribution",
    showticklabels: bool = True,
    pad_value: float = np.nan,
    pad_side: Literal["left", "right"] = "left",
    highlight_bar_idx: Optional[int] = None,
    showlegend: bool = True,
) -> go.Figure:
    
    # Ensure all inputs are lists
    if isinstance(qc, np.ndarray | pd.Series):
        qc = [qc]
        Rp = [Rp]
        Rs = [Rs]
        
    n_series = len(qc)
    assert all(len(lst) == n_series for lst in [Rp, Rs]), "All input lists must have the same length"# Determine if working with time series
    is_timeseries = isinstance(qc[0], pd.Series)
    
    if is_timeseries:
        if x is None:
            x = qc[0].index
        else:
            # Ensure x is a datetime index for resampling
            if not isinstance(x, (pd.DatetimeIndex, pd.Index)):
                x = pd.to_datetime(x)
        
        # Resample all Series to match the common index
        qc = [s.reindex(x).fillna(pad_value).to_numpy() for s in qc]
        Rp = [s.reindex(x).fillna(pad_value).to_numpy() for s in Rp]
        Rs = [s.reindex(x).fillna(pad_value).to_numpy() for s in Rs]
        x = x.to_numpy()  # Convert x to numpy for plotting
    else:
        # Pad non-timeseries arrays to the maximum length
        def pad_array(arr: np.ndarray, target_length: int) -> np.ndarray:
            if len(arr) == target_length:
                return arr
            pad_width = target_length - len(arr)
            if pad_side == "left":
                return np.pad(arr, (pad_width, 0), constant_values=pad_value)
            else:
                return np.pad(arr, (0, pad_width), constant_values=pad_value)
        
        max_length = max(max(len(q) for q in qc), max(len(r) for r in Rp), max(len(r) for r in Rs))
        qc = [pad_array(np.asarray(q), max_length) for q in qc]
        Rp = [pad_array(np.asarray(r), max_length) for r in Rp]
        Rs = [pad_array(np.asarray(r), max_length) for r in Rs]
        
        if x is None:
            x = np.arange(max_length)
    
    if labels is None:
        labels = list(string.ascii_uppercase[:n_series])

    n_points = len(x)

    fig = go.Figure()

    for i, (qc_, Rp_, Rs_, label) in enumerate(zip(qc, Rp, Rs, labels)):
        # Handle NaN values in calculations - NaN * anything = NaN, which is what we want
        qdc = qc_ * (1 - Rp_)
        qwct_p = qc_ * Rp_
        qwct_s = qdc * Rs_
        qdc_only = qdc - qwct_s

        # Create masks to handle NaN values in plotting
        valid_mask = ~(np.isnan(qc_) | np.isnan(Rp_) | np.isnan(Rs_))
        
        line = dict(
            width=None if highlight_bar_idx is None or i != highlight_bar_idx else 2,
            color=None if highlight_bar_idx is None or i != highlight_bar_idx else ComponentColors.CONDENSER.value,
        )
        
        fig.add_trace(go.Bar(
            x=x,
            y=np.where(valid_mask, qdc_only, None),  # Use None for invalid data points
            showlegend=True if (i == 0 and showlegend) else False,
            # legendgroup=legend_id,
            name='DC //',
            offsetgroup=label,
            marker=dict(
                color=ComponentColors.DC.value,
                line=line
            ),
            hovertemplate = f'DC // ({label}) | %{{y:.2f}}<extra></extra>' if i == 0 else f'{label} | %{{y:.2f}}<extra></extra>',
        ))
        
        fig.add_trace(go.Bar(
            x=x,
            y=np.where(valid_mask, qwct_s, None),
            name='DC - WCT',
            showlegend=True if (i == 0 and showlegend) else False,
            # legendgroup=legend_id,
            offsetgroup=label,
            base=np.where(valid_mask, qdc_only, None),
            marker=dict(
                color=ComponentColors.DC.value,
                line=line,
                pattern=dict(
                    shape="/",
                    fgcolor=ComponentColors.WCT.value,
                    size=15,
                    fgopacity=1,
                    solidity=0.5,
                ),
            ),
            hovertemplate = f'DC - WCT ({label}) | %{{y:.2f}}<extra></extra>' if i == 0 else f'{label} | %{{y:.2f}}<extra></extra>',
        ))
        
        fig.add_trace(go.Bar(
            x=x,
            y=np.where(valid_mask, qwct_p, None),
            name='WCT //',
            showlegend=True if (i == 0 and showlegend) else False,
            # legendgroup="hydraulic_distribution",
            offsetgroup=label,
            base=np.where(valid_mask, qdc_only + qwct_s, None),
            marker=dict(
                color=ComponentColors.WCT.value,
                line=line
            ),
            
            text=[label if j == n_points-1 and valid_mask[j] else None for j in range(n_points)] if n_series > 1 else [None] * n_points,
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
        yaxis_range=[0, max(np.nanmax(q) for q in qc) * 1.1],
        uniformtext_minsize=12, 
        uniformtext_mode='show',
        hovermode="x unified",
        hoverlabel_align = 'right',
    )

    # print(f"{fig.layout=} | {showticklabels=}")

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
    # print(f"{fig_aux.layout=}")
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

    # print(fig_out.layout)
    # display(fig_out.data)
    
    return fig_out


def plot_results(
    plot_config: dict, 
    df: Optional[pd.DataFrame] = None, 
    df_comp: Optional[pd.DataFrame] = None,
    comp_trace_labels: Optional[list[str]] = ["[opt]"],
    day_results: Optional[HorizonResults ] = None, 
    template: Optional[str] = None,
    hydraulic_distribution_dfs: Optional[list[pd.DataFrame]] = None,
    hydraulic_distribution_highlight_bar_idx: Optional[int] = None,
    hydraulic_distribution_labels: Optional[list[str]] = None,
    hydraulic_distribution_transplant_xaxis: bool = False,
    adapt_data: bool = True,
) -> go.Figure:
                #  df_paretos: list[pd.DataFrame] = None, pareto_idxs:  list[int] | list[list[int]] = None, ) -> go.Figure:
    
    supported_transplants = ["hydraulic_distribution", "paretos"]
    assert df is not None or day_results is not None, "Either `df` Dataframe or a `HorizonResults` instance must be provided"
    
    if df is None:
        df = day_results.df_results
        
    if adapt_data:
        df = adapt_dataframe(df.resample("h").asfreq())
        if df_comp is not None:
            df_comp = adapt_dataframe(df_comp.resample("h").asfreq())
    
    fig = experimental_results_plot(
        plot_config, 
        df=adapt_dataframe(df), 
        df_comp=adapt_dataframe(df_comp) if df_comp is not None else None, 
        resample=False, 
        template=template, 
        comp_trace_labels=comp_trace_labels,
    )
    
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
            if hydraulic_distribution_dfs:
                df_ = hydraulic_distribution_dfs
            else:
                df_ = [df] if df_comp is None else [df, df_comp]
                
            qc = [df_["qc"] for df_ in df_]
            Rp = [df_["Rp"] for df_ in df_]
            Rs = [df_["Rs"] for df_ in df_]

            fig = organ_transplant(
                fig=fig,
                fig_aux=plot_hydraulic_distribution(
                    qc, Rp, Rs, 
                    x=df_[0].index, 
                    showticklabels=hydraulic_distribution_transplant_xaxis, 
                    highlight_bar_idx=hydraulic_distribution_highlight_bar_idx,
                    labels=hydraulic_distribution_labels,
                    showlegend=plot_config["plots"][plot_id].get("showlegend", True)
                ),
                plot_id=plot_id,
                transplant_xaxis=hydraulic_distribution_transplant_xaxis
            )
                    
        # Join paretos plot
        if plot_id == "paretos":
            # TODO: For some reason the pareto plot breaks when a discontinuous optimization is provided
            # assert df_paretos is not None, "Pareto front dataframes must be provided"
            # assert pareto_idxs is not None, "Pareto front indices must be provided"
            assert day_results is not None, "HorizonResults object must be provided"
    
            
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