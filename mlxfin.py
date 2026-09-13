import board
import busio
import numpy as np
import adafruit_mlx90640
import time
import cv2
import serial

print("Initializing I2C...")
i2c = busio.I2C(board.SCL, board.SDA)

print("Initializing sensor...")
mlx = adafruit_mlx90640.MLX90640(i2c)
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ

# 🔌 UART setup
ser = serial.Serial('/dev/serial0', 9600, timeout=1)

frame = [0] * 768

print("Starting detection...")

K = 30000  # 🔥 your calibrated constant
last_sent_time = 0

while True:
    try:
        mlx.getFrame(frame)
    except:
        time.sleep(0.1)
        continue

    # Convert to 2D
    temp = np.array(frame).reshape(24, 32)

    # Resize for processing
    temp = cv2.resize(temp, (320, 240), interpolation=cv2.INTER_CUBIC)

    # Smooth noise
    temp = cv2.GaussianBlur(temp, (5, 5), 0)

    # Normalize
    min_temp = np.percentile(temp, 10)
    max_temp = np.percentile(temp, 90)

    temp_clipped = np.clip(temp, min_temp, max_temp)

    temp_norm = (temp_clipped - min_temp) / (max_temp - min_temp + 1e-6)
    temp_norm = (temp_norm * 255).astype(np.uint8)

    # Threshold for humans
    _, mask = cv2.threshold(temp_norm, 150, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    distances = []

    for c in contours:
        if cv2.contourArea(c) < 2000:
            continue

        x, y, w, h = cv2.boundingRect(c)

        # Distance calculation
        distance = K / (h + 1e-6)

        if 5 < distance < 500:
            distances.append(int(distance))

    distances.sort()
    count = len(distances)

    # Format output
    if count > 0:
        output = "EN," + str(count) + "," + ",".join(map(str, distances))
    else:
        output = "EN,0"

    # Send every 2 seconds
    current_time = time.time()
    if current_time - last_sent_time >= 2:
        ser.write((output + "\n").encode())
        print(output)  # debug
        last_sent_time = current_time
