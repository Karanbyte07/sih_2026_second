import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import joblib
import os

def train_anomaly_model():
    print("Loading synthetic telemetry dataset...")
    df = pd.read_csv('data/telemetry_dataset.csv')
    
    # Use normal operating data to train (or let isolation forest figure it out)
    # We will use temperature, vibration, load, power consumption, pressure, operating hours as features
    features = ['temperature', 'vibration', 'load_kw', 'power_consumption_kw', 'pressure', 'operating_hours']
    
    X = df[features]
    
    print("Training Isolation Forest model...")
    # Isolation forest for anomaly detection
    model = IsolationForest(n_estimators=100, contamination=0.02, random_state=42)
    model.fit(X)
    
    # Predict on training data to verify
    df['anomaly_pred'] = model.predict(X)
    df['anomaly_score'] = model.decision_function(X)
    
    # anomaly_pred: -1 is anomaly, 1 is normal
    anomalies_detected = (df['anomaly_pred'] == -1).sum()
    print(f"Model trained. Detected {anomalies_detected} anomalies out of {len(df)} records.")
    
    os.makedirs('models', exist_ok=True)
    joblib.dump(model, 'models/isolation_forest.joblib')
    print("Model saved to models/isolation_forest.joblib")

if __name__ == "__main__":
    train_anomaly_model()
