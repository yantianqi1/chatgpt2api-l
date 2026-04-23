from test.utils import post_json, save_image


def main() -> None:
    prompt = "A cute orange cat sitting on a chair"
    result = post_json("/v1/chat/completions", {"model": "gpt-image-1", "stream": False, "messages": [{"role": "user", "content": prompt}]})
    for index, item in enumerate(result["choices"][0]["message"]["images"], start=1):
        image_reference = item.get("url") or item.get("b64_json")
        if image_reference:
            print(save_image(image_reference, f"completions_{index}"))


if __name__ == "__main__":
    main()
