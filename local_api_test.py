import requests
import json
import base64
from datetime import datetime
from pathlib import Path

API_URL = "https://your-api-id.execute-api.us-east-1.amazonaws.com/backendLogicForZones"
IMAGE_PATH = "mapImage.jpeg"


def encode_image(image_path):
    path = Path(image_path)

    if not path.exists():
        return None

    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def main():
    encoded_image = encode_image(IMAGE_PATH)

    payload = {
        "image_base64": encoded_image,
        "text_input": (
            "You will receive an image showing a green-coloured dotted boundary. "
            "Please divide the highlighted area into 4 zones of roughly equal size. "
            "These zones are for agricultural use, so make them practical and regular in shape. "
            "Do not use any external maps or resources. Only analyze the provided image."
        ),
        "metadata": {
            "user": "test_user",
            "timestamp": datetime.utcnow().isoformat()
        }
    }

    response = requests.post(
        API_URL,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=60
    )

    print("Status Code:", response.status_code)

    try:
        print("Response JSON:", json.dumps(response.json(), indent=2))
    except Exception:
        print("Raw Response:", response.text)


if __name__ == "__main__":
    main()
