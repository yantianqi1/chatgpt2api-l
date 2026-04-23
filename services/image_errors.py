from __future__ import annotations

IMAGE_REQUEST_TIMEOUT_MESSAGE = "图片生成超时，请稍后重试"


class ImageGenerationError(Exception):
    pass


class ImageGenerationPendingError(ImageGenerationError):
    pass


class ImageGenerationTimeoutError(ImageGenerationError):
    pass


def image_generation_status_code(error: ImageGenerationError) -> int:
    if isinstance(error, ImageGenerationPendingError):
        return 503
    if isinstance(error, ImageGenerationTimeoutError):
        return 504
    return 502
