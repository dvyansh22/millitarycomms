import time
import board
import busio
import numpy as np
import adafruit_mlx90640

print("================================")
print(" MLX90640 TEST")
print("================================")

print("Initializing I2C...")

i2c = busio.I2C(board.SCL, board.SDA)

print("Initializing MLX90640...")

mlx = adafruit_mlx90640.MLX90640(i2c)

mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ

frame = [0] * 768

print("Sensor initialized.")
print("Reading temperature frames...")
print()

while True:

    try:
        mlx.getFrame(frame)

        temp = np.array(frame).reshape(24, 32)

        print(
            "Min: {:.2f} °C | Max: {:.2f} °C | Average: {:.2f} °C".format(
                np.min(temp),
                np.max(temp),
                np.mean(temp)
            )
        )

    except Exception as e:
        print("MLX90640 error:", e)

    time.sleep(1)
