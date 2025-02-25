import plotly.graph_objects as go
import numpy as np

from solhycool_visualization import ComponentColors


def plot_hydraulic_distribution(qc: np.ndarray, Rp: np.ndarray, Rs: np.ndarray) -> go.Figure:
    qdc = qc * (1 - Rp)
    qwct_p = qc * Rp
    qwct_s = qdc * Rs
    x = np.arange(len(qc))
    
    # print(f"{qc=}, \n{qwct_p=}, \n{qdc=}, \n{qwct_s=}")

    fig = go.Figure()

    # Add stacked bars for qdc and qwct_p
    fig.add_trace(go.Bar(
        x=x,
        y=qdc,
        name='DC',
        marker=dict(color=ComponentColors.DC.value)
    ))

    fig.add_trace(go.Bar(
        x=x,
        y=qwct_p,
        name='WCT',
        marker=dict(color=ComponentColors.WCT.value)
    ))

    # Add shape for qwct_s starting from the end of qdc
    for i in range(len(qc)):
        # print(f"{qc[i]=:.0f}, {qdc[i]=:.0f}, {qwct_p[i]=:.0f}, {qwct_s[i]=:.0f}, {Rp[i]=}, {Rs[i]=}")
        fig.add_shape(
            type="rect",
            x0=x[i] - 0.4, x1=x[i] + 0.4,
            y0=qdc[i] - qwct_s[i], y1=qdc[i],
            line=dict(color=ComponentColors.WCT.value, width=5),
            # fillcolor="red",
            opacity=1,
            layer="above",
            name="DC 🠒 WCT",
            showlegend=True if i == 0 else False,
        )

    fig.update_layout(
        barmode='stack', 
        title=dict(text='<b>Hydraulic Distribution</b>', subtitle_text="of combined cooler"),
        yaxis_title='Flow rate (m³/h)',
        template='plotly_white',
        
    )
    
    return fig