import pandas as pd
import joblib
import time
import numpy as np
import tkinter as tk
import RPi.GPIO as GPIO
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from max30100 import MAX30100

# GPIO pin setup - 2 buttons only
START_BTN = 16
STOP_BTN = 20
GPIO.setmode(GPIO.BCM)
GPIO.setup(START_BTN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(STOP_BTN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

sensor = MAX30100()
sensor.enable_spo2()
sensor.set_led_current(50, 50)
time.sleep(1)

sarimax_model = joblib.load("sarimax_model.pkl")
horizons = [5, 15, 30, 60, 480, 720, 1440]
temperature = 36.0

root = tk.Tk()
root.title("Glucose Forecast")
# Set resolution for 3.5" TFT display (480x320)
root.geometry("480x320")
# Optional: Uncomment for fullscreen
# root.attributes('-fullscreen', True)

# Smaller label for current glucose
current_label = tk.Label(root, text="Current: -- mg/dL", font=("Helvetica", 16, "bold"))
current_label.pack(pady=5)

# Smaller figure for the plot
fig = Figure(figsize=(5.5, 2.8), dpi=80)
ax = fig.add_subplot(111)
ax.set_title("Glucose Forecast", fontsize=10)
ax.set_xlabel("Minutes", fontsize=8)
ax.set_ylabel("mg/dL", fontsize=8)
ax.tick_params(labelsize=7)
ax.grid(True, alpha=0.3)
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(pady=2, fill=tk.BOTH, expand=True)

def detect_peaks(signal, threshold=0.5):
    return [i for i in range(1, len(signal)-1) if signal[i-1]<signal[i]>signal[i+1] and signal[i]>threshold]

def get_hr_ibi(duration=60):
    ir_buffer, time_buffer = [], []
    start_time = time.time()
    while time.time() - start_time < duration:
        sensor.read_sensor()
        ir_buffer.append(sensor.ir)
        time_buffer.append(time.time())
        if len(ir_buffer) > 250:
            ir_buffer.pop(0)
            time_buffer.pop(0)
        time.sleep(0.005)
    signal = ir_buffer
    t = time_buffer
    if not signal: return 0, 0
    min_val, max_val = min(signal), max(signal)
    norm_signal = [(s - min_val) / (max_val - min_val + 1e-6) for s in signal]
    peaks = detect_peaks(norm_signal, 0.5)
    if len(peaks) > 1:
        ibi_list = [t[peaks[i]] - t[peaks[i-1]] for i in range(1, len(peaks))]
        avg_ibi = sum(ibi_list) / len(ibi_list)
        hr = 60 / avg_ibi
        return hr, avg_ibi
    return 0, 0

def predict_glucose(ir, red):
    if red <= 0 or ir <= 0:
        return None
    ratio_log = np.log10(ir / red)
    a, b, c = -210.45, 427.70, 21.80
    glucose = a * (ratio_log ** 2) + b * ratio_log + c
    return round(glucose, 2)

running = False
update_job = None
last_predicted_glucose = 123.0

def update_forecast():
    global update_job, last_predicted_glucose
    if not running:
        return
    sensor.read_sensor()
    ir, red = sensor.ir, sensor.red
    predicted_glucose = predict_glucose(ir, red)
    if predicted_glucose is None:
        predicted_glucose = last_predicted_glucose
    last_predicted_glucose = predicted_glucose
    hr, ibi = get_hr_ibi(duration=60)
    exog = pd.DataFrame({
        "HeartRate": [hr] * len(horizons),
        "IBI": [ibi] * len(horizons),
        "Temperature": [temperature] * len(horizons)
    })
    forecast = sarimax_model.get_forecast(steps=len(horizons), exog=exog)
    forecasted_glucose = forecast.predicted_mean + predicted_glucose - forecast.predicted_mean.iloc[0]
    current_label.config(text=f"Current: {predicted_glucose:.1f} mg/dL")
    ax.clear()
    ax.plot(horizons, forecasted_glucose, marker='o', markersize=4, linestyle='-', color='blue', linewidth=1.5)
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

# Only 2 buttons - START and STOP
GPIO.add_event_detect(START_BTN, GPIO.FALLING, callback=start, bouncetime=300)
GPIO.add_event_detect(STOP_BTN, GPIO.FALLING, callback=stop, bouncetime=300)

try:
    root.mainloop()
finally:
    GPIO.cleanup()