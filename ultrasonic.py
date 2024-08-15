import RPi.GPIO as GPIO
import time
import requests

# GPIO Mode (BOARD / BCM)
GPIO.setmode(GPIO.BCM)

# Set GPIO Pins
GPIO_TRIGGER = 23
GPIO_ECHO = 24

# Set GPIO direction (IN / OUT)
GPIO.setup(GPIO_TRIGGER, GPIO.OUT)
GPIO.setup(GPIO_ECHO, GPIO.IN)

# Set the total height of the bin in cm
bin_height = 50.0  # adjust this to the actual height of your bin

def distance():
    # Set Trigger to HIGH
    GPIO.output(GPIO_TRIGGER, True)

    # Set Trigger after 0.01ms to LOW
    time.sleep(0.00001)
    GPIO.output(GPIO_TRIGGER, False)

    StartTime = time.time()
    StopTime = time.time()

    # Save StartTime
    while GPIO.input(GPIO_ECHO) == 0:
        StartTime = time.time()

    # Save time of arrival
    while GPIO.input(GPIO_ECHO) == 1:
        StopTime = time.time()

    # Time difference between start and arrival
    TimeElapsed = StopTime - StartTime
    # Multiply with the sonic speed (34300 cm/s)
    # and divide by 2, because there and back
    distance = (TimeElapsed * 34300) / 2

    return distance

def bin_level_percentage():
    dist = distance()
    # Calculate the distance from the top of the bin to the trash level
    trash_level = bin_height - dist
    # Calculate the percentage
    percentage = (trash_level / bin_height) * 100
    return max(0, min(100, percentage))  # Ensure the percentage is between 0 and 100

def send_data(level):
    url = 'http://192.168.77.190:8000/api/receive-data'
    headers = {'Content-Type': 'application/json'}
    data = {'sensor_data': level}
    
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print('Data sent successfully!')
        else:
            print('Failed to send data:', response.status_code)
    except requests.RequestException as e:
        print('Error sending data:', e)

if __name__ == '__main__':
    try:
        while True:
            level = bin_level_percentage()
            print(f"Bin Level: {level:.1f}%")
            send_data(level)
            time.sleep(60)  # Send data every 60 seconds

    except KeyboardInterrupt:
        print("Measurement stopped by User")
        GPIO.cleanup()


