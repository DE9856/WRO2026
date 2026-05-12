import cv2
from camera.distance import estimate_distance

def detect_objects(mask, frame, color_name, draw_color):

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )
    detections = []

    for cnt in contours:
        area = cv2.contourArea(cnt)

        if area > 500:
            x, y, w, h = cv2.boundingRect(cnt)
            cx = x + w // 2
            cy = y + h // 2

            dist = estimate_distance(h)  # renamed to avoid clash with module

            cv2.rectangle(frame, (x, y), (x+w, y+h), draw_color, 2)
            cv2.circle(frame, (cx, cy), 5, (255, 255, 255), -1)
            cv2.putText(frame, f"{dist:.1f} cm", (x, y+h+20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, draw_color, 2)

            detections.append({
                "x": x, "y": y, "w": w, "h": h,
                "cx": cx, "cy": cy, "area": area
            })

    return detections