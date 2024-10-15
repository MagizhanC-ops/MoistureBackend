from flask import Flask, render_template, jsonify, request
import paho.mqtt.client as mqtt
import threading
import json
import joblib
import pandas as pd
import time
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load the trained model
model = joblib.load('humidity_model.joblib')

MQTT_BROKER = "192.168.137.4"
MQTT_PORT = 1883
MQTT_TOPIC_MEASURE = "esp8266/sensor/measure"
MQTT_TOPIC_DATA = "esp8266/sensor/data"

client = mqtt.Client()
latest_moisture = None
moisture_event = threading.Event()

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC_DATA)

def on_message(client, userdata, message):
    global latest_moisture
    print(f"Received message on topic {message.topic}: {message.payload.decode()}")
    try:
        payload = message.payload.decode('utf-8')
        latest_moisture = float(payload)
        moisture_event.set()
        print(f"Updated latest_moisture: {latest_moisture}")
    except ValueError:
        print(f"Invalid moisture value received: {payload}")

client.on_connect = on_connect
client.on_message = on_message

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/publish_measure', methods=['POST'])
def publish_measure():
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.publish(MQTT_TOPIC_MEASURE, "Measure")
        client.disconnect()
        return jsonify({"status": "success", "message": "Measure command published"})
    except Exception as e:
        logger.error(f"Error publishing measure command: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/process_data', methods=['POST'])
def process_data():
    global latest_moisture
    data = request.json
    logger.debug(f"Received data: {data}")
    
    moisture_event.clear()
    latest_moisture = None
    
    logger.info("Publishing measure command...")
    try:
        client.publish(MQTT_TOPIC_MEASURE, "Measure")
    except Exception as e:
        logger.error(f"Error publishing measure command: {e}")
        return jsonify({"status": "error", "message": "Failed to publish measure command"}), 500
    
    logger.info("Waiting for moisture measurement...")
    start_time = time.time()
    while time.time() - start_time < 10:
        if moisture_event.is_set():
            break
        time.sleep(0.1)
    
    if latest_moisture is None:
        logger.warning("No moisture measurement received within timeout")
        # Provide default values for classification
        latest_moisture = 50.0  # Default to 50% moisture
        predicted_humidity = 60.0  # Default predicted optimal humidity
    else:
        logger.info(f"Received moisture measurement: {latest_moisture}")
        
        try:
            def safe_float(value, default=0.0):
                try:
                    return float(value) if value is not None else default
                except ValueError:
                    return default

            model_input = pd.DataFrame({
                'label': [str(data.get('cropType', ''))],
                'temperature': [safe_float(data.get('temperature'))],
                'N': [safe_float(data.get('nitrogen'))],
                'P': [safe_float(data.get('phosphorus'))],
                'K': [safe_float(data.get('potassium'))],
                'ph': [safe_float(data.get('ph'))]
            })
            
            predicted_humidity = model.predict(model_input)[0]
            logger.info(f"Predicted optimal humidity: {predicted_humidity}")
            
            # Define moisture thresholds
            critical_low = 20  # Critical low threshold
            low_threshold = max(30, predicted_humidity * 0.8)
            high_threshold = min(80, predicted_humidity * 1.2)
            critical_high = 90  # Critical high threshold
            
            # Classify soil moisture
            latest_moisture = safe_float(latest_moisture)
            if latest_moisture < critical_low:
                moisture_status = "Severely Under-irrigated"
            elif latest_moisture < low_threshold:
                moisture_status = "Under-irrigated"
            elif latest_moisture > critical_high:
                moisture_status = "Severely Over-irrigated"
            elif latest_moisture > high_threshold:
                moisture_status = "Over-irrigated"
            else:
                moisture_status = "Optimal"
            
            # Calculate adjusted moisture (weighted average favoring measured moisture)
            adjusted_moisture = (0.9 * latest_moisture + 0.1 * predicted_humidity)
            
            response_data = {
                "measured_moisture": latest_moisture,
                "predicted_optimal_humidity": predicted_humidity,
                "adjusted_moisture": adjusted_moisture,
                "moisture_status": moisture_status,
                "critical_low": critical_low,
                "low_threshold": low_threshold,
                "high_threshold": high_threshold
            }
            
            logger.info(f"Response data: {response_data}")
            
            return jsonify({"status": "success", "processed_data": response_data})
        except KeyError as e:
            logger.error(f"Missing required input field: {e}")
            return jsonify({"status": "error", "message": f"Missing required input field: {e}"}), 400
        except ValueError as e:
            logger.error(f"Invalid input value: {e}")
            return jsonify({"status": "error", "message": f"Invalid input value: {e}"}), 400
        except Exception as e:
            logger.error(f"Error processing data: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

def run_mqtt_client():
    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_forever()
        except Exception as e:
            print(f"MQTT connection error: {e}")
            time.sleep(5)  # Wait for 5 seconds before trying to reconnect

if __name__ == '__main__':
    mqtt_thread = threading.Thread(target=run_mqtt_client)
    mqtt_thread.daemon = True
    mqtt_thread.start()
    
    logger.info("Starting Flask application...")
    app.run(debug=True, use_reloader=False)
