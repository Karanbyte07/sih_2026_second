import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
import joblib
import os

def train_forecasting_models():
    print("Loading telemetry dataset...")
    df = pd.read_csv('data/telemetry_dataset.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(by=['station_id', 'timestamp'])
    
    # Feature Engineering for time-series
    df['hour'] = df['timestamp'].dt.hour
    df['day'] = df['timestamp'].dt.dayofyear
    
    # Create lag features for demand forecasting
    # Predicting next hour demand based on current state
    df['next_power'] = df.groupby('station_id')['power_consumption_kw'].shift(-4) # 4 * 15min = 1 hour ahead
    
    # Drop rows with NaN (due to shift)
    train_df = df.dropna().copy()
    
    features = ['temperature', 'vibration', 'load_kw', 'power_consumption_kw', 'pressure', 'hour', 'day']
    X = train_df[features]
    
    # 1. Energy Forecasting Model
    y_energy = train_df['next_power']
    print("Training GradientBoosting Energy Forecasting Model...")
    energy_model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42)
    energy_model.fit(X, y_energy)
    
    # 2. Inventory (Fuel) Forecasting Model
    # Predicting fuel consumption for next hour
    train_df['next_fuel'] = train_df.groupby('station_id')['fuel_consumption'].shift(-4)
    train_df = train_df.dropna()
    y_fuel = train_df['next_fuel']
    
    print("Training GradientBoosting Fuel Forecasting Model...")
    fuel_model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42)
    fuel_model.fit(train_df[features], y_fuel)
    
    os.makedirs('models', exist_ok=True)
    joblib.dump(energy_model, 'models/energy_model.joblib')
    joblib.dump(fuel_model, 'models/fuel_model.joblib')
    
    print("Models trained and saved successfully.")

if __name__ == "__main__":
    train_forecasting_models()
