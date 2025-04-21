from plotly.subplots import make_subplots
import plotly.graph_objects as go
from plotly.colors import qualitative
import pandas as pd


def plot_samples(df: pd.DataFrame, var_ids: list[str] = None, Ncols: int = 3) -> go.Figure:
    # Taken from github.com/juan11iguel/med-performance-evaluation/dev/med_performance_evaluation/notebooks/sensitivity_analysis.ipynb
    # TODO: Add hover support so that when one point in one scatter subplot is hovered, the corresponding point in the other subplots are highlighted

    if var_ids is None:
        var_ids = df.columns.tolist()

    # Create a subplot
    Nrows = (len(var_ids) // Ncols) * 2

    max_n_samples = 1000
    sample_rate = len(df) // max_n_samples

    # Create title for each subplot
    var_idx=0
    subplot_titles = []
    # subplot_titles = var_ids
    for row_idx in range(0, Nrows, 2):
        for col_idx in range(1, Ncols+1):
            if var_idx >= len(var_ids):
                break
            subplot_titles.append(var_ids[var_idx])
            var_idx+=1
        subplot_titles.extend(['']*Ncols)

    fig = make_subplots(rows=Nrows, cols=Ncols,
                        row_heights=[0.2, 0.5] * (len(var_ids) // Ncols),
                        # vertical_spacing=0.01,
                        subplot_titles=subplot_titles,
                        # row_titles=[f"<b>{label}</b>" for label in ['Histogram', 'Scatter']] * (len(var_ids) // Ncols + 1),
                        )
    # fig.print_grid()
    # subplot_titles=[label for label in var_ids]

    var_idx = 0
    for row_idx in range(0, Nrows, 2):
        for col_idx in range(1, Ncols+1):
            if var_idx >= len(var_ids):
                break
                
            # logger.info(f'Plotting {var_ids[var_idx]} in rows {row_idx+1}-{row_idx+2}, col {col_idx}')
            color = qualitative.Plotly[var_idx % len(qualitative.Plotly)]
            
            # Add the histogram
            fig.add_trace(
                go.Histogram(
                    x=df[var_ids[var_idx]],
                    name=var_ids[var_idx],
                    histnorm='probability',
                    marker_color=color
                ),
                row=row_idx+1,
                col=col_idx,
            )
            
            # Add the scatter plot
            fig.add_trace(
                go.Scatter(
                    x=df.index[::sample_rate],
                    y=df[var_ids[var_idx]][::sample_rate],
                    mode='markers',
                    name=var_ids[var_idx],
                    marker=dict(
                        color=color,
                        size=3
                    ),
                ),
                row=row_idx+2,
                col=col_idx
            )
            
            if col_idx == 1:
                fig.update_yaxes(title_text="values", row=row_idx+2, col=col_idx)
            if row_idx == 0:
                fig.update_xaxes(title_text="samples", row=row_idx+2, col=col_idx)
            
            # fig.update_xaxes(title_text=unit_list[var_idx], row=row_idx+2, col=col_idx)
            
            var_idx += 1

    fig.update_layout(
        title_text=f'<b>Samples distribution</b><br>Showing every {sample_rate}th sample (total {len(df)} samples)',
        # title_pad=dict(t=50),
        height=200 * Nrows + 50,
        hoversubplots="axis",
        hovermode="x",
        showlegend=False,
        margin=dict(l=0, r=0, t=130, b=0,),
    )

    return fig