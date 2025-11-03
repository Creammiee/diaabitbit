import time, threading, numpy as np, tkinter as tk
import RPi.GPIO as GPIO
from max30100 import MAX30100

GPIO.setmode(GPIO.BCM)
START_BTN, STOP_BTN = 16, 20
GPIO.setup(START_BTN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(STOP_BTN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

sensor = MAX30100()
sensor.enable_spo2()
sensor.set_led_current(46.8, 46.8)
time.sleep(1)

running = False

def predict_glucose(ir, red):
    if red <= 0 or ir <= 0:
        return None
    ratio_log = np.log10(ir / red)
    a, b, c = -210.45, 420.12, 9.84
    return round(a * (ratio_log ** 2) + b * ratio_log + c, 2)

def read_sensor():
    global running
    ir_vals, red_vals = [], []
    start_time = time.time()
    
    while running:
        try:
            sensor.read_sensor()
            ir, red = sensor.ir, sensor.red
            
            if ir and red and ir > 0 and red > 0:
                ir_vals.append(ir)
                red_vals.append(red)
            
            # Update every 60 seconds
            if time.time() - start_time >= 60:
                if ir_vals and red_vals:
                    avg_ir, avg_red = np.mean(ir_vals), np.mean(red_vals)
                    glucose = predict_glucose(avg_ir, avg_red)
                    if glucose:
                        root.after(0, lambda g=glucose: label_result.config(
                            text=f"Glucose: {g} mg/dL"
                        ))
                ir_vals.clear()
                red_vals.clear()
                start_time = time.time()
            
            time.sleep(0.05)
        except Exception as e:
            print(f"Error reading sensor: {e}")
            time.sleep(0.1)

def start_measurement(channel=None):
    global running
    if not running:
        running = True
        threading.Thread(target=read_sensor, daemon=True).start()
        label_result.config(text="Measuring...")

def stop_measurement(channel=None):
    global running
    running = False
    label_result.config(text="Stopped. Press START")

GPIO.add_event_detect(START_BTN, GPIO.FALLING, callback=start_measurement, bouncetime=300)
GPIO.add_event_detect(STOP_BTN, GPIO.FALLING, callback=stop_measurement, bouncetime=300)

root = tk.Tk()
root.title("Glucose Monitor")
# Set resolution for 3.5" TFT display (480x320)
root.geometry("480x320")
# Optional: Uncomment for fullscreen
# root.attributes('-fullscreen', True)

label_result = tk.Label(root, text="Press START button", font=("Arial", 24, "bold"))
label_result.pack(expand=True)

try:
    root.mainloop()
finally:
    running = False
    GPIO.cleanup()