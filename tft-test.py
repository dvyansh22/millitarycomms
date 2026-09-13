import spidev
import RPi.GPIO as GPIO
import time

# =====================================================
# GPIO
# =====================================================

DC = 24
RST = 25

GPIO.setmode(GPIO.BCM)

GPIO.setup(DC, GPIO.OUT)
GPIO.setup(RST, GPIO.OUT)

# =====================================================
# SPI LCD
# CE0 = GPIO8 = physical pin 24
# =====================================================

spi = spidev.SpiDev()
spi.open(0, 0)

spi.max_speed_hz = 12000000
spi.mode = 0

# =====================================================
# Command
# =====================================================

def command(cmd):
    GPIO.output(DC, GPIO.LOW)
    spi.xfer2([cmd])


# =====================================================
# Data
# =====================================================

def data(values):

    GPIO.output(DC, GPIO.HIGH)

    if isinstance(values, int):
        values = [values]

    spi.xfer2(values)


# =====================================================
# Reset
# =====================================================

def reset():

    GPIO.output(RST, GPIO.HIGH)
    time.sleep(0.1)

    GPIO.output(RST, GPIO.LOW)
    time.sleep(0.1)

    GPIO.output(RST, GPIO.HIGH)
    time.sleep(0.15)


# =====================================================
# Set drawing window
# =====================================================

def set_window(x0, y0, x1, y1):

    command(0x2A)

    data([
        (x0 >> 8) & 0xFF,
        x0 & 0xFF,
        (x1 >> 8) & 0xFF,
        x1 & 0xFF
    ])

    command(0x2B)

    data([
        (y0 >> 8) & 0xFF,
        y0 & 0xFF,
        (y1 >> 8) & 0xFF,
        y1 & 0xFF
    ])

    command(0x2C)


# =====================================================
# Fill screen
# =====================================================

def fill_screen(r, g, b):

    set_window(0, 0, 479, 319)

    # ILI9486 uses RGB666
    pixel = [
        r >> 2,
        g >> 2,
        b >> 2
    ]

    total_pixels = 480 * 320
    chunk_pixels = 256

    GPIO.output(DC, GPIO.HIGH)

    for start in range(0, total_pixels, chunk_pixels):

        count = min(
            chunk_pixels,
            total_pixels - start
        )

        spi.xfer2(pixel * count)


# =====================================================
# Initialize
# =====================================================

print("Initializing TFT...")

reset()

# Software reset
command(0x01)
time.sleep(0.15)

# Sleep out
command(0x11)
time.sleep(0.12)

# 18-bit color
command(0x3A)
data(0x66)

# Memory access control
command(0x36)
data(0x48)

# Display ON
command(0x29)
time.sleep(0.1)

print("TFT initialized.")

# =====================================================
# Color test
# =====================================================

print("RED")
fill_screen(255, 0, 0)
time.sleep(2)

print("GREEN")
fill_screen(0, 255, 0)
time.sleep(2)

print("BLUE")
fill_screen(0, 0, 255)
time.sleep(2)

print("WHITE")
fill_screen(255, 255, 255)
time.sleep(2)

print("BLACK")
fill_screen(0, 0, 0)
time.sleep(2)

print("Test complete.")

spi.close()
GPIO.cleanup()
