from typing import Literal
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from solhycool_visualization import ComponentColors as CC
from phd_visualizations.constants import color_palette
from solhycool_modeling import OperationPoint

plot_metadata = {
    "costs": {
        "title":{"text": "Costs"}, # , "variants":{"absolute": "€/h", "specific": "€/kW<sub>th</sub>"}},
        "labels": ["pumping", "DC", "WCT", "water source 1", "water source 2"],
        "var_ids": {"base": "J" , "components": ["Je_c", "Je_dc", "Je_wct", "Jw_s1", "Jw_s2"]},
        "colors": [CC.ELECTRICITY.value, CC.ELECTRICITY.value, CC.ELECTRICITY.value, CC.WATER.value, CC.WATER.value],
        "line_colors": [CC.CONDENSER.value, CC.DC.value, CC.WCT.value, CC.WATER1.value, CC.WATER2.value],
        "domain": [0, 0.35]
    },
    "cooling_power": {
        "title":{"text": "Cooling<br>power", "variants":{"absolute": "kW<sub>th</sub>"}},
        "labels": ["DC", "WCT"],
        "var_ids": {"base": "Qc_released" , "components": ["Qdc", "Qwct"]},
        "colors": [CC.DC.value, CC.WCT.value],
        "domain": [0.5, 0.7]
        # "line_colors": [CC.CONDENSER.value, CC.DC.value, CC.WCT.value, CC.TRANSPARENT.value, CC.TRANSPARENT.value]
    },
    "hydraulic_distribution": {
        "title":{"text": "Hydraulic<br>distribution"},
        "labels": ["DC", "DC🠒WCT", "WCT"],
        "var_ids": {"base": "qc" , "components": ["qdc_only", "qwct_s", "qwct_p"]},
        "colors": [CC.DC.value, CC.DC.value, CC.WCT.value],
        "pattern_colors": [CC.TRANSPARENT.value, CC.WCT.value, CC.TRANSPARENT.value],
        "domain": [0.8, 1]
        # "line_colors": [CC.CONDENSER.value, CC.DC.value, CC.WCT.value, CC.TRANSPARENT.value, CC.TRANSPARENT.value]
    },
}

def year_pie_plot(
    ds: pd.Series, 
    theme_color: Literal['light', 'dark'] = 'light', 
    element_ids: list[Literal["costs", "electrical_consumptions", "cooling_power", "hydraulic_configuration"]] = None,
    title_value_type: Literal["absolute", "specific"] | None = "absolute",
    base_var_id: str = "Qc_released",
    title_text: str = "<b>Year averages</b>",
    width: int = 1400,
) -> go.Figure:
    
    if element_ids is None:
        element_ids = list(plot_metadata.keys())
    else:
        for el_id in element_ids:
            assert el_id in plot_metadata.keys(), f"Unsupported element {el_id}, options are: {list(plot_metadata.keys())}"
        
    fig = make_subplots(rows=1, cols=len(element_ids), specs=[[{"type": "pie"}]*len(element_ids)])

    for col_idx, el_id in enumerate(element_ids):
        el_data = plot_metadata[el_id]
        
        # Build text, 💩 code
        if title_value_type is not None and el_data["title"].get("variants", None) is not None:
            if title_value_type not in el_data["title"]["variants"]:
                title_value_type = "absolute"
            title_value = ds[el_data["var_ids"]["base"]]
            if title_value_type == "absolute":
                title_value = f"{title_value:,.2f}"
            else:
                title_value = f"{title_value / ds[base_var_id]:.2e}"
            title_aux = f'<br>{title_value} {el_data["title"].get("variants", {title_value_type:""})[title_value_type]}'
        else:
            title_aux = ""
        
        fig.add_trace(
            go.Pie(
                labels=el_data["labels"],
                values=[ds[var_id]/ds[el_data["var_ids"]["base"]]*100 for var_id in el_data["var_ids"]["components"]],
                marker=dict(colors=el_data["colors"],
                            line=dict(color=el_data.get("line_colors", ["rgba(0,0,0,0)"]*len(el_data["colors"])), width=3),
                            pattern=dict(bgcolor=el_data["colors"], fgcolor=el_data.get("pattern_colors", ["rgba(0,0,0,0)"]*len(el_data["colors"])), shape="/"),),
                showlegend=False,
                title=dict(
                    text=f'<b>{el_data["title"]["text"]}</b>{title_aux}',
                    font=dict(size=20),
                ),
                hole=.5,
                textposition='auto', # ['inside', 'outside', 'auto', 'none']
                texttemplate='<b>%{label}</b><br>%{value:.1f} %</br>',
                textinfo='label+percent',  # Display labels and percentages inside slices
                insidetextorientation='radial',  # Display text radially inside slices,
                textfont_size=18,
                sort=False,
            ),
            row=1, col=col_idx+1,
        )


    # Update layout
    fig.update_layout(
        title_text=title_text,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=400,
        width=width,
        # autosize=True,
        margin=dict(t=50, b=0, l=5, r=5),
        template='ggplot2' if theme_color == 'light' else 'plotly_dark',
        uniformtext_minsize=16
        # width=500
    )
    
    for pie_data, el_id in zip(fig.data, element_ids):
        if "domain" in plot_metadata[el_id]:
            pie_data.domain.x = plot_metadata[el_id]["domain"]
    
    return fig