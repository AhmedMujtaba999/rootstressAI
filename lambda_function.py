import json
import base64
import boto3
import traceback

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))

        img_b64 = body.get("image_base64")
        user_prompt = body.get("text_input", "")

        if not img_b64:
            return _resp(400, {"status": "error", "message": "No image provided."})

        raw_bytes = base64.b64decode(img_b64)

        system_instruction = (
            "You are an agriculture assistant helping farmers understand and plan farm areas. "
            "Explain clearly in simple language. Do not use unnecessary technical jargon. "
            "When asked to divide a highlighted area into zones, provide practical farming-friendly guidance. "
            "If image generation is not available, clearly describe how the zones should be drawn."
        )

        payload = {
            "system": [
                {
                    "text": system_instruction
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": "jpeg",
                                "source": {
                                    "bytes": base64.b64encode(raw_bytes).decode("utf-8")
                                }
                            }
                        },
                        {
                            "text": user_prompt
                        }
                    ]
                }
            ]
        }

        response = bedrock.invoke_model(
            modelId="amazon.nova-pro-v1:0",
            body=json.dumps(payload),
            contentType="application/json",
            accept="application/json"
        )

        result = json.loads(response["body"].read())
        reply = result["output"]["message"]["content"][0]["text"]

        return _resp(
            200,
            {
                "status": "success",
                "reply": reply
            }
        )

    except Exception as e:
        trace = traceback.format_exc()
        print(trace)

        return _resp(
            500,
            {
                "status": "error",
                "message": str(e),
                "trace": trace
            }
        )


def _resp(code, body):
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }
