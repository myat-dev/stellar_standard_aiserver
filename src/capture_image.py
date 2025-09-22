import os

import cv2

from src.helpers.logger import logger
from src.resource_path import src_path


def capture_image(session_id, camera_index=0):
    # Try multiple backends
    folder_path = src_path("line_images")
    filename = os.path.join(folder_path, f"{session_id}.jpg")
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_V4L2, 0]

    for backend in backends:

        cap = cv2.VideoCapture(camera_index, backend)
        logger.info(f"Trying to open camera :{cap} with backend {backend}")
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                cv2.imwrite(filename, frame)
                logger.info(f"Image saved as {filename} using backend {backend}")
                return
            else:
                logger.error(f"Failed to capture frame with backend {backend}")
        else:
            logger.error(f"Could not open camera with backend {backend}")
