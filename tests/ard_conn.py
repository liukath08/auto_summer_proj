import serial

import time

PORT = "/dev/cu.usbmodemXXXX"   # Replace with your Arduino port

BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=1)

time.sleep(2)   # Give Arduino time to reset

print(ser.readline().decode().strip())

ser.write(b"PING\n")

print(ser.readline().decode().strip())

ser.write(b"ON\n")

print(ser.readline().decode().strip())

time.sleep(2)

ser.write(b"OFF\n")

print(ser.readline().decode().strip())

ser.close()