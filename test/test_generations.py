from test.utils import post_json, save_image


def main() -> None:
    prompt = "A cute orange cat sitting on a chair"
    result = post_json("/v1/images/generations", {"prompt": prompt, "model": "gpt-image-1", "n": 1})
    for index, item in enumerate(result["data"], start=1):
        image_reference = item.get("url") or item.get("b64_json")
        if image_reference:
            print(save_image(image_reference, f"generations_{index}"))


if __name__ == "__main__":
    main()
