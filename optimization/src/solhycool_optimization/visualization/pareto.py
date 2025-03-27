from dataclasses import asdict, fields
import numpy as np
import pandas as pd

from solhycool_modeling import OperationPoint
from solhycool_optimization import DecisionVariables

from plotly.validators.scatter.marker import SymbolValidator
from phd_visualizations.constants import color_palette, plt_colors, default_fontsize, newshape_style
import plotly.graph_objects as go

symbols = SymbolValidator().values[2::12]
symbols_open = SymbolValidator().values[3::12]
symbols_filled = SymbolValidator().values[4::12]

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

def plot_pareto_front(ops_list: list[pd.DataFrame] | list[list[OperationPoint]], objective_keys: tuple[str, str] = ('Cw', 'Ce'),
                additional_pts: np.ndarray[float] = None,
                full_legend:bool = False, highlight_idx:int = None, width: int = 550, height: int = 450) -> go.Figure:

    fig = go.Figure()
    
    if not isinstance(ops_list[0], pd.DataFrame):
        # Convert list of OperationPoint objects to DataFrame
        ops_list = [pd.DataFrame([asdict(op) for op in ops]) for ops in ops_list]
        
    if additional_pts is not None:
        assert additional_pts.shape[1] == len(objective_keys), f"additional_pts must have the same number of columns ({additional_pts.shape[1]}) as objective_keys ({len(objective_keys)})"

    # Add each pareto front with a different line style and mode line+markers
    for pareto_idx, ops in enumerate(ops_list):
        op = ops.iloc[0]
        # Order by ascending Cw
        ops.sort_values(by=objective_keys[0], inplace=True)
        if highlight_idx is None:
            color = plt_colors[pareto_idx]
            opacity = 0.7
        else:
            if pareto_idx == highlight_idx:
                color = plt_colors[pareto_idx]
                opacity = 0.7
            else:
                color = color_palette['gray']
                opacity = 0.3

        idx_str = op["time"].strftime("%H:%M") if "time" in ops.columns else str(pareto_idx)
        
        if full_legend:
            name = f'{idx_str} | T<sub>amb</sub>={op["Tamb"]:.1f} ºC, ɸ={op["HR"]:.0f} %, T<sub>v</sub>={op["Tv"]:.1f} ºC, Q={op["Qc_released"]:.0f} kW<sub>th</sub>'
        else:
            if pareto_idx == len(ops_list) - 1:
                name = f'{idx_str} | T<sub>amb</sub>={op["Tamb"]:.1f}, ɸ={op["HR"]:.0f}, T<sub>v</sub>={op["Tv"]:.1f}, Q={op["Qc_released"]:.0f}'
            else:
                name = f'{idx_str} | {op["Tamb"]:.1f} ºC, {op["HR"]:.0f} %, {op["Tv"]:.1f} ºC, {op["Qc_released"]:.0f} kW<sub>th</sub>'

        # custom_data, hover_text = generate_tooltip_data(ops)
        custom_data, hover_text = None, None

        # Pareto line
        fig.add_trace(
            go.Scatter(
                x=ops[objective_keys[0]], y=ops[objective_keys[1]],
                name=name,
                mode='lines+markers',
                line=dict(width=0.5, color=color, dash='dot'),
                marker=dict(size=10, color=color, symbol=symbols[pareto_idx], opacity=opacity),
                hovertemplate=hover_text, customdata=custom_data,
            )
        )

        # Pareto point
        # fig.add_trace(
        #     go.Scatter(
        #         x=[ops['Cw'][case_study['selected_solution_idx']-1]], 
        #         y=[ops['Ce'][case_study['selected_solution_idx']-1]],
        #         name=case_study["time"].strftime("%H:%M"),
        #         mode='markers', showlegend=False,
        #         marker=dict(size=20, color=color, symbol=symbols_open[pareto_idx], opacity=opacity, line_width=3),
        #     )
        # )

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

    fig.update_xaxes(title_text=f"{objective_keys[0]} ({OPERATION_PT_FIELD_METADATA[objective_keys[0]].get('units', '')})", title_font=dict(size=default_fontsize),)
    fig.update_yaxes(title_text=f"{objective_keys[1]} ({OPERATION_PT_FIELD_METADATA[objective_keys[1]].get('units', '')})", title_font=dict(size=default_fontsize),)

    fig.update_layout(
        # Configure axis
        
        # xaxis=dict(title='Water consumption (l/h)', range=[xlim[0], xlim[1]], showspikes=True, gridcolor='rgba(0,0,0,0.1)'),
        # yaxis=dict(title='Electricity consumption (kW<sub>e</sub>)', range=[ylim[0], ylim[1]], showspikes=True, gridcolor='rgba(0,0,0,0.1)'),
        # Transparent background
        # plot_bgcolor='rgba(0,0,0,0)',
        # Fontsize
        font=dict(size=default_fontsize),
        newshape=newshape_style,
        # hovermode="x",
        # Configure legend
        legend=dict(
            # # Smaller font
            # font=dict(size=default_fontsize-2),
            # # orientation="h",
            yanchor="bottom",
            xanchor="center",
            x=0.5, y=1,
            bgcolor=f'rgba(255,255,255,1)',
            # font_color='white',
            # font=dict(),
            # entrywidth=opacity, # change it to 0.3
            # entrywidthmode='fraction',
        ),

        width=width,
        height=height,
        margin=dict(l=20, r=20, t=20, b=20, pad=5),
    )

    return fig