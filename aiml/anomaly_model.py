import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "data" / "telemetry_dataset.csv"
MODEL_DIR = BASE_DIR / "models"

def train_anomaly_model():
    print("Loading synthetic telemetry dataset...")
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Training dataset not found at {DATASET_PATH}. "
            "Run telemetry_simulator.py first or provide a validated telemetry export."
        )
    df = pd.read_csv(DATASET_PATH)
    
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
    
    MODEL_DIR.mkdir(exist_ok=True)
    output_path = MODEL_DIR / "isolation_forest.joblib"
    joblib.dump(model, output_path)
    print(f"Model saved to {output_path}")

if __name__ == "__main__":
    train_anomaly_model()
