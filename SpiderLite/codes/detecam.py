import cv2
import numpy as np
import time
import socket
import struct
from picamera2 import Picamera2
from queue import Queue
import pickle


import threading
from queue import Queue

def run(cam_id, host, port):
    FOV = 104

    picam2 = Picamera2(camera_num=cam_id)
    config = picam2.create_video_configuration(
        main={"size": (320, 240), "format": "YUV420"},
        buffer_count=2
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.connect((host, port))
    sock.settimeout(0.2)

    print(f"[CAM {cam_id}] started")

    capture_q = Queue(maxsize=1)
    process_q = Queue(maxsize=1)

    # -------- CAPTURE --------
    def capture_loop():
        while True:
            frame = picam2.capture_array("main")
            if frame is None:
                continue

            if capture_q.full():
                capture_q.get_nowait()

            capture_q.put(frame)

    # -------- PROCESS --------
    def process_loop():
        background = None
        baseline = 5

        while True:
            frame = capture_q.get()

            h = frame.shape[0] * 2 // 3
            gray = frame[:h, :320].copy()

            gray_t = cv2.GaussianBlur(gray, (3, 3), 0)
            gray_t = cv2.convertScaleAbs(gray_t, alpha=0.75)

            if background is None:
                background = gray_t.astype("float")
                continue

            cv2.accumulateWeighted(gray_t, background, 0.02)

            diff = cv2.absdiff(gray_t, cv2.convertScaleAbs(background))
            diff[diff < 10] = 0

            motion_intensity = np.mean(diff)

            baseline = 0.95 * baseline + 0.05 * motion_intensity
            threshold = max(baseline * 1.05, 5)

            x_percent = None

            if motion_intensity > threshold:
                moments = cv2.moments((diff > threshold).astype(np.uint8) * 255)
                if moments["m00"] != 0:
                    cx = int(moments["m10"] / moments["m00"])
                    width = gray.shape[1]
                    x_percent = (cx / width) * FOV

            _, buffer = cv2.imencode('.jpg', gray_t, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
            frame_bytes = buffer.tobytes()

            if process_q.full():
                process_q.get_nowait()

            process_q.put((frame_bytes, x_percent))

    # -------- SEND --------
    def send_loop():
        while True:
            frame_bytes, x_percent = process_q.get()

            try:
                header = struct.pack(
                    "fI",
                    x_percent if x_percent is not None else 0,
                    len(frame_bytes)
                )
                sock.sendall(header + frame_bytes)
            except Exception as e:
                print(f"[CAM {cam_id}] send error:", e)

    # -------- START THREADS --------
    threading.Thread(target=capture_loop, daemon=True).start()
    threading.Thread(target=process_loop, daemon=True).start()
    threading.Thread(target=send_loop, daemon=True).start()

    while True:
        time.sleep(1)
