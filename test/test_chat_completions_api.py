from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api import create_app
from services.chatgpt_service import ChatGPTService
from services.config import config


ROOT_DIR = Path(__file__).resolve().parents[1]
ROOT_CONFIG_FILE = ROOT_DIR / "config.json"


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


if __name__ == "__main__":
    unittest.main()
