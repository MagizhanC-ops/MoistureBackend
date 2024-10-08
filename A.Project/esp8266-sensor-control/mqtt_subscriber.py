import paho.mqtt.client as mqtt

MQTT_BROKER = "192.168.0.205"
MQTT_PORT = 1883
MQTT_TOPIC = "esp8266/sensor/data"

# Global variable to store the latest moisture percentage
latest_moisture = None

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global latest_moisture
    print(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
    try:
        # Assuming the message is a string containing the moisture percentage
        latest_moisture = float(msg.payload.decode())
        print(f"Updated latest moisture: {latest_moisture}%")
    except ValueError:
        print(f"Received invalid moisture value: {msg.payload.decode()}")

def run_subscriber():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

def get_latest_moisture():
    return latest_moisture

if __name__ == "__main__":
    run_subscriber()
