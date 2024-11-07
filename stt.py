import os
import boto3
import requests
import jsonlines
from dotenv import load_dotenv
from time import sleep
from tenacity import retry, stop_after_attempt, wait_fixed


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
    aws_secret_access_key=S3KEY
)


def send_file_to_recognizer(token: str, bucket: str, file_name: str):
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
        }
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()


@retry(stop=stop_after_attempt(10), wait=wait_fixed(5))
def get_recognition(token: str, operationId: str):
    url = "https://stt.api.cloud.yandex.net/stt/v3/getRecognition"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    params = {"operationId": operationId}
    response = requests.get(url, headers=headers, params=params, stream=True)
    if response.status_code == 200:
        json_objects = []
        with jsonlines.Reader(response.iter_lines()) as reader:
            for obj in reader:
                json_objects.append(obj)
        for json_object in json_objects:
            try:
                normalized_text = json_object["result"]["finalRefinement"]["normalizedText"]["alternatives"][0]["text"]
                print(normalized_text, "\n\n")
            except Exception as e:
                pass
        return json_objects
    else:
        raise ValueError("No recognized content yet")
        

def main():
    filename = f"{BUCKET_FOLDER}/test.ogg"
    s3.upload_file('audio/test.ogg', BUCKET_NAME, filename)
    recognition_id = send_file_to_recognizer(RECOGNIZER_TOKEN, BUCKET_NAME, filename).get("id")
    sleep(3)
    recognition_response = get_recognition(RECOGNIZER_TOKEN, recognition_id)


if __name__ == "__main__":
    main()
