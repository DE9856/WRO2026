FOCAL_LENGTH = 700

REAL_PILLAR_HEIGHT = 10  # cm

def estimate_distance(pixel_height):

    if pixel_height <= 0:
        return 999

    distance = (
        REAL_PILLAR_HEIGHT * FOCAL_LENGTH
    ) / pixel_height

    return round(distance, 2)