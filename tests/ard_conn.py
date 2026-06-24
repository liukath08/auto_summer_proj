import serial
import time

# CHANGE THIS to Arduino port:
PORT = "COMX"

baud_rate = 9600

# Open serial connection
arduino = serial.Serial(PORT, baud_rate, timeout=1)

# Wait for Arduino to reset
time.sleep(2)

print("Connected to Arduino")

# Send test messages
for i in range(5):
    message = f"Hello Arduino {i}\n"
    arduino.write(message.encode())   # send bytes
    print("Sent:", message.strip())

    # Read response
    response = arduino.readline().decode().strip()
    print("Received:", response)

    time.sleep(1)

arduino.close()

import serial
import time

# CHANGE THIS to your Arduino port:
# Windows: "COM3", "COM4", etc.
# Mac/Linux: "/dev/tty.usbmodemXXXX" or "/dev/ttyACM0"
PORT = "COM3"

baud_rate = 9600

# Open serial connection
arduino = serial.Serial(PORT, baud_rate, timeout=1)

# Wait for Arduino to reset
time.sleep(2)

print("Connected to Arduino")

# Send test messages
for i in range(5):
    message = f"Hello Arduino {i}\n"
arduino.write(message.encode()) # send bytes
print("Sent:", message.strip())

# Read response
response = arduino.readline().decode().strip()
print("Received:", response)

time.sleep(1)

arduino.close()