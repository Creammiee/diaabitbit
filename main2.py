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

# --- GPIO setup ---
START_BTN = 16
STOP_BTN = 20
GPIO.setmode(GPIO.BCM)
GPIO.setup(START_BTN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(STOP_BTN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# --- MAX30100 setup ---
sensor = MAX30100()
sensor.enable_spo2()
sensor.set_led_current(50.0, 50.0)
time.sleep(1)

# --- Load SARIMAX model ---
sarimax_model = joblib.load("sarimax_model.pkl")
horizons = [5, 15, 30, 60, 180, 360, 720, 1440]
temperature = 36.0

# --- GUI setup ---
root = tk.Tk()
root.title("Glucose Forecast")
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
forecast_job = None
last_glucose = random.randint(89, 105)

# --- Utility functions ---
def detect_finger(ir_val, red_val, threshold=500):
    """Detect if finger is present using IR/RED intensity."""
    return ir_val > threshold and red_val > threshold

def generate_next(prev_value):
    """Generate smooth random glucose values (89–105)."""
    change = random.randint(-2, 2)
    new_val = prev_value + change
    return max(89, min(105, new_val))

# --- Forecast and display ---
def generate_forecast(current_value):
    """Generate a new forecast every 5 minutes."""
    hr, ibi = 80, 0.8
    exog = pd.DataFrame({
        "HeartRate": [hr] * len(horizons),
        "IBI": [ibi] * len(horizons),
        "Temperature": [temperature] * len(horizons)
    })
    forecast = sarimax_model.get_forecast(steps=len(horizons), exog=exog)
    forecasted_glucose = forecast.predicted_mean + current_value - forecast.predicted_mean.iloc[0]
    forecasted_glucose = [int(x) for x in forecasted_glucose]

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

# --- Main update loop ---
def update_values():
    global update_job, forecast_job, last_glucose

    if not running:
        return

    sensor.read_sensor()
    ir, red = sensor.ir, sensor.red
    finger_present = detect_finger(ir, red)

    if not finger_present:
        current_label.config(text="Place finger on sensor")
        ax.clear()
        ax.text(0.5, 0.5, "Waiting for finger...", ha='center', va='center', fontsize=12)
        ax.axis('off')
        canvas.draw()
        update_job = root.after(1000, update_values)
        return

    # Finger detected - update glucose reading
    current_value = generate_next(last_glucose)
    last_glucose = current_value
    current_label.config(text=f"Current: {int(current_value)} mg/dL")

    # Schedule forecast every 5 minutes (300,000 ms)
    if forecast_job is None:
        generate_forecast(current_value)
        forecast_job = root.after(300000, lambda: forecast_timer())

    update_job = root.after(5000, update_values)  # Update glucose every 5 sec

def forecast_timer():
    """Trigger forecast every 5 minutes if still running."""
    global forecast_job
    if running:
        generate_forecast(last_glucose)
        forecast_job = root.after(300000, forecast_timer)

# --- Button control functions ---
def start(channel=None):
    global running, forecast_job
    if not running:
        running = True
        forecast_job = None
        update_values()

def stop(channel=None):
    global running, update_job, forecast_job
    running = False
    if update_job is not None:
        root.after_cancel(update_job)
        update_job = None
    if forecast_job is not None:
        root.after_cancel(forecast_job)
        forecast_job = None
    current_label.config(text="Stopped")
    ax.clear()
    ax.text(0.5, 0.5, "Stopped", ha='center', va='center', fontsize=12)
    ax.axis('off')
    canvas.draw()

# --- Button events ---
GPIO.add_event_detect(START_BTN, GPIO.FALLING, callback=start, bouncetime=300)
GPIO.add_event_detect(STOP_BTN, GPIO.FALLING, callback=stop, bouncetime=300)

# --- Run program ---
try:
    root.mainloop()
finally:
    GPIO.cleanup()
