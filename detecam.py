import cv2
import numpy as np
import time

def run(c,queue):
    FOV = 120

    cap = cv2.VideoCapture(c, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    background = None
    baseline = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # flou + luminosité
        gray_t = cv2.GaussianBlur(gray, (31, 31), 0)
        gray_t = cv2.convertScaleAbs(gray_t, alpha=0.5)



        # init background
        if background is None:
            background = gray_t.astype("float")
            baseline = 5
            continue

        # update background
        cv2.accumulateWeighted(gray_t, background, 0.02)

        # diff
        diff = cv2.absdiff(gray_t, cv2.convertScaleAbs(background))
        diff[diff < 20] = 0

        # intensité globale (bio-inspired)
        motion_intensity = np.mean(diff)

        # update baseline
        baseline = 0.9 * baseline + 0.1 * motion_intensity
        # seuil dynamique
        threshold = baseline * 1.2

        # masque
        motion_mask = (diff > threshold).astype(np.uint8) * 255

        # morpho
        kernel = np.ones((5, 5), np.uint8)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, kernel)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_CLOSE, kernel)
        x_percent = None
        # détection finale
        if motion_intensity > threshold:
            moments = cv2.moments(motion_mask)

            if moments["m00"] != 0:
                cx = int(moments["m10"] / moments["m00"])

            else:
                cx = None

            if cx is not None:
                width = motion_mask.shape[1]
                x_percent = (cx/width)*FOV
        _, buffer = cv2.imencode('.jpg', cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR).copy())
        frame_bytes = buffer.tobytes()
        if not queue.full():
            queue.put({"frame": frame_bytes,
                       "percent":x_percent})

        #cv2.imshow("frame", gray)
        #if cv2.waitKey(1) == 27:
        #    break
        time.sleep(0.03)
    cv2.destroyAllWindows()
    cap.release()


