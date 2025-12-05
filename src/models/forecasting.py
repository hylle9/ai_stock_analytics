import pandas as pd
from prophet import Prophet
import logging

# Suppress Prophet logs
logging.getLogger('cmdstanpy').setLevel(logging.WARNING)
logging.getLogger('prophet').setLevel(logging.WARNING)

class ForecastModel:
    """
    Time-series forecasting using Prophet.
    """
    def __init__(self):
        self.model = None

    def train_predict(self, df: pd.DataFrame, periods: int = 30) -> pd.DataFrame:
        """
        Train Prophet model on OHLCV data and predict future prices.
        
        Args:
            df: DataFrame with 'close' column and DatetimeIndex
            periods: Number of days to forecast
            
        Returns:
            DataFrame with columns ['ds', 'yhat', 'yhat_lower', 'yhat_upper']
        """
        if df.empty or 'close' not in df.columns:
            return pd.DataFrame()

        # Prepare data for Prophet
        # Prophet requires columns 'ds' (date) and 'y' (value)
        data = df.reset_index()[['Date', 'close']].rename(columns={'Date': 'ds', 'close': 'y'})
        
        # Handle timezone if present (Prophet prefers tz-naive)
        if data['ds'].dt.tz is not None:
            data['ds'] = data['ds'].dt.tz_localize(None)

        # Initialize and fit model
        self.model = Prophet(daily_seasonality=True, yearly_seasonality=True)
        self.model.fit(data)

        # Create future dataframe
        future = self.model.make_future_dataframe(periods=periods)
        
        # Predict
        forecast = self.model.predict(future)
        
        return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
