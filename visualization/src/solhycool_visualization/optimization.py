# Similarly named as in the optimization package, decisions need to be made
from typing import Literal, Optional
import pandas as pd
import numpy as np
import copy
import plotly.graph_objects as go
from dataclasses import asdict, fields
import plotly

from solhycool_modeling import OperationPoint
from phd_visualizations.constants import color_palette, plt_colors, default_fontsize, newshape_style
import plotly.graph_objects as go

from packaging import version

if version.parse(plotly.__version__) >= version.parse("6.0.0"):
    # Plotly 6+
    from plotly.validator_cache import ValidatorCache
    SymbolValidator = ValidatorCache.get_validator("scatter.marker", "symbol")
    symbols = SymbolValidator.values
else:
    # Plotly 5.x and below
    from plotly.validators.scatter.marker import SymbolValidator
    symbols = SymbolValidator().values  # May need filtering depending on internal format

# TODO: Esta función tiene que unirse y hacerse compatible con la del módulo de optimización

symbols = copy.deepcopy(symbols)[2::12]
symbols_open = copy.deepcopy(symbols)[3::12]
symbols_filled = copy.deepcopy(symbols)[4::12]

# Precompute field metadata lookup dictionary
OPERATION_PT_FIELD_METADATA = {fld.name: fld.metadata for fld in fields(OperationPoint)}

def generate_tooltip_data(ops: pd.DataFrame | list[OperationPoint]) -> tuple[np.ndarray, str]:
    """Generates tooltip data dynamically from dataclass fields."""
    if not isinstance(ops, pd.DataFrame):
        ops = pd.DataFrame([asdict(op) for op in ops])
    
    custom_data = ops.to_numpy()
    hover_text = "<b>Decision variables</b><br>"
    
    for idx, fld in enumerate(fields(DecisionVariables)):
        unit = OPERATION_PT_FIELD_METADATA[fld.name].get("units", "")
        hover_text += f"- {fld.name}: %{{customdata[{idx}]:.2f}} {unit}<br>"
    
    return custom_data, hover_text

def plot_pareto_front(
    ops_list: list[pd.DataFrame],
    objective_keys: tuple[str, str] = ('Cw', 'Ce'),
    additional_pts: np.ndarray = None,
    full_legend: bool = False,
    highlight_idx: int = None,
    mode: Literal["overlap", "side_by_side"] = "overlap",
    selected_idxs: list[int] | list[list[int]] = None,
    line_width: float =0.5,
    showlegend: bool = True,
    date_fmt: str = "%H:%M",
    simple_colors: bool = False,
    xaxis_label: Optional[str] = None,
    yaxis_label: Optional[str] = None,
    **kwargs,
) -> go.Figure:
    """
    Plots Pareto fronts either overlapping or side by side, with optional connecting lines.
    """
    
    fig = go.Figure()
    x_offset = 100 if mode == "side_by_side" else 0  # Adjust for side-by-side spacing
    x0_values_list = [ops_list[0].iloc[0][objective_keys[0]]]
    for pareto_idx, ops in enumerate(ops_list):
        ops = ops.copy()
        ops.sort_values(by=objective_keys[0], inplace=True)
        op = ops.iloc[0]
        opacity = 1 if highlight_idx is None or pareto_idx == highlight_idx else 0.3
        if highlight_idx is None:
            if simple_colors:
                color = plt_colors[pareto_idx]
            else:
                color = f'rgba({pareto_idx * 30 % 255}, {100 + pareto_idx * 20 % 155}, {200 - pareto_idx * 20 % 200}, 0.7)'
        else:
            if pareto_idx == highlight_idx:
                color = plt_colors[pareto_idx]
                opacity = 0.7
            else:
                color = color_palette['gray']
                opacity = 0.3
        
        # Adjust x values for side_by_side mode
        diff = 1
        idx_str = str(pareto_idx)
        if "time" in ops.columns:
            idx_str = op["time"].strftime(date_fmt)
            diff = (op["time"] - ops_list[pareto_idx-1].iloc[0]["time"]).seconds/3600
            
        if pareto_idx > 0 and mode == "side_by_side":
            x_offset_ = x0_values_list[-1] + x_offset*diff
        else:
            x_offset_ = 0
            
        # print(f"{x_offset_=}, {diff=}")
        x_values = ops[objective_keys[0]].values + x_offset_
        
        if pareto_idx > 0:
            x0_values_list.append(x_values[0])
        
        name = f'{idx_str} | T<sub>amb</sub>={op["Tamb"]:.1f} °C, HR={op["HR"]:.0f} %, T<sub>v</sub>={op["Tv"]:.1f} °C, Q̇={op["Qc_released"]:.0f} kW<sub>th</sub>' if full_legend else idx_str # ɸ
        
        # custom_data, hover_text = generate_tooltip_data(ops)
        custom_data, hover_text = None, None
        
        fig.add_trace(go.Scatter(
            x=x_values, y=ops[objective_keys[1]],
            name=name,
            mode='lines+markers',
            line=dict(width=line_width, color=color, dash='dot'),
            marker=dict(size=10, color=color, opacity=opacity, symbol=symbols[pareto_idx]),
            zorder=2 if highlight_idx is not None and pareto_idx == highlight_idx else 1,
            showlegend=showlegend,
        ), )
        
        #TODO: We should support highlighting selected points in the pareto front 
        # not only in side_by_side mode but also in overlap mode. I think I already
        # had this impemented in a solhycool-optimization repo
        if selected_idxs is not None and mode == "overlap":
            selected_idx = selected_idxs[pareto_idx]
            if selected_idx is None:
                continue
            
            fig.add_trace(go.Scatter(
                x=[x_values[selected_idx]], y=[ops[objective_keys[1]][selected_idx]],
                name=name,
                mode='markers',
                showlegend=False,
                marker=dict(size=20, color=color, opacity=opacity, symbol=symbols_open[pareto_idx], line_width=3),
            ))
    
    
    # Add connecting lines for selected indices
    # print(f"{len(ops_list)=}, {len(x0_values_list)=}")
    if selected_idxs is not None and mode == "side_by_side":
        # for idx in selected_idxs:
        if not isinstance(selected_idxs[0], list):
            selected_idxs = copy.deepcopy(selected_idxs)
            # selected_idxs = [copy.deepcopy(selected_idxs)]
            
            # Automatically split potential discontinuities in the static optimization
            if "time" in ops_list[0].columns:
                index = [ops.iloc[0]["time"] for ops in ops_list] 
                boundaries = [0] + (
                    np.where(np.diff(index) > np.mean(np.diff(index)))[0] + 1
                    ).tolist() + [len(selected_idxs)]
                
                selected_idxs = [selected_idxs[boundaries[i]:boundaries[i+1]] for i in range(len(boundaries) - 1)]
        
        p_idx0 = 0
        for s_idxs in selected_idxs:
            ops_list_ = ops_list[p_idx0:p_idx0+len(s_idxs)]
            x0_values_list_ = x0_values_list[p_idx0:p_idx0+len(s_idxs)]
            
            x_vals = [xval0 + (ops.iloc[s_idx][objective_keys[0]] - ops.iloc[0][objective_keys[0]]) for ops, s_idx, xval0 in zip(ops_list_, s_idxs, x0_values_list_)]
            y_vals = [ops.iloc[selected_idx][objective_keys[1]] for ops, selected_idx in zip(ops_list_, s_idxs)]
            # print(f"{len(ops_list_)=}, {len(s_idxs)=}, {len(x0_values_list_)=}")
            # print(f"{x_vals=}")
            # print(f"{y_vals=}")
            fig.add_trace(
                go.Scatter(
                    x=np.array(x_vals), 
                    y=np.array(y_vals), 
                    mode='lines+markers', 
                    line=dict(color='black', width=2), 
                    name=f'Selected path, x0={x0_values_list[p_idx0+1]}',
                    showlegend=showlegend,
                )
            )

            p_idx0 += len(s_idxs)
            
    # Modify xticks to have one for each pareto, placed in its middle and change the label to the time if available
    # xtick minor should be placed at the first and last point of the pareto and as label have the objective value 
    # without the offset

    # Compute x-ticks positions
    if mode == "side_by_side":
        major_xticks = []
        major_xtick_labels = []
        minor_xticks = []

        for pareto_idx, ops in enumerate(ops_list):
            x_values = ops[objective_keys[0]].values + x0_values_list[pareto_idx] - ops[objective_keys[0]].values[0]
            x_mid = (x_values[0] + x_values[-1]) / 2  # Midpoint of Pareto front
            
            # Major ticks: at the midpoint of each Pareto set
            major_xticks.append(x_mid)
            if "time" in ops.columns:
                major_xtick_labels.append(ops.iloc[0]["time"].strftime("%H"))
            else:
                major_xtick_labels.append(f"P{pareto_idx+1}")  # Fallback label
            
            # Minor ticks: first and last points of each Pareto front
            minor_xticks.extend([x_values[0], x_values[-1]])

        # Update x-axis with major ticks
        fig.update_xaxes(
            tickvals=major_xticks, 
            ticktext=major_xtick_labels,
            tickmode="array",
            # tickangle=90,
            # title_side="top",
            minor=dict(
                tickvals=minor_xticks, 
                # ticktext=minor_xtick_labels,
                showgrid=True
            ),
        )
            
    # Cloud of operation points
    if additional_pts is not None:

        fig.add_trace(
            go.Scatter(
                x=additional_pts[:, 0], y=additional_pts[:, 1],
                name="Additional evaluation points",
                mode='markers', 
                showlegend=False,
                marker=dict(size=3, color=color_palette['gray'], symbol=symbols_open[pareto_idx], opacity=0.3, line_width=3),
            )
        )

    # Set axis labels
    fig.update_xaxes(
        title_text=f"{objective_keys[0]} ({OPERATION_PT_FIELD_METADATA[objective_keys[0]].get('units', '')})" if xaxis_label is None else xaxis_label, 
        title_font=dict(size=default_fontsize),
        zeroline=False,
        range=(-x_offset, minor_xticks[-1]+x_offset) if mode=="side_by_side" else (0, max([ops[objective_keys[0]].max() for ops in ops_list])*1.05) # So it's available when transplanting to other axis
        )
    fig.update_yaxes(
        title_text=f"{objective_keys[1]} ({OPERATION_PT_FIELD_METADATA[objective_keys[1]].get('units', '')})" if yaxis_label is None else yaxis_label, 
        title_font=dict(size=default_fontsize),
        showgrid=True, range=[ 0, max([ops[objective_keys[1]].max() for ops in ops_list])*1.05 ]
    )

    kwargs.setdefault("width", 1000)
    kwargs.setdefault("height", 450)
    kwargs.setdefault("showlegend", True)
    kwargs.setdefault("font", dict(size=default_fontsize))
    kwargs.setdefault("margin", dict(l=20, r=20, t=20, b=20, pad=5))
    kwargs.setdefault("legend_bgcolor", 'rgba(255,255,255,0.9)')
    fig.update_layout(
        newshape=newshape_style,
        **kwargs,
    )
    
    return fig