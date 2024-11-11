import os
import asyncio
import aiohttp
import boto3
import json
from dotenv import load_dotenv
from time import time
from tenacity import retry, stop_after_attempt, wait_fixed, wait_exponential


load_dotenv()

S3KEY_ID = os.getenv("S3KEY_ID")
S3KEY = os.getenv("S3KEY")
RECOGNIZER_TOKEN = os.getenv("RECOGNIZER_TOKEN")
BUCKET_NAME = os.getenv("BUCKET_NAME")
BUCKET_FOLDER = os.getenv("BUCKET_FOLDER")


session = boto3.session.Session()

s3 = session.client(
    service_name="s3",
    endpoint_url="https://storage.yandexcloud.net",
    aws_access_key_id=S3KEY_ID,
    aws_secret_access_key=S3KEY,
)


async def send_file_to_recognizer(token: str, bucket: str, file_name: str):
    url = "https://stt.api.cloud.yandex.net/stt/v3/recognizeFileAsync"
    headers = {"Authorization": token}
    data = {
        "uri": f"https://storage.yandexcloud.net/{bucket}/{file_name}",
        "recognitionModel": {
            "model": "general:rc",
            "audioFormat": {
                "containerAudio": {"containerAudioType": "OGG_OPUS"},
            },
            "textNormalization": {
                "textNormalization": "TEXT_NORMALIZATION_ENABLED",
                "profanityFilter": False,
                "literatureText": True,
                "phoneFormattingMode": "PHONE_FORMATTING_MODE_DISABLED",
            },
            "languageRestriction": {
                "languageCode": ["ru-RU"],
            },
            "audioProcessingType": "FULL_DATA",
        },
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise RuntimeError(f"Response status code: {response.status}")


@retry(stop=stop_after_attempt(50), wait=wait_fixed(2))
async def get_recognition(token: str, operationId: str) -> list:
    url = "https://stt.api.cloud.yandex.net/stt/v3/getRecognition"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    params = {"operationId": operationId}
    recognized_content = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                raise RuntimeError("No recognized content yet")
            async for json_line in response.content:
                recognized_content.append(json_line.decode("utf-8"))
    return recognized_content


async def parse_recognition_result(json_objects: list) -> str:
    for json_object in json_objects:
        try:
            normalized_text = json.loads(json_object)
            normalized_text = normalized_text["result"]["finalRefinement"][
                "normalizedText"
            ]["alternatives"][0]["text"]
            print(normalized_text)
        except (KeyError, IndexError):
            pass
    return json_objects



async def main():
    filename = f"{BUCKET_FOLDER}/test.ogg"
    s3.upload_file("audio/test.ogg", BUCKET_NAME, filename)
    recognition_request = await send_file_to_recognizer(
        RECOGNIZER_TOKEN, BUCKET_NAME, filename
    )
    recognition_response = await get_recognition(
        RECOGNIZER_TOKEN, recognition_request.get("id")
    )
    await parse_recognition_result(recognition_response)


if __name__ == "__main__":
    asyncio.run(main())
