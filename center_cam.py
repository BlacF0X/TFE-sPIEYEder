import cv2
import time
from collections import deque

history = deque(maxlen=10)

def global_box(boxes):
    xs, ys = [], []

    for (x,y,w,h) in boxes:
        xs.extend([x, x+w])
        ys.extend([y, y+h])

    return min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)

def center_cam_loop(queue):
    cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    ret, prev = cap.read()
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    prev_gray = cv2.GaussianBlur(prev_gray, (5,5), 0)
    tracked_boxes = []  # boxes persistantes
    last_box = None
    last_time = 0
    WAIT_DURATION = 5.0
    wait_box = None
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        copy = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5,5), 0)

        if 'bg' not in locals():
            bg = gray.copy().astype("float")

        if wait_box is not None:
            x, y, w, h = wait_box
            margin = 40

            x1 = max(0, x - margin)
            y1 = max(0, y - margin)
            x2 = min(gray.shape[1], x + w + margin)
            y2 = min(gray.shape[0], y + h + margin)

            roi_gray = gray[y1:y2, x1:x2]
            roi_bg = bg[y1:y2, x1:x2]
        else:
            roi_gray = gray
            roi_bg = bg

        cv2.accumulateWeighted(gray, bg, 0.05)
        diff = cv2.absdiff(roi_gray, cv2.convertScaleAbs(roi_bg))
        _, thresh = cv2.threshold(diff, 35, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        motion_score = cv2.countNonZero(thresh)
        if motion_score < 750:
            thresh[:] = 0
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        max_contour = None
        max_area = 0

        for c in contours:
            area = cv2.contourArea(c)
            if area > 1500 and area > max_area:
                max_area = area
                max_contour = c

        box = None

        if max_contour is not None:
            x, y, w, h = cv2.boundingRect(max_contour)
            if wait_box is not None:
                x += x1
                y += y1
            box = (x, y, w, h)
        frame = cv2.GaussianBlur(frame, (15, 15), 0)


        current_time = time.time()
        if box is not None:
            wait_box = None
            history.append(box)
            if last_box is not None:
                alpha = 0.7
                x = int(alpha * last_box[0] + (1 - alpha) * box[0])
                y = int(alpha * last_box[1] + (1 - alpha) * box[1])
                w = int(alpha * last_box[2] + (1 - alpha) * box[2])
                h = int(alpha * last_box[3] + (1 - alpha) * box[3])
                box = (x, y, w, h)

            last_box = box
            last_time = current_time

        elif last_box is not None:
            if current_time - last_time < WAIT_DURATION:
                if wait_box is None:
                    if len(history) >= 3:
                        wait_box = global_box(history)
                    else:
                        wait_box = last_box

                box = wait_box

            else:
                last_box = None
                history.clear()
                wait_box = None

        # 🔥 AFFICHAGE
        if box is not None:
            padding = 30

            x, y, w, h = box
            x = max(0, x - padding)
            y = max(0, y - padding)
            w += 2 * padding
            h += 2 * padding
            if max_contour is not None:
                color = (0, 255, 0)  # mouvement
            else:
                color = (0, 165, 255)  # WAIT

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)



        prev_gray = gray
        _, buffer = cv2.imencode('.jpg', frame, [
            int(cv2.IMWRITE_JPEG_QUALITY), 70
        ])

        data = {
            "frame": buffer.tobytes()
        }

        if not queue.full():
            queue.put(data)
        time.sleep(0.01)