import time
import RPi.GPIO as GPIO
import requests
import os

# Set up GPIO mode
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)  # Disable GPIO warnings

# Define GPIO pins for the HC-SR04
TRIGGER_PIN = 23
ECHO_PIN = 24

# Set up the trigger and echo pins
GPIO.setup(TRIGGER_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)

# Bin dimensions
BIN_HEIGHT_CM = 26.0  # Replace with the actual height of your bin in cm

# Notification flag
notification_sent = False

# Bin id 
BIN_ID = 1 # Update with your actual bin ID

# Laravel API credentials and URL
API_URL = "http://192.168.100.196:8000/api" #Update with your actual IP Address
BIN_ENDPOINT = f"{API_URL}/bins/{BIN_ID}"  # Update with your actual bin ID
NOTIFICATION_ENDPOINT = f"{API_URL}/notifications"
TOKEN = os.getenv("API_TOKEN", "f3YBgU7j71eC8U2CadwMLOMmwMdVi0hR7nerEAPgcc5bd95d")  # Load from environment

def get_distance(retries=5):
    for _ in range(retries):
        # Send a pulse to the trigger pin
        GPIO.output(TRIGGER_PIN, GPIO.LOW)
        time.sleep(0.5)
        GPIO.output(TRIGGER_PIN, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(TRIGGER_PIN, GPIO.LOW)

        # Wait for the echo pin to go high
        pulse_start = time.time()
        while GPIO.input(ECHO_PIN) == GPIO.LOW:
            pulse_start = time.time()

        pulse_end = time.time()
        while GPIO.input(ECHO_PIN) == GPIO.HIGH:
            pulse_end = time.time()

        # Calculate pulse duration
        pulse_duration = pulse_end - pulse_start

        # Calculate distance in centimeters
        distance = pulse_duration * 17150
        distance = round(distance, 2)

        # Validate distance (within a reasonable range for your bin)
        if 2 < distance < BIN_HEIGHT_CM:
            return distance
        time.sleep(0.1)
    return BIN_HEIGHT_CM  # Return maximum bin height if sensor fails

def calculate_fill_level(distance):
    # Calculate the filled portion of the bin
    fill_level_cm = BIN_HEIGHT_CM - distance

    # Ensure fill level is within 0 to BIN_HEIGHT_CM
    fill_level_cm = max(0, min(fill_level_cm, BIN_HEIGHT_CM))

    # Calculate fill percentage
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
        if response.status_code == 200:
            print("Data sent successfully.")
        else:
            print(f"Failed to send data. Status code: {response.status_code}")
            print(f"Response Content: {response.text}")
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
        if response.status_code == 200:
            print("Notification sent successfully.")
        else:
            print(f"Failed to send notification. Status code: {response.status_code}")
            print(f"Response Content: {response.text}")
    except requests.RequestException as e:
        print(f"Error sending notification: {e}")


def main():
    global notification_sent  # Declare notification_sent as global
    last_fill_percentage = None  # To track the previous fill percentage

    try:
        while True:
            distance = get_distance()
            fill_percentage = calculate_fill_level(distance)
            print(f"Bin fill level: {fill_percentage}%")

            # Only send data if fill percentage changes significantly
            if last_fill_percentage is None or abs(last_fill_percentage - fill_percentage) >= 2:
                send_data_to_server(fill_percentage, TOKEN)
                last_fill_percentage = fill_percentage

            # Check if the bin is 50% or more filled and send a notification if it hasn't been sent yet
            if fill_percentage >= 50 and not notification_sent:
                message = f"Alert: The bin has reached {fill_percentage}% of its capacity!"
                print(message)  # Print the alert message before sending the notification
                send_notification(fill_percentage, TOKEN)
                notification_sent = True  # Ensure notification is sent only once

            # Check if the bin is emptied below 50% to reset the notification flag
            if fill_percentage < 50:
                notification_sent = False  # Reset the notification flag
                print(f"Notification flag reset. Current fill level: {fill_percentage}%")

            time.sleep(30)  # Adjust the delay as needed (increased to 30s for better efficiency)
    except KeyboardInterrupt:
        print("Program stopped.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
