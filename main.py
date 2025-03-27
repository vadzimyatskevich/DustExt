#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox
import requests
import json
import threading
import time
from datetime import datetime
import os

# Configuration files
CONFIG_FILE = "config.json"
LANG_FILE = "lang.json"
LOG_DIR = "logs"

# Default configurations
DEFAULT_CONFIG = {
    "device_ip": "192.168.1.100",
    "output": 1,
    "poll_interval": 5,
    "username": "admin",
    "password": "joker",
    "logging": False,  # Включение/выключение логирования
    "language": "en"
}

DEFAULT_LANG = {
    "en": {
        "window_title": "Tasmota Controller",
        "status": "Status:",
        "output_state": "Output State:",
        "device": "Device:",
        "output": "Output:",
        "on": "ON",
        "off": "OFF",
        "unknown": "UNKNOWN",
        "turn_on": "TURN ON",
        "turn_off": "TURN OFF",
        "toggle": "TOGGLE",
        "online": "ONLINE",
        "offline": "OFFLINE",
        "config_error": "Configuration Error",
        "connection_error": "Connection Error",
        "command_failed": "Command Failed",
        "logging": "Logging:",
        "enabled": "ENABLED",
        "disabled": "DISABLED"
    }
}

# Global variables
config = DEFAULT_CONFIG.copy()
lang = DEFAULT_LANG["en"].copy()
is_connected = False
output_state = None
stop_polling = False
last_update = None
log_file = None
log_enabled = False

def setup_logging():
    global log_file, log_enabled
    log_enabled = config.get("logging", False)
    
    if log_enabled:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        log_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{LOG_DIR}/log_{log_time}.txt"
        log_file = open(log_filename, "a", encoding="utf-8")
        log_message(f"Logging started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def log_message(message):
    if log_enabled and log_file:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"[{timestamp}] {message}\n")
        log_file.flush()

def close_logging():
    if log_enabled and log_file:
        log_message(f"Logging stopped at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_file.close()

def load_config():
    global config
    try:
        with open(CONFIG_FILE, "r") as f:
            config.update(json.load(f))
            if config["poll_interval"] < 1:
                config["poll_interval"] = 5
                log_message("Adjusted poll interval to 5 seconds (was too small)")
    except Exception as e:
        message = f"Using default config. Error: {str(e)}"
        messagebox.showerror(lang["config_error"], message)
        log_message(message)
        save_config()

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    log_message("Configuration saved")

def load_language():
    global lang
    try:
        with open(LANG_FILE, "r", encoding='utf-8') as f:
            all_langs = json.load(f)
            lang = all_langs.get(config.get("language", "en"), DEFAULT_LANG["en"])
    except Exception as e:
        lang = DEFAULT_LANG["en"]
        log_message(f"Language file error, using English. Error: {str(e)}")

def build_command_url(command):
    base = f"http://{config['device_ip']}/cm"
    params = f"cmnd=Power{config['output']}%20{command}"
    if config["username"] and config["password"]:
        auth = f"user={config['username']}&password={config['password']}"
        return f"{base}?{auth}&{params}"
    return f"{base}?{params}"

def check_connection():
    global is_connected, output_state, last_update
    try:
        url = build_command_url("State")
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            is_connected = True
            new_state = data.get(f"POWER{config['output']}", "").upper()
            
            if new_state != output_state:
                log_message(f"Output state changed from {output_state} to {new_state}")
            
            output_state = new_state
            last_update = datetime.now().strftime("%H:%M:%S")
            return True
    except Exception as e:
        log_message(f"Connection check failed: {str(e)}")
    
    if is_connected:  # Если было подключение, но теперь нет
        log_message("Connection lost")
    is_connected = False
    output_state = None
    return False

def polling_worker():
    while not stop_polling:
        check_connection()
        update_display()
        time.sleep(config["poll_interval"])

def update_display():
    # Update connection status
    status_text = lang["online"] if is_connected else lang["offline"]
    status_color = "green" if is_connected else "red"
    status_label.config(text=f"{lang['status']} {status_text}", fg=status_color)
    
    # Update output state
    if output_state in ["ON", "OFF"]:
        state_text = lang["on"] if output_state == "ON" else lang["off"]
        state_color = "green" if output_state == "ON" else "red"
    else:
        state_text = lang["unknown"]
        state_color = "gray"
    
    state_label.config(text=f" {state_text}", fg=state_color)
    
    # Update last refresh time
    if last_update:
        time_label.config(text=f"{lang['last_update']} {last_update}")
    
    # Update logging status
    logging_status = lang["enabled"] if log_enabled else lang["disabled"]
    logging_label.config(text=f"{lang['logging']} {logging_status}")

def send_command(command):
    try:
        url = build_command_url(command)
        log_message(f"Sending command: {command}")
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            log_message(f"Command {command} successful")
            check_connection()  # Immediate status update
            
            return True
        else:
            log_message(f"Command {command} failed with status {response.status_code}")
    except Exception as e:
        log_message(f"Command {command} error: {str(e)}")
        if is_connected:
            messagebox.showerror(lang["command_failed"], f"{lang['command_failed']}: {str(e)}")
    return False

def turn_on():
    threading.Thread(target=lambda: send_command("On")).start()

def turn_off():
    threading.Thread(target=lambda: send_command("Off")).start()

def toggle():
    threading.Thread(target=lambda: send_command("Toggle")).start()

def on_closing():
    global stop_polling
    stop_polling = True
    close_logging()
    root.destroy()

# Initialize
load_config()
setup_logging()
load_language()

# Create GUI
root = tk.Tk()
root.title(lang["window_title"])
root.geometry("640x120")
root.protocol("WM_DELETE_WINDOW", on_closing)

# Configure root grid to expand
root.grid_rowconfigure([0], weight=1)  # Make row 0 expandable
root.grid_columnconfigure([0], weight=1)  # Make column 0 expandable

control_frame = tk.Frame(root)
# Configure control_frame grid to expand
control_frame.grid_rowconfigure([0], weight=1)
control_frame.grid_columnconfigure([0,1,2], weight=1)

control_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")  # Make frame stick to all sides

state_label = tk.Label(control_frame, text=f"{lang['output_state']}", font=("Arial", 30))
state_label.grid(row=0,  column=1, padx=5, sticky="nsew")

on_button = tk.Button(
    control_frame, 
    activebackground="green",
    text=lang["turn_on"], 
    command=turn_on,
    width=12,
    height=3
)
on_button.grid(row=0, column=0, padx=5, sticky="nsew")

off_button = tk.Button(
    control_frame,
    activebackground="red",
    text=lang["turn_off"],
    command=turn_off,
    width=12,
    height=3
)
off_button.grid(row=0, column=2, padx=5, sticky="nsew")

# toggle_button = tk.Button(
#     control_frame,
#     foreground="brown",
#     text=lang["toggle"],
#     command=toggle,
#     width=12,
#     height=2
# )
# toggle_button.grid(row=0, column=1, padx=5, sticky="nsew")

info_frame = tk.Frame(root)
info_frame.grid(row=1, column=0, sticky="nsew", pady=0, padx=5)

# Configure control_frame grid to expand
info_frame.grid_rowconfigure([0], weight=1)
info_frame.grid_columnconfigure([0,1,2], weight=1)
time_label = tk.Label(info_frame, text="Last update: --:--:--", font=("Arial", 8), fg="gray")
time_label.grid(row=0, column=0, padx=10, sticky=tk.W)
logging_label = tk.Label(info_frame, text=f"{lang['logging']} ...", font=("Arial", 8), fg="gray")
logging_label.grid(row=0, column=1, padx=10, sticky=tk.W)
tk.Label(info_frame, text=f"{lang['device']} {config['device_ip']}", font=("Arial", 8), fg="gray").grid(row=0, column=2, sticky="w")
tk.Label(info_frame, text=f"{lang['output']} {config['output']}", font=("Arial", 8), fg="gray").grid(row=0, column=3, sticky="w")
status_label = tk.Label(info_frame, text=f"{lang['status']} ...", font=("Arial", 8))
status_label.grid(row=0, column=4, padx=5, sticky="w")


# Start polling thread
polling_thread = threading.Thread(target=polling_worker, daemon=True)
polling_thread.start()

# Initial update
update_display()

root.mainloop()