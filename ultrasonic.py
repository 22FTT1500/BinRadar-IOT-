import time
import RPi.GPIO as GPIO
import requests

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

# Laravel API credentials and URL
API_URL = "http://192.168.100.196:8000/api"
BIN_ENDPOINT = f"{API_URL}/bins/3"  # Update with your actual bin ID
TOKEN = "uN3yfpL9wN37PZEJOl7ThnHAS8Hup5SFqL36CYP3e4ea2bec"  # Replace with your actual token

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

def send_notification():
    # Replace this with the code to send an actual notification (email, SMS, etc.)
    print("Alert: The bin has reached 50% of its capacity!")

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
                send_notification()
                notification_sent = True  # Ensure notification is sent only once
            
            # Reset notification if the bin is emptied below 50%
            if fill_percentage < 50:
                notification_sent = False  # Reset the notification flag

            time.sleep(15)  # Adjust the delay as needed
    except KeyboardInterrupt:
        print("Program stopped.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
