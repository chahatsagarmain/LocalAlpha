import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.io as pio

def generate_interactive_chart(df: pd.DataFrame, ticker: str) -> str:
    """
    Generates a synchronized three-tier interactive Plotly chart:
    1. Candlestick with Bollinger Bands
    2. RSI (14) with overbought/oversold bands
    3. MACD line, signal line, and color-coded histogram
    Returns a standalone HTML div snippet.
    """
    df = df.copy()
    # Format index for cleaner x-axis labeling without gap weekends
    df.index = df.index.strftime('%Y-%m-%d')
    
    # Create subplots synced on X-axis (shared_xaxes=True)
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.55, 0.22, 0.23],
        subplot_titles=(
            f"{ticker} Price & Bollinger Bands (20, 2)",
            "Relative Strength Index (RSI, 14)",
            "MACD (12, 26, 9) Crossover"
        )
    )
    
    # 1. Row 1: Candlestick overlay
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name="Price",
            increasing_line_color='#26a69a',  # Professional mint green
            decreasing_line_color='#ef5350'   # Professional crimson red
        ),
        row=1, col=1
    )
    
    # Bollinger Bands Lines
    if 'BBU_20_2.0' in df.columns and 'BBL_20_2.0' in df.columns and 'BBM_20_2.0' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['BBU_20_2.0'],
                line=dict(color='rgba(233, 236, 239, 0.4)', width=1, dash='dash'),
                name="BB Upper",
                legendgroup="bb"
            ),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['BBM_20_2.0'],
                line=dict(color='rgba(255, 193, 7, 0.7)', width=1.2),
                name="BB Middle (SMA 20)",
                legendgroup="bb"
            ),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['BBL_20_2.0'],
                line=dict(color='rgba(233, 236, 239, 0.4)', width=1, dash='dash'),
                name="BB Lower",
                legendgroup="bb"
            ),
            row=1, col=1
        )
        
    # 2. Row 2: RSI Line
    if 'RSI_14' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['RSI_14'],
                line=dict(color='#2196f3', width=1.5),
                name="RSI (14)"
            ),
            row=2, col=1
        )
        # Red Overbought line (70)
        fig.add_shape(
            type="line", x0=df.index[0], y0=70, x1=df.index[-1], y1=70,
            line=dict(color="#ef5350", width=1, dash="dot"),
            row=2, col=1
        )
        # Green Oversold line (30)
        fig.add_shape(
            type="line", x0=df.index[0], y0=30, x1=df.index[-1], y1=30,
            line=dict(color="#26a69a", width=1, dash="dot"),
            row=2, col=1
        )
        
    # 3. Row 3: MACD Lines and Histogram
    if 'MACD_12_26_9' in df.columns and 'MACDs_12_26_9' in df.columns and 'MACDh_12_26_9' in df.columns:
        # MACD Line
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['MACD_12_26_9'],
                line=dict(color='#ff9800', width=1.2),
                name="MACD"
            ),
            row=3, col=1
        )
        # Signal Line
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['MACDs_12_26_9'],
                line=dict(color='#9c27b0', width=1.2),
                name="Signal Line"
            ),
            row=3, col=1
        )
        # Histogram bars
        hist_colors = ['rgba(38, 166, 154, 0.75)' if val >= 0 else 'rgba(239, 83, 80, 0.75)' for val in df['MACDh_12_26_9']]
        fig.add_trace(
            go.Bar(
                x=df.index, y=df['MACDh_12_26_9'],
                marker_color=hist_colors,
                name="Histogram"
            ),
            row=3, col=1
        )
        
    # Dark Mode Premium Aesthetics Configuration
    fig.update_layout(
        template="plotly_dark",
        height=760,
        margin=dict(l=40, r=20, t=50, b=40),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0, 0, 0, 0)"
        ),
        paper_bgcolor="rgba(24, 26, 27, 0.95)",
        plot_bgcolor="rgba(18, 18, 18, 0.95)",
        font=dict(family="Outfit, Inter, sans-serif", size=11, color="#E9ECEF")
    )
    
    # Hide rangesliders for all axes and sync grids
    fig.update_xaxes(
        rangeslider_visible=False,
        gridcolor="rgba(255, 255, 255, 0.08)",
        linecolor="rgba(255, 255, 255, 0.1)"
    )
    fig.update_yaxes(
        gridcolor="rgba(255, 255, 255, 0.08)",
        linecolor="rgba(255, 255, 255, 0.1)"
    )
    
    # Return raw div code with CDN plotly integration
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
