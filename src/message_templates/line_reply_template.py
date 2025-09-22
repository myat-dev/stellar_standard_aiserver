import requests

from src.helpers.env_loader import CHANNEL_ACCESS_TOKEN
from src.helpers import logger


def reply_to_user(reply_token: str, message: str):
    """Send a reply message to the user via LINE API."""
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": message}],
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        logger.error(f"Error sending reply: {response.status_code}, {response.text}")
