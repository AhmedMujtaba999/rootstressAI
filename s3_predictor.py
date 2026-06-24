import json
import base64
import boto3
import requests
from datetime import datetime

S3_BUCKET_NAME = "your-s3-bucket-name"
S3_OBJECT_KEY = "images/mapImage.jpeg"
API_URL = "https://your-api-id.execute-api.us-east-1.amazonaws.com/backendLogicForZones"

s3 = boto3.client("s3")


def get_image_from_s3(bucket_name, object_key):
    response = s3.get_object(
        Bucket=bucket_name,
        Key=object_key
    )

    image_bytes = response["Body"].read()
    return base64.b64encode(image_bytes).decode("utf-8")


def send_to_lambda_api(encoded_image):
    payload = {
        "image_base64": encoded_image,
        "text_input": (
            "You will receive an image showing a green-coloured dotted boundary. "
            "Please divide the highlighted area into 4 zones of roughly equal size. "
            "These zones are for agricultural use, so make them practical and regular in shape. "
            "Do not use any external maps or resources. Only analyze the provided image."
        ),
        "metadata": {
            "source": "s3_predictor",
            "timestamp": datetime.utcnow().isoformat()
        }
    }

    response = requests.post(
        API_URL,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=60
    )

    return response


def main():
    encoded_image = get_image_from_s3(S3_BUCKET_NAME, S3_OBJECT_KEY)
    response = send_to_lambda_api(encoded_image)

    print("Status Code:", response.status_code)

    try:
        print("Response JSON:", json.dumps(response.json(), indent=2))
    except Exception:
        print("Raw Response:", response.text)


if __name__ == "__main__":
    main()
