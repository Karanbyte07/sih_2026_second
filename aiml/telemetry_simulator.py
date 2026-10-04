import pandas as pd
import numpy as np
import datetime
import random
import os

def generate_telemetry(station_id, start_date, num_days=30, interval_minutes=15):
    records = []
    current_time = start_date
    end_time = start_date + datetime.timedelta(days=num_days)
    
    # Base states
    temperature = -10.0
    vibration_base = 2.0
    load_base = 50.0 # kW
    
    operating_hours = 1000
    
    while current_time < end_time:
        # Time components
        hour = current_time.hour
        month = current_time.month
        
        # Diurnal temperature cycle + noise
        temp_cycle = 5 * np.sin(2 * np.pi * hour / 24.0)
        temperature = -15 + temp_cycle + random.uniform(-2, 2)
        
        # Lower temp -> higher heating demand -> higher load
        heating_demand = max(0, -5 - temperature) * 2.5
        load = load_base + heating_demand + random.uniform(-5, 5)
        
        # Power consumption is proportional to load
        power_consumption = load * 1.1 + random.uniform(-2, 2)
        
        # Fuel consumption (L/h roughly)
        fuel_consumption = power_consumption * 0.25
        
        # Vibration relates to load + noise
        vibration = vibration_base + (load / 100) + random.uniform(-0.1, 0.1)
        
        # Pressure (kPa)
        pressure = 980 + random.uniform(-10, 10)
        
        operating_hours += (interval_minutes / 60.0)
        
        # Inject anomalies (~2% of the time)
        is_anomaly = random.random() < 0.02
        if is_anomaly:
            anomaly_type = random.choice(['overheating', 'high_vibration', 'load_spike'])
            if anomaly_type == 'overheating':
                temperature += random.uniform(20, 40) # abnormal asset temp
            elif anomaly_type == 'high_vibration':
                vibration += random.uniform(3, 8)
            elif anomaly_type == 'load_spike':
                load += random.uniform(50, 100)
                power_consumption += 60
        
        records.append({
            'timestamp': current_time,
            'station_id': station_id,
            'asset_id': f'gen1_{station_id}',
            'temperature': round(temperature, 2),
            'vibration': round(vibration, 3),
            'load_kw': round(load, 2),
            'power_consumption_kw': round(power_consumption, 2),
            'pressure': round(pressure, 2),
            'operating_hours': round(operating_hours, 1),
            'fuel_consumption': round(fuel_consumption, 2),
            'is_anomaly': int(is_anomaly)
        })
        
        current_time += datetime.timedelta(minutes=interval_minutes)
        
    return pd.DataFrame(records)

if __name__ == "__main__":
    print("Generating synthetic telemetry for Maitri...")
    df_maitri = generate_telemetry('maitri', datetime.datetime(2025, 1, 1), num_days=60)
    
    print("Generating synthetic telemetry for Bharati...")
    df_bharati = generate_telemetry('bharati', datetime.datetime(2025, 1, 1), num_days=60)
    
    df_all = pd.concat([df_maitri, df_bharati], ignore_index=True)
    
    os.makedirs('data', exist_ok=True)
    df_all.to_csv('data/telemetry_dataset.csv', index=False)
    print(f"Dataset generated with {len(df_all)} records. Saved to data/telemetry_dataset.csv.")
