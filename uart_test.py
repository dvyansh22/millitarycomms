import serial
import time

ser = serial.Serial(
    '/dev/serial0',
    9600,
    timeout=2
)

print("UART test started")
print("Waiting for ESP data...")

while True:

    data = ser.readline().decode(
        errors="ignore"
    ).strip()

    if data:
        print("ESP:", data)

    time.sleep(0.1)
