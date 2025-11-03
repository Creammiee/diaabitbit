import time
from max30100 import MAX30100

print("Initializing MAX30100 sensor...")
sensor = MAX30100()

# Optional: enable SpO2 mode (recommended)
sensor.enable_spo2()

print("Sensor initialized successfully.")
print("Reading IR and Red values... (Press Ctrl+C to stop)")

try:
    while True:
        sensor.read_sensor()
        ir = sensor.ir
        red = sensor.red
        print(f"IR: {ir}, RED: {red}")
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nTest stopped by user.")
