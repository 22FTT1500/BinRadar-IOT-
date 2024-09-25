import time
import RPi.GPIO as GPIO
import requests
import os

# Set up GPIO mode
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Define GPIO pins for the HC-SR04
TRIGGER_PIN = 23
ECHO_PIN = 24

# Set up the trigger and echo pins
GPIO.setup(TRIGGER_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)

# Bin dimensions
BIN_HEIGHT_CM = 26.0
BIN_ID = 123  # Update with your actual bin ID

# Laravel API credentials and URL
API_URL = "http://binradar-laravel:8000/api"
BIN_ENDPOINT = f"{API_URL}/bins/{BIN_ID}" 
NOTIFICATION_ENDPOINT = f"{API_URL}/notifications"
TOKEN = os.getenv("API_TOKEN", "E0kxzho0BW96KcBXRMIoB5q6DAoYpJwgT7AI3xJz3e6103c1")

notification_sent = False

def get_distance(retries=5):
    for _ in range(retries):
        GPIO.output(TRIGGER_PIN, GPIO.LOW)
        time.sleep(0.5)
        GPIO.output(TRIGGER_PIN, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(TRIGGER_PIN, GPIO.LOW)

        pulse_start = time.time()
        while GPIO.input(ECHO_PIN) == GPIO.LOW:
            pulse_start = time.time()
        pulse_end = time.time()
        while GPIO.input(ECHO_PIN) == GPIO.HIGH:
            pulse_end = time.time()

        pulse_duration = pulse_end - pulse_start
        distance = pulse_duration * 17150
        distance = round(distance, 2)

        if 2 < distance < BIN_HEIGHT_CM:
            return distance
        time.sleep(0.1)
    return BIN_HEIGHT_CM  # Default to max height

def calculate_fill_level(distance):
    fill_level_cm = BIN_HEIGHT_CM - distance
    fill_level_cm = max(0, min(fill_level_cm, BIN_HEIGHT_CM))
    fill_percentage = (fill_level_cm / BIN_HEIGHT_CM) * 100
    return int(fill_percentage)

def send_data_to_server(fill_percentage, token):
    url = BIN_ENDPOINT
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = {"fill_percentage": fill_percentage}

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
        print("Data sent successfully.")
    except requests.RequestException as e:
        print(f"Error sending data: {e}")

def send_notification(fill_percentage, token):
    url = NOTIFICATION_ENDPOINT
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    message = f"{fill_percentage}%"

    data = {
        "message": message,
        "type": "alert",
        "bin_id": BIN_ID
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
        print("Notification sent successfully.")
    except requests.RequestException as e:
        print(f"Error sending notification: {e}")

def main():
    global notification_sent
    last_fill_percentage = None

    try:
        while True:
            distance = get_distance()
            fill_percentage = calculate_fill_level(distance)
            print(f"Bin fill level: {fill_percentage}%")

            if last_fill_percentage is None or abs(last_fill_percentage - fill_percentage) >= 2:
                send_data_to_server(fill_percentage, TOKEN)
                last_fill_percentage = fill_percentage

            if fill_percentage >= 50 and not notification_sent:
                message = f"Alert: The bin has reached {fill_percentage}% of its capacity!"
                print(message)
                send_notification(fill_percentage, TOKEN)
                notification_sent = True

            if fill_percentage < 50:
                notification_sent = False
                print(f"Notification flag reset. Current fill level: {fill_percentage}%")

            time.sleep(5)  # Adjust delay as needed
    except KeyboardInterrupt:
        print("Program stopped.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
