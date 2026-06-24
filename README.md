# RootstressAI — Agricultural Zone Planner powered by AWS Bedrock

![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-FF9900?style=for-the-badge&logo=awslambda&logoColor=white)
![Amazon Bedrock](https://img.shields.io/badge/Amazon-Bedrock-232F3E?style=for-the-badge&logo=amazonaws&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![API Gateway](https://img.shields.io/badge/API-Gateway-FF4F8B?style=for-the-badge&logo=amazonaws&logoColor=white)
![Amazon S3](https://img.shields.io/badge/Amazon-S3-569A31?style=for-the-badge&logo=amazons3&logoColor=white)

> A serverless, multimodal AI system that accepts a farm field image and a natural-language instruction, then returns intelligent zone planning recommendations using **Amazon Nova Pro** on AWS Bedrock.

---

## Overview

Farmers frequently need to divide a selected field into usable zones for irrigation, crop rotation, soil treatment, and fertilization planning. **RootstressAI** automates this process by accepting an uploaded field image alongside a plain-English instruction and returning structured, actionable zone recommendations — no GIS tools required.

**Example prompt:**

```
Divide the highlighted boundary into 4 equal agricultural zones
suitable for crop rotation planning.
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     CLIENT / FRONTEND                   │
│              POST { image_base64, text_input }          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │ API Gateway │
                  └──────┬──────┘
                         │
                         ▼
                  ┌─────────────┐
                  │ AWS Lambda  │
                  └──────┬──────┘
                         │  image + prompt
                         ▼
            ┌────────────────────────┐
            │  Amazon Bedrock        │
            │  (Nova Pro v1)         │
            └────────────┬───────────┘
                         │  text response
                         ▼
                  ┌─────────────┐
                  │  JSON Reply │
                  └─────────────┘
```

**Optional S3 workflow:**

```
S3 Bucket  ──►  s3_predictor.py  ──►  Lambda  ──►  Bedrock
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Runtime | Python 3.11 |
| Compute | AWS Lambda |
| AI Model | Amazon Nova Pro (via Bedrock) |
| API | Amazon API Gateway |
| Storage | Amazon S3 |
| SDK | boto3 |
| Auth | IAM Role-based permissions |

---

## Key Features

- Multimodal input: accepts base64-encoded images + natural-language prompts
- Serverless architecture with zero server management
- Clean JSON request/response interface
- S3-based image ingestion workflow
- Local testing script for rapid iteration
- IAM policy template included for quick deployment
- Extensible to image generation models (Stable Diffusion XL, Titan Image Generator)

---

## API Reference

**Request**

```json
{
  "image_base64": "<base64_encoded_image>",
  "text_input": "Divide the highlighted area into 4 equal zones for crop rotation.",
  "metadata": {
    "user": "farm_operator_01",
    "timestamp": "2026-06-24T00:00:00Z"
  }
}
```

**Response**

```json
{
  "status": "success",
  "reply": "The selected area can be divided into 4 practical zones using two horizontal and two vertical divisions. This creates four regular sections optimized for crop planning, irrigation scheduling, and field access."
}
```

---

## Model Details

| Property | Value |
|----------|-------|
| Model ID | `amazon.nova-pro-v1:0` |
| Region | `us-east-1` |
| Input | Image + Text (multimodal) |
| Output | Structured text recommendation |

> **Note:** Amazon Nova Pro supports multimodal input but returns text-only output. Image overlay generation can be added using Stable Diffusion XL or Amazon Titan Image Generator in a future iteration.

---

## Project Structure

```
rootstressAI/
├── lambda_function.py      # Core Lambda handler
├── s3_predictor.py         # S3-based image ingestion
├── local_api_test.py       # Local test runner
├── requirements.txt        # Python dependencies
├── iam_policy_bedrock.json # IAM policy template
├── sample_event.json       # Sample Lambda event payload
├── sample_payload.json     # Sample API request payload
├── DEPLOYMENT.md           # Step-by-step deployment guide
└── PROJECT_SUMMARY.md      # High-level project summary
```

---

## Getting Started

**Install dependencies**

```bash
pip install -r requirements.txt
```

**Run locally against the API**

```bash
python local_api_test.py
```

**Run the S3 predictor**

```bash
python s3_predictor.py
```

---

## Deployment

1. Create an AWS Lambda function (Python 3.11 runtime)
2. Upload `lambda_function.py`
3. Attach the IAM policy from `iam_policy_bedrock.json`
4. Create an API Gateway HTTP API and connect it to the Lambda
5. Deploy the stage and copy the invoke URL
6. Update `local_api_test.py` with the invoke URL and run a smoke test

Full step-by-step instructions are in [`DEPLOYMENT.md`](./DEPLOYMENT.md).

**Required IAM permissions:**

```
bedrock:InvokeModel
logs:CreateLogGroup
logs:CreateLogStream
logs:PutLogEvents
```

---

## Roadmap

- [ ] Integrate Stable Diffusion XL / Titan Image Generator for annotated image output
- [ ] Use OpenCV to programmatically draw zone boundaries on the original image
- [ ] Persist request history in DynamoDB
- [ ] Add a React frontend with drag-and-drop image upload
- [ ] Integrate Amazon Cognito for user authentication
- [ ] Incorporate soil, water, and crop-type data for context-aware zone recommendations

---

## About

RootstressAI demonstrates a production-oriented serverless AI pipeline combining **AWS Lambda**, **Amazon Bedrock multimodal AI**, **S3 image handling**, and **API Gateway** to solve a tangible agricultural planning problem. The project reflects practical experience with cloud-native backend engineering, AI model integration, and REST API design on AWS.
