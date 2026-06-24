# Deployment Guide

## 1. Create Lambda Function

Create a new AWS Lambda function.

Recommended settings:

```text
Runtime: Python 3.11
Architecture: x86_64
Timeout: 60 seconds
Memory: 512 MB
Region: us-east-1
```

Paste the code from:

```text
lambda_function.py
```

---

## 2. Add IAM Permission

Attach the policy from:

```text
iam_policy_bedrock.json
```

The Lambda execution role must be allowed to invoke:

```text
amazon.nova-pro-v1:0
```

---

## 3. Enable Bedrock Model Access

In Amazon Bedrock:

```text
Bedrock Console → Model access → Amazon Nova Pro → Enable access
```

---

## 4. Create API Gateway

Create an HTTP API or REST API.

Route:

```text
POST /backendLogicForZones
```

Integration:

```text
Lambda function
```

Enable CORS if calling from a browser frontend.

---

## 5. Test the API

Update the API URL inside:

```text
local_api_test.py
```

Then run:

```bash
python local_api_test.py
```

---

## 6. Optional S3 Workflow

Upload an image to S3:

```text
s3://your-s3-bucket-name/images/mapImage.jpeg
```

Update the bucket and key in:

```text
s3_predictor.py
```

Then run:

```bash
python s3_predictor.py
```

---

## 7. Troubleshooting

### AccessDeniedException

Check:

- Bedrock model access is enabled
- IAM role has `bedrock:InvokeModel`
- Region is `us-east-1`

### Invalid image error

Check:

- Image is base64 encoded correctly
- Image format is JPEG
- Request body has `image_base64`

### Lambda timeout

Increase timeout to 60 seconds.

### Payment error for paid models

Nova Pro may work if access is granted, but paid Marketplace models such as SDXL may require a valid AWS payment method.
