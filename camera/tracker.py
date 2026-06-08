import math

class CentroidTracker:

    def __init__(self):

        self.previous_center = None

    def track(self, detections):

        if not detections:
            return None

        # First frame
        if self.previous_center is None:

            best = max(
                detections,
                key=lambda obj: obj["area"]
            )

            self.previous_center = (
                best["cx"],
                best["cy"]
            )

            return best

        # Find closest object to previous center
        best_object = None
        min_distance = float("inf")

        px, py = self.previous_center

        for obj in detections:

            cx = obj["cx"]
            cy = obj["cy"]

            distance = math.sqrt(
                (cx - px) ** 2 +
                (cy - py) ** 2
            )

            if distance < min_distance:

                min_distance = distance
                best_object = obj

        # Update tracker memory
        if best_object:

            self.previous_center = (
                best_object["cx"],
                best_object["cy"]
            )

        return best_object