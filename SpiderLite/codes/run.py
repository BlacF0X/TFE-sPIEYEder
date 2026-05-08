import threading
import detecam
import time

PI_MAIN_IP = "192.168.10.1"

def start_cameras():
    threading.Thread(
        target=detecam.run,
        args=(1, PI_MAIN_IP, 5002),
        daemon=True
    ).start()
    time.sleep(0.5)
    threading.Thread(
        target=detecam.run,
        args=(0, PI_MAIN_IP, 5003),
        daemon=True
    ).start()

if __name__ == "__main__":
    start_cameras()

    while True:
        time.sleep(1)
