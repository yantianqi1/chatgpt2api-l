from __future__ import annotations

UPSTREAM_IMAGE_POLICY_MESSAGE = (
    "非常抱歉，生成的图片可能违反了我们的内容政策。如果你认为此判断有误，请重试或修改提示语。"
)
OPENAI_INVALID_REQUEST_ERROR = "invalid_request_error"
IMAGE_GENERATION_ERROR_TYPE = "image_generation_error"
CONTENT_POLICY_VIOLATION_CODE = "content_policy_violation"
IMAGE_GENERATION_TIMEOUT_CODE = "image_generation_timeout"
IMAGE_GENERATION_PENDING_CODE = "image_generation_pending"
IMAGE_GENERATION_FAILED_CODE = "image_generation_failed"

# Moderated upstream image requests commonly surface locally as request timeouts.
IMAGE_REQUEST_TIMEOUT_MESSAGE = UPSTREAM_IMAGE_POLICY_MESSAGE


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


def image_generation_error_code(error: ImageGenerationError) -> str:
    if isinstance(error, ImageGenerationPendingError):
        return IMAGE_GENERATION_PENDING_CODE
    if isinstance(error, ImageGenerationTimeoutError):
        if str(error) == UPSTREAM_IMAGE_POLICY_MESSAGE:
            return CONTENT_POLICY_VIOLATION_CODE
        return IMAGE_GENERATION_TIMEOUT_CODE
    return IMAGE_GENERATION_FAILED_CODE


def image_generation_error_type(error: ImageGenerationError) -> str:
    if image_generation_error_code(error) == CONTENT_POLICY_VIOLATION_CODE:
        return OPENAI_INVALID_REQUEST_ERROR
    return IMAGE_GENERATION_ERROR_TYPE


def image_generation_error_payload(error: ImageGenerationError) -> dict[str, object]:
    return {
        "error": {
            "message": str(error),
            "type": image_generation_error_type(error),
            "param": None,
            "code": image_generation_error_code(error),
        }
    }
