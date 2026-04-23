from __future__ import annotations

from services.account_service import account_service
from services.chatgpt_service import ChatGPTService
from test.utils import save_image


def main() -> None:
    prompt = "一只橘猫坐在窗台上，午后阳光，写实摄影"
    data = ChatGPTService(account_service).generate_with_pool(prompt, "gpt-5-3", 1, "url")
    for index, item in enumerate(data["data"], start=1):
        image_reference = item.get("url") or item.get("b64_json")
        if image_reference:
            print(save_image(image_reference, f"image_{index}"))


if __name__ == "__main__":
    main()
