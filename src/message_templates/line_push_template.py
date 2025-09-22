import re
from abc import ABC, abstractmethod

import requests

from src.helpers import logger
from src.helpers.conf_loader import NGROK_URL, OPEN_LINE_MESSAGES
from src.helpers.env_loader import *
from src.helpers.env_loader import CHANNEL_ACCESS_TOKEN


class PushMessageTemplate(ABC):
    def __init__(self, user_id):
        self.url = "https://api.line.me/v2/bot/message/push"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        }
        self.user_id = user_id

    @abstractmethod
    def create_payload(self):
        pass

    def send(self):
        if not OPEN_LINE_MESSAGES:
            logger.info("LINEメッセージ送信は無効化されています。")
            return None
        
        payload = self.create_payload()
        # logger.info(f"Sending payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        response = requests.post(self.url, json=payload, headers=self.headers)

        if response.status_code == 200:
            logger.info("Message sent successfully!")
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
        return response


class ButtonMessage(PushMessageTemplate):
    def __init__(self, user_id, alt_text, title, text, actions):
        super().__init__(user_id)
        self.alt_text = alt_text
        self.title = title
        self.text = text
        self.actions = actions

    def create_payload(self):
        return {
            "to": self.user_id,
            "messages": [
                {
                    "type": "template",
                    "altText": self.alt_text,
                    "template": {
                        "type": "buttons",
                        "title": self.title,
                        "text": self.text,
                        "actions": self.actions,
                    },
                }
            ],
        }


class TextMessage(PushMessageTemplate):
    def __init__(self, user_id, text):
        super().__init__(user_id)
        self.text = text

    def create_payload(self):
        return {"to": self.user_id, "messages": [{"type": "text", "text": self.text}]}


class CheckAvailablityMessage(ButtonMessage):
    def __init__(
        self, user_id: str, line_message: str, title_text="来訪者が来ています。"
    ):
        alt_text = "来訪者が受付に来ています。ご対応できますか？"
        template_text = line_message.strip()
        actions = [
            {"type": "message", "label": "今すぐ対応する", "text": "今すぐ対応する"},
            {
                "type": "message",
                "label": "2分以内に対応する",
                "text": "2分以内に対応する",
            },
            {"type": "message", "label": "対応出来ない", "text": "対応出来ない"},
        ]
        super().__init__(user_id, alt_text, title_text, template_text, actions)


class CallButtonMessage(ButtonMessage):
    def __init__(self, user_id, name, phone_number, purpose, title):
        name_display = name if name else "来訪者"
        
        # Clean phone number
        cleaned_phone_number = (
            re.sub(r"[^\d+]", "", phone_number) if phone_number else ""
        )

        # Build message text and actions
        if cleaned_phone_number:
            phone_display = f"連絡先は{cleaned_phone_number}です。"
            text_body = f"{purpose} {phone_display}"  # Concise version for `text` field
            actions = [
                {
                    "type": "uri",
                    "label": "お電話をかける",
                    "uri": f"tel:{cleaned_phone_number}",
                }
            ]
        else:
            phone_display = "連絡先はありません。"
            text_body = f"{purpose} {phone_display}"
            actions = [
                {
                    "type": "message",
                    "label": "連絡先なし",
                    "text": "電話番号が登録されていません。",
                }
            ]

        # Truncate text to 60 characters max (LINE limit)
        truncated_text = text_body[:60]

        # Full version for altText or title
        alt_text = f"{name_display}様がお寺に訪問しました"
        title = title
        super().__init__(user_id, alt_text, title, truncated_text, actions)


class ImageMessage(PushMessageTemplate):
    def __init__(self, user_id: str, file_name: str):
        image_url = f"{NGROK_URL}/line_images/{file_name}.jpg"
        super().__init__(user_id)
        self.image_url = image_url
        print(f"Image URL: {self.image_url}")

    def create_payload(self):
        return {
            "to": self.user_id,
            "messages": [
                {
                    "type": "image",
                    "originalContentUrl": self.image_url,
                    "previewImageUrl": self.image_url,
                }
            ],
        }


class ImageWithTextMessage(PushMessageTemplate):
    def __init__(self, user_id: str, file_name: str, message_text: str):
        image_url = f"{NGROK_URL}/line_images/{file_name}.jpg"
        super().__init__(user_id)
        self.image_url = image_url
        self.message_text = message_text

    def create_payload(self):
        return {
            "to": self.user_id,
            "messages": [
                {"type": "text", "text": self.message_text},
                {
                    "type": "image",
                    "originalContentUrl": self.image_url,
                    "previewImageUrl": self.image_url,
                },
            ],
        }


class SendOnlyMessage(PushMessageTemplate):
    def __init__(self, user_id: str, message_text: str, title_text: str = None):
        super().__init__(user_id)
        self.message_text = message_text
        self.title_text = title_text

    def create_payload(self):
        return {
            "to": self.user_id,
            "messages": [
                {
                    "type": "flex",
                    "altText": "伝言があります",
                    "contents": {
                        "type": "bubble",
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": self.title_text,
                                    "weight": "bold",  # ★ 太字
                                    "size": "lg",  # ★ 大きく
                                    "align": "start",
                                    "wrap": True,
                                },
                                {
                                    "type": "text",
                                    "text": self.message_text,
                                    "wrap": True,
                                    "margin": "md",
                                },
                            ],
                        },
                    },
                }
            ],
        }


class ResponseNotiMessage(PushMessageTemplate):
    def __init__(self, user_id: str, message_text: str, title_text: str = None):
        super().__init__(user_id)
        self.message_text = message_text
        self.title_text = title_text

    def create_payload(self):
        return {
            "to": self.user_id,
            "messages": [
                {
                    "type": "text",
                    "text": (
                        f"{self.title_text}\n{self.message_text}"
                        if self.title_text
                        else self.message_text
                    ),
                }
            ],
        }
