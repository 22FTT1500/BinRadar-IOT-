import time # For adding delays in the code.
import RPi.GPIO as GPIO # A library for controlling the GPIO pins of the Raspberry Pi.
import requests # For making HTTP requests to the Laravel API.
import os # To access environment variables (e.g., for API tokens).
import random # To generate random numbers, used for dummy bins.

# Set up GPIO mode
GPIO.setmode(GPIO.BCM) # Sets the GPIO pin numbering mode to BCM (Broadcom SOC channel)
GPIO.setwarnings(False) # Suppresses warnings related to GPIO setup.

# Define GPIO pins for the HC-SR04
# The Trigger pin sends the signal, and the Echo pin receives the reflected signal.
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
notifications_sent = {bin_data['id']: {'error': False, 'recovered': False} for bin_data in bins}
last_fill_percentage = {bin_data['id']: None for bin_data in bins}

# Laravel API credentials and URL
API_URL = "http://binradar-laravel:8000/api"
TOKEN = os.getenv("API_TOKEN", "9JWyE7J6LM6ORw286sKECymckkDZSNDKXxNUWvL8e41620a8")  # Admin token

# Function to check if a bin exists in the database
def bin_exists_in_db(bin_id):
    url = f"{API_URL}/bins/{bin_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return True  # Bin exists
        elif response.status_code == 404:
            return False  # Bin does not exist
        else:
            print(f"Checking existence of bin {bin_id}.") 
            return False  
    except requests.RequestException as e:
        print(f"Error checking existence of bin {bin_id}: {e}") # Handling connection issues
        return False 
    
# Fetches the notification threshold for a specific bin from the API.
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

# Fetches the preferred notification methods for the specified bin.
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

# Measures the distance from the ultrasonic sensor to the bin’s top. 
# If is_real is True, it performs actual measurements; 
# if False, it generates a random distance.
def get_distance(bin_height, retries=5, is_real=True):
    if is_real:
        for _ in range(retries):
            try:
                GPIO.output(TRIGGER_PIN, GPIO.LOW) # This ensures that the sensor is ready for a new measurement by resetting any previous signal.
                time.sleep(0.5) # 500 miliseconds
                GPIO.output(TRIGGER_PIN, GPIO.HIGH) # This sends a brief pulse to the ultrasonic sensor, which starts the measurement process
                time.sleep(0.00001) # 10 microseconds
                GPIO.output(TRIGGER_PIN, GPIO.LOW) # After the 10 microsecond pulse, the code sets the Trigger pin back to LOW again, signaling the end of the pulse.

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

# Calculates the fill percentage of the bin based on the measured distance and bin height.
def calculate_fill_level(distance, bin_height):
    fill_level_cm = bin_height - distance
    fill_level_cm = max(0, min(fill_level_cm, bin_height))
    fill_percentage = (fill_level_cm / bin_height) * 100
    return int(fill_percentage)

# Sends the current fill percentage for a specific bin to the server.
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
            print(f"SUCCESSFUL sending data for bin {bin_id}.")
            return True
        else:
            print(f"FAILED to send data for bin {bin_id}. Status code: {response.status_code}")
            print(f"Response Content: {response.text}")
            return False
    except requests.RequestException as e:
        print(f"Error sending data for bin {bin_id}: {e}")
        return False

# Sends a notification to the server based on the provided parameters.
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
            print(f"SUCCESSFUL sending {notification_type} notification for bin {bin_id}.")
            return True
        else:
            print(f"FAILED to send {notification_type} notification for bin {bin_id}. Status code: {response.status_code}")
            print(f"Response Content: {response.text}")
            return False
    except requests.RequestException as e:
        print(f"Error sending {notification_type} notification for bin {bin_id}: {e}")
        return False

# The main() function runs an infinite loop to continuously monitor the bins.
def main():
    # Track displayed notifications
    displayed_notifications = {bin_data['id']: {'email': False, 'website': False} for bin_data in bins}
    
    try:
        while True:
            for bin_data in bins:
                bin_id = bin_data["id"]
                bin_height = bin_data["height"]
                is_real = bin_data["is_real"]

                # Check if the bin exists in the database before processing
                if not bin_exists_in_db(bin_id):
                    print(f"Bin {bin_id} not exist. Skipping...")
                    continue
                
                # Get the distance from the current bin
                distance = get_distance(bin_height, is_real=is_real)

                if distance is None:
                    print(f"Warning: Potential wiring issue detected for bin {bin_id}.")
                    if not notifications_sent[bin_id]['error']:
                        send_notification(bin_id, "sensor or wiring issue", TOKEN, notification_type="error")
                        notifications_sent[bin_id]['error'] = True
                        notification_methods = get_notification_methods_from_db(bin_id, TOKEN)
                        print(f"Notification methods for bin {bin_id}: {notification_methods}")
                    continue

                if notifications_sent[bin_id]['error']:
                    send_notification(bin_id, "sensor is responding again", TOKEN, notification_type="recovered")
                    notifications_sent[bin_id]['error'] = False
                    notifications_sent[bin_id]['recovered'] = True

                fill_percentage = calculate_fill_level(distance, bin_height)
                print(f"Bin {bin_id} fill level: {fill_percentage}%")

                if last_fill_percentage[bin_id] is None or abs(last_fill_percentage[bin_id] - fill_percentage) >= 5:
                    send_data_to_server(bin_id, fill_percentage, TOKEN)
                    last_fill_percentage[bin_id] = fill_percentage

                threshold = get_threshold_from_db(bin_id, TOKEN)

                if fill_percentage >= threshold and not notifications_sent[bin_id].get('alerted', False):
                    print(f"Alert: Bin {bin_id} has reached {fill_percentage}% of its capacity!")
                    send_notification(bin_id, f"{fill_percentage}% full", TOKEN, notification_type="alert")
                    notifications_sent[bin_id]['alerted'] = True
                    notification_methods = get_notification_methods_from_db(bin_id, TOKEN)
                    print(f"Notification methods for bin {bin_id}: {notification_methods}")

                # If fill percentage is above threshold, send notification
                if fill_percentage >= threshold:
                    if 'email' in notification_methods and not displayed_notifications[bin_id]['email']:
                        send_notification(bin_id, f"{fill_percentage}% full", TOKEN, notification_type="alert")
                        print(f"SUCCESSFUL sending email notification for bin {bin_id}.")
                        displayed_notifications[bin_id]['email'] = True  # Mark email notification as displayed
                        
                    if 'website' in notification_methods and not displayed_notifications[bin_id]['website']:
                        print(f"SUCCESSFUL sending website notification for bin {bin_id}.")
                        displayed_notifications[bin_id]['website'] = True  # Mark website notification as displayed

                if fill_percentage < threshold:
                    notifications_sent[bin_id]['alerted'] = False  # Reset the alert notification flag
                    displayed_notifications[bin_id] = {'email': False, 'website': False}  # Reset displayed notifications for bin

            time.sleep(20)  # Adjust the delay as needed
    except KeyboardInterrupt:
        print("Program stopped.")
    finally:
        GPIO.cleanup() # Cleans up the GPIO settings when the program ends (e.g., through a keyboard interrupt).

# This checks if the script is being run directly, and if so, it calls the main() function to start the program.
if __name__ == "__main__":
    main()
