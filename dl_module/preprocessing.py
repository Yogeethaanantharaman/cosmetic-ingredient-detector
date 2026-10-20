
import cv2
import numpy as np

MAX_DIMENSION = 1800


def preprocess_image(image_bytes: bytes):
    """
    Decode the uploaded image and resize oversized images.
    Preserve the aspect ratio and avoid unnecessary enlargement.
    """
    if not image_bytes:
        raise ValueError("The uploaded image is empty.")

    image_array = np.frombuffer(
        image_bytes,
        dtype=np.uint8,
    )

    image = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise ValueError(
            "Unable to read the uploaded image. "
            "Please upload a valid JPG, JPEG, or PNG image."
        )

    height, width = image.shape[:2]
    largest_dimension = max(height, width)

    if largest_dimension > MAX_DIMENSION:
        scale = MAX_DIMENSION / largest_dimension

        new_width = max(
            1,
            round(width * scale),
        )

        new_height = max(
            1,
            round(height * scale),
        )

        image = cv2.resize(
            image,
            (new_width, new_height),
            interpolation=cv2.INTER_AREA,
        )

    return image
