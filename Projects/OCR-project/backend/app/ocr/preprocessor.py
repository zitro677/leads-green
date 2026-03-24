import numpy as np
from PIL import Image, ImageEnhance
import cv2


def preprocess_image(image: Image.Image) -> Image.Image:
    img = image.convert("L")
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    cv_img = np.array(img)
    cv_img = cv2.adaptiveThreshold(
        cv_img, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2,
    )
    cv_img = cv2.fastNlMeansDenoising(cv_img, h=10)

    return Image.fromarray(cv_img)
