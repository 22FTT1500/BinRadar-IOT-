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
    {"id": 456, "height": 36.0, "is_real": False},  # Dummy bin 1
    {"id": 789, "height": 46.0, "is_real": False},  # Dummy bin 2
    {"id": 101, "height": 25.0, "is_real": False},  # Dummy bin 3
    {"id": 202, "height": 40.0, "is_real": False},  # Dummy bin 4
    {"id": 303, "height": 50.0, "is_real": False}   # Dummy bin 5
]

# Notification flags for each bin
notifications_sent = {bin_data['id']: {'error': False, 'recovered': False, 'alerted': False} for bin_data in bins}
last_fill_percentage = {bin_data['id']: None for bin_data in bins}

# Laravel API credentials and URL
API_URL = "http://binradar-laravel:8000/api"
TOKEN = os.getenv("API_TOKEN", "WUOArY94LsUNAmzRZQm5MOuMhMhfXA8jPCjTzKgD97808dd8")  # Admin token

def get_threshold_from_db(bin_id, token):
    url = f"{API_URL}/bins/{bin_id}/threshold"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get('threshold', 80)  # Default to 80 if not found
        else:
            print(f"Failed to fetch threshold for bin {bin_id}. Status code: {response.status_code}")
            return 80  # Fallback value if request fails
    except requests.RequestException as e:
        print(f"Error fetching threshold for bin {bin_id}: {e}")
        return 80  # Fallback value

def get_notification_methods_from_db(bin_id, token):
    url = f"{API_URL}/bins/{bin_id}/notification-methods"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get('notification_methods', ['email', 'website'])  # Default preferences
        else:
            print(f"Failed to fetch notification methods for bin {bin_id}. Status code: {response.status_code}")
            return ['email', 'website']  # Fallback value
    except requests.RequestException as e:
        print(f"Error fetching notification methods for bin {bin_id}: {e}")
        return ['email', 'website']  # Fallback value

def get_distance(bin_height, retries=5, is_real=True):
    if is_real:
        for _ in range(retries):
            try:
                GPIO.output(TRIGGER_PIN, GPIO.LOW)
                time.sleep(0.5)
                GPIO.output(TRIGGER_PIN, GPIO.HIGH)
                time.sleep(0.00001)
                GPIO.output(TRIGGER_PIN, GPIO.LOW)

                pulse_start = time.time()
                timeout_start = pulse_start
                while GPIO.input(ECHO_PIN) == GPIO.LOW:
                    pulse_start = time.time()
                    if pulse_start - timeout_start > 2:  # Timeout after 2 seconds
                        raise Exception("No response from sensor (potential wiring issue).")

                pulse_end = time.time()
                while GPIO.input(ECHO_PIN) == GPIO.HIGH:
                    pulse_end = time.time()

                pulse_duration = pulse_end - pulse_start
                distance = pulse_duration * 17150
                distance = round(distance, 2)

                if 2 < distance < bin_height:
                    return distance
                time.sleep(0.1)
            except Exception as e:
                print(f"Error: {e}")
                return None
        return bin_height
    else:
        return round(random.uniform(0, bin_height), 2)

def calculate_fill_level(distance, bin_height):
    fill_level_cm = bin_height - distance
    fill_level_cm = max(0, min(fill_level_cm, bin_height))
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
            print(f"FAILED to send data for bin {bin_id}. Status code: {response.status_code}")
            print(f"Response Content: {response.text}")
    except requests.RequestException as e:
        print(f"Error sending data for bin {bin_id}: {e}")

def send_notification(bin_id, message, token, notification_type):
    url = f"{API_URL}/notifications"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    data = {
        "message": message,
        "type": notification_type,
        "bin_id": bin_id
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print(f"Sending notification..")
        else:
            print(f"FAILED to send {notification_type} notification for bin {bin_id}. Status code: {response.status_code}")
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

                if distance is None:
                    print(f"Warning: Potential wiring issue detected for bin {bin_id}.")
                    if not notifications_sent[bin_id]['error']:
                        send_notification(bin_id, "Sensor or wiring issue", TOKEN, notification_type="error")
                        notifications_sent[bin_id]['error'] = True
                    continue

                if notifications_sent[bin_id]['error']:
                    send_notification(bin_id, "Sensor is responding again", TOKEN, notification_type="recovered")
                    notifications_sent[bin_id]['error'] = False
                    notifications_sent[bin_id]['recovered'] = True

                fill_percentage = calculate_fill_level(distance, bin_height)
                
                # Print fill level
                print(f"Bin {bin_id} fill level: {fill_percentage}%")

                # Get the threshold from the database for the current bin
                threshold = get_threshold_from_db(bin_id, TOKEN)

                # Check if we need to send an alert
                if fill_percentage >= threshold and not notifications_sent[bin_id].get('alerted', False):
                    alert_message = f"Alert: Bin {bin_id} has reached {fill_percentage}% of its capacity!"
                    print(alert_message)  # Print alert message
                    notifications_sent[bin_id]['alerted'] = True

                # Fetch notification methods for the current bin
                notification_methods = get_notification_methods_from_db(bin_id, TOKEN)
                print(f"Notification methods for bin {bin_id}: {notification_methods}")

                # If fill percentage is above threshold, send notification
                if fill_percentage >= threshold:
                    # Check if 'email' is in the notification methods before sending
                    if 'email' in notification_methods:
                        send_notification(bin_id, f"{fill_percentage}% full", TOKEN, notification_type="alert")
                        print(f"SUCCESSFUL sending email notification for bin {bin_id}.")
                        
                    # Always send website notification
                    print(f"SUCCESSFUL sending website notification for bin {bin_id}.")

                if fill_percentage < threshold:
                    notifications_sent[bin_id]['alerted'] = False  # Reset the alert notification flag

            time.sleep(20)  # Adjust the delay as needed
    except KeyboardInterrupt:
        print("Program stopped.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
