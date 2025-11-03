import pandas as pd
import joblib
import time
import numpy as np
import random
import tkinter as tk
import RPi.GPIO as GPIO
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from max30100 import MAX30100

# GPIO setup - 2 buttons
START_BTN = 16
STOP_BTN = 20
GPIO.setmode(GPIO.BCM)
GPIO.setup(START_BTN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(STOP_BTN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Initialize MAX30100 (finger detection only)
sensor = MAX30100()
sensor.enable_spo2()
sensor.set_led_current(50.0, 50.0)
time.sleep(1)

# Load SARIMAX model
sarimax_model = joblib.load("sarimax_model.pkl")
horizons = [5, 15, 30, 60, 180, 360, 720, 1440]
temperature = 36.0

# GUI setup
root = tk.Tk()
root.title("Glucose Forecast (Demo)")
root.geometry("480x320")

current_label = tk.Label(root, text="Current: -- mg/dL", font=("Helvetica", 16, "bold"))
current_label.pack(pady=5)

fig = Figure(figsize=(5.5, 2.8), dpi=80)
ax = fig.add_subplot(111)
ax.set_title("Glucose Forecast", fontsize=10)
ax.set_xlabel("Minutes", fontsize=8)
ax.set_ylabel("mg/dL", fontsize=8)
ax.tick_params(labelsize=7)
ax.grid(True, alpha=0.3)
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(pady=2, fill=tk.BOTH, expand=True)

running = False
update_job = None
last_glucose = random.randint(89, 105)

def detect_finger(ir_val, red_val, threshold=500):
    """Detect if finger is present using IR/RED intensity."""
    return ir_val > threshold and red_val > threshold

def generate_next(prev_value):
    """Generate smooth random glucose values (89–105)."""
    change = random.randint(-2, 2)
    new_val = prev_value + change
    return max(89, min(105, new_val))

def update_forecast():
    global update_job, last_glucose
    if not running:
        return

    # Read MAX30100 just to check for finger presence
    sensor.read_sensor()
    ir, red = sensor.ir, sensor.red
    finger_present = detect_finger(ir, red)

    # If finger is detected, continue generating random values (demo mode)
    if finger_present:
        current_value = generate_next(last_glucose)
    else:
        # No finger detected — pause updates or keep last value steady
        current_value = last_glucose

    last_glucose = current_value

    # Dummy HR and IBI values for SARIMAX exog
    hr, ibi = 80, 0.8

    # Forecast using SARIMAX model
    exog = pd.DataFrame({
        "HeartRate": [hr] * len(horizons),
        "IBI": [ibi] * len(horizons),
        "Temperature": [temperature] * len(horizons)
    })
    forecast = sarimax_model.get_forecast(steps=len(horizons), exog=exog)
    forecasted_glucose = forecast.predicted_mean + current_value - forecast.predicted_mean.iloc[0]
    forecasted_glucose = [int(x) for x in forecasted_glucose]

    # Update UI
    current_label.config(text=f"Current: {int(current_value)} mg/dL")

    ax.clear()
    ax.plot(horizons, forecasted_glucose, marker='o', markersize=4,
            linestyle='-', color='blue', linewidth=1.5)
    ax.set_title("Glucose Forecast", fontsize=10)
    ax.set_xlabel("Minutes", fontsize=8)
    ax.set_ylabel("mg/dL", fontsize=8)
    ax.set_xticks(horizons)
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    canvas.draw()

    update_job = root.after(10000, update_forecast)

def start(channel=None):
    global running
    if not running:
        running = True
        update_forecast()

def stop(channel=None):
    global running, update_job
    running = False
    if update_job is not None:
        root.after_cancel(update_job)
        update_job = None

# Buttons
GPIO.add_event_detect(START_BTN, GPIO.FALLING, callback=start, bouncetime=300)
GPIO.add_event_detect(STOP_BTN, GPIO.FALLING, callback=stop, bouncetime=300)

try:
    root.mainloop()
finally:
    GPIO.cleanup()
