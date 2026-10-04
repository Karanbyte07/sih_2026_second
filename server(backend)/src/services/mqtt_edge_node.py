import json
import time
import queue
import threading
import paho.mqtt.client as mqtt

class EdgeGatewayNode:
    """
    Simulates the Edge Gateway at an Antarctic Station.
    Responsible for local buffering, validation, and forwarding telemetry via MQTT.
    """
    def __init__(self, station_id: str, broker_host: str = "localhost", broker_port: int = 1883):
        self.station_id = station_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        
        # Local short-term buffer for offline mode
        self.local_buffer = queue.Queue()
        self.is_online = False
        
        self.client = mqtt.Client(client_id=f"edge_gateway_{station_id}", protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        
        # Start a background thread to process the buffer and send to MQTT
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        
    def start(self):
        print(f"[{self.station_id} Edge] Starting gateway...")
        try:
            self.client.connect_async(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"[{self.station_id} Edge] Initial connect failed, running in OFFLINE mode: {e}")
        self.sync_thread.start()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[{self.station_id} Edge] Connected to MQTT broker (Cloud/Backend)")
            self.is_online = True
        else:
            print(f"[{self.station_id} Edge] Connection failed with code {rc}")
            
    def _on_disconnect(self, client, userdata, rc):
        print(f"[{self.station_id} Edge] Disconnected from MQTT broker. Switching to OFFLINE mode.")
        self.is_online = False
        
    def ingest_telemetry(self, asset_id: str, payload: dict):
        """
        Called when local SCADA/IoT adapter produces data.
        Validates and buffers locally.
        """
        # Validate (simple check)
        if 'timestamp' not in payload or 'load_kw' not in payload:
            print(f"[{self.station_id} Edge] Invalid telemetry payload from {asset_id}. Discarding.")
            return
            
        topic = f"station/{self.station_id}/asset/{asset_id}/telemetry"
        
        # Run local critical anomaly rule (Offline edge intelligence)
        if payload.get('temperature', 0) > 85.0:
            print(f"[{self.station_id} Edge] LOCAL ALERT: CRITICAL TEMPERATURE DETECTED ON {asset_id}!")
            
        # Buffer the data
        self.local_buffer.put({"topic": topic, "payload": payload, "qos": 1})
        
    def _sync_loop(self):
        """
        Continuously attempts to flush the local buffer to the cloud when online.
        """
        while True:
            if self.is_online and not self.local_buffer.empty():
                try:
                    # Peek at item
                    msg = self.local_buffer.queue[0]
                    
                    # Attempt to publish
                    payload_str = json.dumps(msg["payload"])
                    result = self.client.publish(msg["topic"], payload_str, qos=msg["qos"])
                    
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        # Successfully sent, remove from buffer
                        self.local_buffer.get()
                        print(f"[{self.station_id} Edge] Forwarded buffered message to {msg['topic']}")
                    else:
                        time.sleep(1) # Backoff
                except Exception as e:
                    print(f"[{self.station_id} Edge] Publish error: {e}")
                    time.sleep(2)
            else:
                time.sleep(0.5)

if __name__ == "__main__":
    # Test script for edge node
    gateway = EdgeGatewayNode(station_id="maitri")
    gateway.start()
    
    # Simulate incoming SCADA data while offline (no broker running by default)
    print("Simulating SCADA telemetry ingestion...")
    gateway.ingest_telemetry("gen1", {"timestamp": "2026-10-04T10:00:00Z", "load_kw": 50, "temperature": 40})
    gateway.ingest_telemetry("gen2", {"timestamp": "2026-10-04T10:00:00Z", "load_kw": 80, "temperature": 90}) # Should trigger local alert
    
    time.sleep(3)
    print(f"Current buffer size: {gateway.local_buffer.qsize()} items (waiting for connectivity)")
