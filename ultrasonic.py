import time
import RPi.GPIO as GPIO
import requests
import os
import random

# Set up GPIO mode
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)  # Disable GPIO warnings

# Define GPIO pins for the HC-SR04
TRIGGER_PIN = 23
ECHO_PIN = 24

# Set up the trigger and echo pins
GPIO.setup(TRIGGER_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)

# Bin configurations (real bin and dummy bins)
bins = [
    {"id": 123, "height": 26.0, "is_real": True},  # Real bin with sensor
    #{"id": 456, "height": 36.0, "is_real": False},  # Dummy bin 1
    #{"id": 789, "height": 46.0, "is_real": False},  # Dummy bin 2
    #{"id": 101, "height": 25.0, "is_real": False},  # Dummy bin 3
    #{"id": 202, "height": 40.0, "is_real": False},  # Dummy bin 4
    #{"id": 303, "height": 50.0, "is_real": False}   # Dummy bin 5
]

# Notification flags for each bin
notifications_sent = {bin_data['id']: False for bin_data in bins}
last_fill_percentage = {bin_data['id']: None for bin_data in bins}

# Laravel API credentials and URL
API_URL = "http://binradar-laravel:8000/api"
TOKEN = os.getenv("API_TOKEN", "TPjnqafyEQB9adawJrF18jugzH6n4ZyoYkYsOOdy8a84107f")  # Admin token

def get_distance(bin_height, retries=5, is_real=True):
    if is_real:
        for _ in range(retries):
            try:
                # Send a pulse to the trigger pin
                GPIO.output(TRIGGER_PIN, GPIO.LOW)
                time.sleep(0.5)
                GPIO.output(TRIGGER_PIN, GPIO.HIGH)
                time.sleep(0.00001)
                GPIO.output(TRIGGER_PIN, GPIO.LOW)

                # Wait for the echo pin to go high
                pulse_start = time.time()
                timeout_start = pulse_start
                while GPIO.input(ECHO_PIN) == GPIO.LOW:
                    pulse_start = time.time()
                    if pulse_start - timeout_start > 2:  # Timeout after 2 seconds
                        raise Exception("No response from sensor (potential wiring issue).")

                pulse_end = time.time()
                while GPIO.input(ECHO_PIN) == GPIO.HIGH:
                    pulse_end = time.time()

                # Calculate pulse duration
                pulse_duration = pulse_end - pulse_start

                # Calculate distance in centimeters
                distance = pulse_duration * 17150
                distance = round(distance, 2)

                # Validate distance (within a reasonable range for your bin)
                if 2 < distance < bin_height:
                    return distance
                time.sleep(0.1)
            except Exception as e:
                print(f"Error: {e}")
                return None  # Return None if sensor fails multiple times
        return bin_height  # Return maximum bin height if sensor fails
    else:
        # Simulate distance for dummy bins
        return round(random.uniform(0, bin_height), 2)

def calculate_fill_level(distance, bin_height):
    # Calculate the filled portion of the bin
    fill_level_cm = bin_height - distance

    # Ensure fill level is within 0 to bin_height
    fill_level_cm = max(0, min(fill_level_cm, bin_height))

    # Calculate fill percentage
    fill_percentage = (fill_level_cm / bin_height) * 100
    return int(fill_percentage)

def send_data_to_server(bin_id, fill_percentage, token):
    url = f"{API_URL}/bins/{bin_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = {"fill_percentage": fill_percentage}

    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print(f"Data sent successfully for bin {bin_id}.")
        else:
            print(f"Failed to send data for bin {bin_id}. Status code: {response.status_code}")
            print(f"Response Content: {response.text}")
    except requests.RequestException as e:
        print(f"Error sending data for bin {bin_id}: {e}")

def send_notification(bin_id, message, token, notification_type="alert"):
    url = f"{API_URL}/notifications"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    data = {
        "message": message,
        "type": notification_type,  # Use "alert" for bin level, "error" for wiring issues
        "bin_id": bin_id
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        print(f"Sending {notification_type} notification for bin {bin_id}: {data}")
        if response.status_code == 200:
            print(f"{notification_type.capitalize()} notification sent successfully for bin {bin_id}.")
        else:
            print(f"Failed to send {notification_type} notification for bin {bin_id}. Status code: {response.status_code}")
            print(f"Response Content: {response.text}")
    except requests.RequestException as e:
        print(f"Error sending {notification_type} notification for bin {bin_id}: {e}")

def main():
    try:
        while True:
            for bin_data in bins:
                bin_id = bin_data["id"]
                bin_height = bin_data["height"]
                is_real = bin_data["is_real"]

                distance = get_distance(bin_height, is_real=is_real)

                # If distance is None, it indicates a sensor/wiring issue
                if distance is None:
                    print(f"Warning: Potential wiring issue detected for bin {bin_id}.")
                    send_notification(bin_id, "sensor or wiring issue", TOKEN, notification_type="error")
                    continue  # Skip further processing for this bin until the issue is resolved

                fill_percentage = calculate_fill_level(distance, bin_height)
                print(f"Bin {bin_id} fill level: {fill_percentage}%")

                # Only send data if fill percentage changes significantly
                if last_fill_percentage[bin_id] is None or abs(last_fill_percentage[bin_id] - fill_percentage) >= 2:
                    send_data_to_server(bin_id, fill_percentage, TOKEN)
                    last_fill_percentage[bin_id] = fill_percentage

                # Check if the bin is 80% or more filled and send a notification if it hasn't been sent yet
                if fill_percentage >= 80 and not notifications_sent[bin_id]:
                    print(f"Alert: Bin {bin_id} has reached {fill_percentage}% of its capacity!")
                    send_notification(bin_id, f"{fill_percentage}% full", TOKEN, notification_type="alert")
                    notifications_sent[bin_id] = True  # Ensure notification is sent only once

                # Check if the bin is emptied below 80% to reset the notification flag
                if fill_percentage < 80:
                    notifications_sent[bin_id] = False  # Reset the notification flag

            time.sleep(20)  # Adjust the delay as needed
    except KeyboardInterrupt:
        print("Program stopped.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
