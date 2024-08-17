import time
import RPi.GPIO as GPIO
import requests

# Set up GPIO mode
GPIO.setmode(GPIO.BCM)

# Define GPIO pins for the HC-SR04
TRIGGER_PIN = 23
ECHO_PIN = 24

# Set up the trigger and echo pins
GPIO.setup(TRIGGER_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)

# Bin dimensions
BIN_HEIGHT_CM = 26.0  # Replace with the actual height of your bin in cm

def get_distance():
    # Send a pulse to the trigger pin
    GPIO.output(TRIGGER_PIN, GPIO.LOW)
    time.sleep(0.5)
    GPIO.output(TRIGGER_PIN, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(TRIGGER_PIN, GPIO.LOW)

    # Wait for the echo pin to go high
    while GPIO.input(ECHO_PIN) == GPIO.LOW:
        pulse_start = time.time()

    while GPIO.input(ECHO_PIN) == GPIO.HIGH:
        pulse_end = time.time()

    # Calculate pulse duration
    pulse_duration = pulse_end - pulse_start

    # Calculate distance in centimeters
    distance = pulse_duration * 17150
    distance = round(distance, 2)

    return distance

def calculate_fill_level(distance):
    # Calculate the filled portion of the bin
    fill_level_cm = BIN_HEIGHT_CM - distance

    # Ensure fill level is within 0 to BIN_HEIGHT_CM
    fill_level_cm = max(0, min(fill_level_cm, BIN_HEIGHT_CM))

    # Calculate fill percentage
    fill_percentage = (fill_level_cm / BIN_HEIGHT_CM) * 100
    return int(fill_percentage)

def send_data_to_server(fill_percentage):
    url = "http://192.168.100.196:8000/api/bin-level"  # Replace with your Laravel API endpoint
    headers = {"Content-Type": "application/json"}
    data = {"fill_percentage": fill_percentage}

    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print("Data sent successfully.")
        else:
            print(f"Failed to send data. Status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"Error sending data: {e}")

try:
    while True:
        distance = get_distance()
        fill_percentage = calculate_fill_level(distance)
        print(f"Bin fill level: {fill_percentage}%")
        send_data_to_server(fill_percentage)
        time.sleep(15)  
except KeyboardInterrupt:
    print("Program stopped.")
finally:
    GPIO.cleanup()
