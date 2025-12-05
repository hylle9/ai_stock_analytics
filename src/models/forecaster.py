import pandas as pd
from prophet import Prophet
import numpy as np

def generate_forecast(df: pd.DataFrame, periods: int = 5) -> dict:
    """
    Generate forecasts using Prophet.
    
    Args:
        df: DataFrame with 'close' column and DatetimeIndex
        periods: Number of days to forecast
        
    Returns:
        Dictionary with forecast data and model confidence
    """
    if df.empty or len(df) < 30:
        return {"error": "Insufficient data for forecasting"}
    
    # Prepare data for Prophet
    # Prophet requires columns 'ds' (date) and 'y' (value)
    prophet_df = df.reset_index()[['Date', 'close']].rename(columns={'Date': 'ds', 'close': 'y'})
    
    # Initialize and fit model
    # We use a simple configuration for the MVP
    model = Prophet(daily_seasonality=True, yearly_seasonality=True)
    model.fit(prophet_df)
    
    # Create future dataframe
    future = model.make_future_dataframe(periods=periods)
    
    # Predict
    forecast = model.predict(future)
    
    # Extract relevant results
    # We want the last 'periods' rows for the forecast
    future_forecast = forecast.tail(periods)
    
    # Calculate expected returns
    current_price = df['close'].iloc[-1]
    
    forecast_1d = future_forecast.iloc[0]['yhat']
    return_1d = (forecast_1d - current_price) / current_price
    
    forecast_5d = future_forecast.iloc[-1]['yhat']
    return_5d = (forecast_5d - current_price) / current_price
    
    # Simple confidence metric (inverse of uncertainty interval width normalized by price)
    uncertainty = (future_forecast.iloc[0]['yhat_upper'] - future_forecast.iloc[0]['yhat_lower']) / forecast_1d
    confidence_score = max(0, 100 * (1 - uncertainty))
    
    return {
        "forecast_df": forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(periods + 30), # Return recent history + forecast
        "return_1d": return_1d,
        "return_5d": return_5d,
        "confidence_score": confidence_score
    }
