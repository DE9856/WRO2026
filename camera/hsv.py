import cv2
from config.hsv_config import *

def get_red_mask(hsv):
    mask1 = cv2.inRange(hsv, RED_LOWER1, RED_UPPER1)
    mask2 = cv2.inRange(hsv, RED_LOWER2, RED_UPPER2)
    return cv2.bitwise_or(mask1, mask2)

def get_green_mask(hsv):
    return cv2.inRange(hsv, GREEN_LOWER, GREEN_UPPER)