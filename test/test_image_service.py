from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

if "curl_cffi.requests" not in sys.modules:
    curl_cffi_module = types.ModuleType("curl_cffi")
    requests_module = types.ModuleType("curl_cffi.requests")
    requests_module.Session = object
    curl_cffi_module.requests = requests_module
    sys.modules["curl_cffi"] = curl_cffi_module
    sys.modules["curl_cffi.requests"] = requests_module

from services.image_service import (
    generate_image_result,
)
from services.image_errors import ImageGenerationPendingError


class FakeSession:
    def close(self) -> None:
        return None


class ImageServiceTests(unittest.TestCase):
    def test_generate_image_result_fails_fast_when_upstream_reports_pending_queue(self) -> None:
        with (
            patch("services.image_service._new_session", return_value=(FakeSession(), {})),
            patch("services.image_service._bootstrap", return_value="device-id"),
            patch("services.image_service._chat_requirements", return_value=("chat-token", {})),
            patch("services.image_service._send_conversation", return_value=object()),
            patch(
                "services.image_service._parse_sse",
                return_value={
                    "conversation_id": "conv-1",
                    "file_ids": [],
                    "text": "正在处理图片\n\n目前有很多人在创建图片，因此可能需要一点时间。图片准备好后我们会通知你。",
                },
            ),
            patch("services.image_service._poll_image_ids") as mocked_poll,
        ):
            with self.assertRaises(ImageGenerationPendingError):
                generate_image_result("token-1", "draw a cat", "gpt-image-2", "url")

        mocked_poll.assert_not_called()
