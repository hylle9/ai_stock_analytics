import plotly.graph_objects as go

def render_risk_gauge(value: float, title: str):
    """
    Renders a gauge chart representing portfolio volatility / risk.
    
    Args:
        value (float): The volatility value (0.0 to 1.0, e.g., 0.20 for 20%).
        title (str): Title of the chart.
        
    Returns:
        plotly.graph_objects.Figure: The gauge chart figure.
    """
    # Convert to percentage for display
    display_value = value * 100
    
    # Create a spectral gradient approximation using steps
    # Ranges: 0-100
    # Create a spectral gradient approximation using steps
    # Ranges: 0-100
    steps = [
        {'range': [0, 20], 'color': "#d73027"},   # Red
        {'range': [20, 40], 'color': "#fc8d59"},  # Orange-Red
        {'range': [40, 60], 'color': "#fee08b"},  # Yellow
        {'range': [60, 80], 'color': "#91cf60"},  # Light Green
        {'range': [80, 100], 'color': "#1a9850"}  # Dark Green
    ]

    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = display_value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 14}},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 0, 'tickcolor': "white", 'visible': False}, # Hide axis ticks for cleaner look
            'bar': {'color': "black", 'thickness': 0.3}, # Thinner marker
            'bgcolor': "white",
            'borderwidth': 0,
            'steps': steps,
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 1,
                'value': display_value
            }
        }
    ))
    
    fig.update_layout(height=180, margin=dict(l=30, r=30, t=30, b=30))
    return fig
