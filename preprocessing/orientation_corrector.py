import logging

import cv2
import easyocr

logger = logging.getLogger(__name__)

_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def rotate_image(image, angle):

    if angle == 0:
        return image

    if angle == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)

    if angle == 180:
        return cv2.rotate(image, cv2.ROTATE_180)

    if angle == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)

    return image


def score_text(image):

    try:
        results = _get_reader().readtext(image)

        if len(results) == 0:
            return 0

        confidences = [r[2] for r in results]

        return sum(confidences) / len(confidences)

    except Exception as exc:
        logger.debug("Orientation OCR scoring failed: %s", exc)
        return 0


def detect_best_orientation(image):

    angles = [0, 90, 180, 270]

    best_score = -1
    best_angle = 0

    for angle in angles:

        rotated = rotate_image(image, angle)

        score = score_text(rotated)

        if score > best_score:
            best_score = score
            best_angle = angle

    return best_angle


def correct_orientation(image):
    """Return the rotated image together with the applied angle."""
    angle = detect_best_orientation(image)
    return rotate_image(image, angle), angle