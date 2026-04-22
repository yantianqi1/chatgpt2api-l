from __future__ import annotations

from contextlib import contextmanager
import json
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from fastapi.testclient import TestClient

from services.api import create_app
from services.chatgpt_service import ChatGPTService
from services.config import config


ROOT_DIR = Path(__file__).resolve().parents[1]
ROOT_CONFIG_FILE = ROOT_DIR / "config.json"
GENERATED_IMAGE_DIR = ROOT_DIR / "data" / "generated-images"


class ChatCompletionsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._created_root_config = False
        if not ROOT_CONFIG_FILE.exists():
            ROOT_CONFIG_FILE.write_text(json.dumps({"auth-key": "test-auth"}), encoding="utf-8")
            cls._created_root_config = True

        cls.client = TestClient(create_app())
        cls.headers = {
            "Authorization": f"Bearer {config.auth_key}",
            "Content-Type": "application/json",
        }

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._created_root_config and ROOT_CONFIG_FILE.exists():
            ROOT_CONFIG_FILE.unlink()

    @contextmanager
    def generated_image_file(self, file_name: str, content: bytes):
        GENERATED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        image_path = GENERATED_IMAGE_DIR / file_name
        image_path.write_bytes(content)
        try:
            yield image_path
        finally:
            if image_path.exists():
                image_path.unlink()

    def test_chat_completions_accepts_text_requests(self) -> None:
        mocked_response = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "hello",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }

        with patch.object(
            ChatGPTService,
            "create_chat_completion",
            create=True,
            return_value=mocked_response,
        ) as mocked_create:
            response = self.client.post(
                "/v1/chat/completions",
                headers=self.headers,
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {
                            "role": "user",
                            "content": "say hello",
                        }
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mocked_response)
        self.assertEqual(mocked_create.call_count, 1)

    def test_chat_completions_streams_text_requests_as_sse(self) -> None:
        mocked_response = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "hello",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        with patch.object(ChatGPTService, "create_chat_completion", return_value=mocked_response) as mocked_create:
            response = self.client.post(
                "/v1/chat/completions",
                headers=self.headers,
                json={
                    "model": "gpt-4o",
                    "stream": True,
                    "messages": [
                        {
                            "role": "user",
                            "content": "say hello",
                        }
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn('"object":"chat.completion.chunk"', response.text)
        self.assertIn('"content":"hello"', response.text)
        self.assertIn("data: [DONE]", response.text)
        self.assertEqual(mocked_create.call_count, 1)

    def test_chat_completions_streams_image_requests_as_sse(self) -> None:
        mocked_response = {
            "id": "chatcmpl-image",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-image-2",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "![image_1](data:image/png;base64,abc)",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        with patch.object(ChatGPTService, "create_chat_completion", return_value=mocked_response) as mocked_create:
            response = self.client.post(
                "/v1/chat/completions",
                headers=self.headers,
                json={
                    "model": "gpt-image-2",
                    "stream": True,
                    "messages": [
                        {
                            "role": "system",
                            "content": "[Start a new Chat]",
                        },
                        {
                            "role": "user",
                            "content": "draw a cat",
                        },
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn("data:image/png;base64,abc", response.text)
        self.assertIn("data: [DONE]", response.text)
        self.assertEqual(mocked_create.call_count, 1)

    def test_responses_stream_requests_as_sse(self) -> None:
        mocked_response = {
            "id": "resp_1",
            "object": "response",
            "created_at": 0,
            "status": "completed",
            "error": None,
            "incomplete_details": None,
            "model": "gpt-5",
            "output": [
                {
                    "id": "ig_1",
                    "type": "image_generation_call",
                    "status": "completed",
                    "result": "abc",
                    "revised_prompt": "draw a cat",
                }
            ],
        }

        with patch.object(ChatGPTService, "create_response", return_value=mocked_response) as mocked_create:
            response = self.client.post(
                "/v1/responses",
                headers=self.headers,
                json={
                    "model": "gpt-5",
                    "stream": True,
                    "tools": [{"type": "image_generation"}],
                    "input": "draw a cat",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn('"type":"response.completed"', response.text)
        self.assertIn('"result":"abc"', response.text)
        self.assertIn("data: [DONE]", response.text)
        self.assertEqual(mocked_create.call_count, 1)

    def test_page_routes_accept_head_requests(self) -> None:
        response = self.client.head("/image/")
        self.assertNotEqual(response.status_code, 405)

    def test_service_builds_text_chat_completion_response(self) -> None:
        service = ChatGPTService(account_service=None)  # type: ignore[arg-type]
        with patch.object(service, "generate_text_with_pool", return_value="hello"):
            result = service.create_chat_completion(
                {
                    "model": "gpt-4o",
                    "messages": [
                        {
                            "role": "user",
                            "content": "say hello",
                        }
                    ],
                }
            )

        self.assertEqual(result["object"], "chat.completion")
        self.assertEqual(result["choices"][0]["message"]["content"], "hello")

    def test_service_keeps_image_requests_on_image_path(self) -> None:
        mocked_response = {"created": 0, "data": [{"b64_json": "abc"}]}
        service = ChatGPTService(account_service=None)  # type: ignore[arg-type]
        with patch.object(service, "create_image_completion", return_value=mocked_response) as mocked_create:
            result = service.create_chat_completion(
                {
                    "model": "gpt-image-1",
                    "messages": [
                        {
                            "role": "user",
                            "content": "draw a cat",
                        }
                    ],
                }
            )

        self.assertEqual(result, mocked_response)
        self.assertEqual(mocked_create.call_count, 1)

    def test_service_builds_image_chat_completion_with_markdown_urls_by_default(self) -> None:
        service = ChatGPTService(account_service=None)  # type: ignore[arg-type]
        with patch.object(
            service,
            "generate_with_pool",
            return_value={
                "created": 0,
                "data": [{"url": "https://img.example.com/generated-images/cat.png", "revised_prompt": "draw a cat"}],
            },
        ):
            result = service.create_chat_completion(
                {
                    "model": "gpt-image-2",
                    "messages": [
                        {
                            "role": "user",
                            "content": "draw a cat",
                        }
                    ],
                }
            )

        self.assertEqual(
            result["choices"][0]["message"]["content"],
            "![image_1](https://img.example.com/generated-images/cat.png)",
        )
        self.assertEqual(
            result["choices"][0]["message"]["images"],
            [{"url": "https://img.example.com/generated-images/cat.png", "revised_prompt": "draw a cat"}],
        )

    def test_service_builds_response_image_output_with_urls_by_default(self) -> None:
        service = ChatGPTService(account_service=None)  # type: ignore[arg-type]
        with patch.object(
            service,
            "generate_with_pool",
            return_value={
                "created": 0,
                "data": [{"url": "https://img.example.com/generated-images/cat.png", "revised_prompt": "draw a cat"}],
            },
        ):
            result = service.create_response(
                {
                    "model": "gpt-5",
                    "tools": [{"type": "image_generation"}],
                    "input": "draw a cat",
                }
            )

        self.assertEqual(result["output"][0]["result"], "https://img.example.com/generated-images/cat.png")

    def test_images_generation_defaults_to_url_response_format(self) -> None:
        with patch.object(
            ChatGPTService,
            "generate_with_pool",
            autospec=True,
            return_value={"created": 1, "data": [{"url": "https://img.example.com/generated-images/cat.png"}]},
        ) as mocked_generate:
            response = self.client.post(
                "/v1/images/generations",
                headers=self.headers,
                json={
                    "prompt": "draw a cat",
                    "model": "gpt-image-2",
                    "n": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        mocked_generate.assert_called_once_with(ANY, "draw a cat", "gpt-image-2", 1, "url")

    def test_generated_images_are_served_as_static_files(self) -> None:
        with self.generated_image_file("test-image.png", b"png-bytes"):
            response = self.client.get("/generated-images/test-image.png")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"png-bytes")


if __name__ == "__main__":
    unittest.main()
