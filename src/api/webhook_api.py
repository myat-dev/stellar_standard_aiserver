from fastapi import APIRouter, Request
import httpx
from src.helpers.availability_storage import availability_responses, set_response
from src.helpers.conf_loader import server_config_loader, server_config
from src.helpers.enums import Mode
from src.helpers.logger import logger
from src.message_templates.line_push_template import ResponseNotiMessage
from src.message_templates.line_reply_template import reply_to_user
from src.helpers.conf_loader import LINE_USER1, LINE_USER2
from src.helpers.env_loader import CHANNEL_ACCESS_TOKEN

router = APIRouter()

# Mode handler mapping
MODE_HANDLERS = {
    Mode.ZAITAKU.value: Mode.ZAITAKU,
    Mode.HANZAITAKU.value: Mode.HANZAITAKU,
    Mode.FUZAI.value: Mode.FUZAI,
}

RICH_MENU_MAP = {
    Mode.ZAITAKU: server_config.get("zaitaku_menu", ""),
    Mode.HANZAITAKU: server_config.get("hanzaitaku_menu", ""),
    Mode.FUZAI: server_config.get("fuzai_menu", ""),
}

AVAILABILITY_MESSAGE_MAP = {
    "今すぐ対応する": "ありがとうございます！訪問者に伝えます。",
    "2分以内に対応する": "ありがとうございます！訪問者に伝えます。",
    "対応出来ない": "分かりました。訪問者に伝えます。",
}


def handle_unknown_postback(reply_token):
    """Handle unknown postback data."""
    reply_to_user(reply_token, "対応できないリクエストです。")


@router.post("/webhook")
async def webhook(request: Request):
    """LINE webhook to handle incoming messages and button clicks."""
    data = await request.json()

    for event in data.get("events", []):
        user_id = event["source"]["userId"]
        logger.info(f"User id: {user_id}")
        event_type = event.get("type")
        reply_token = event.get("replyToken")

        if event_type == "message":
            await handle_message(event, reply_token, user_id)

    return {"status": "ok"}

async def handle_message(event, reply_token, user_id):
    """Handle text messages."""
    message_type = event["message"]["type"]

    if message_type == "text":
        user_message = event["message"]["text"]

        if user_message in AVAILABILITY_MESSAGE_MAP:
            set_response(user_id=user_id, response_type=user_message)
            reply_to_user(reply_token, AVAILABILITY_MESSAGE_MAP[user_message])
            return

        mode = MODE_HANDLERS.get(user_message)
        if mode:
            await change_mode_and_reply(mode, reply_token, user_id)
            return

        reply_to_user(reply_token, "申し訳ございません。対応できないリクエストです。")

async def switch_rich_menu(user_id: str, rich_menu_id: str):
    url = f"https://api.line.me/v2/bot/user/{user_id}/richmenu/{rich_menu_id}"
    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers)
        # if response.status_code != 200:
        #     logger.error(f"Failed to switch rich menu: {response.text}")
        # else:
        #     logger.info(f"Switched rich menu to {rich_menu_id}")

async def change_mode_and_reply(mode: str, reply_token: str, user_id: str):
    """Change mode and send confirmation to the user."""
    line_ids = LINE_USER1 + LINE_USER2
    server_config_loader.update_mode(mode.value)
    rich_menu_id = RICH_MENU_MAP.get(mode)
    if rich_menu_id:
        for line_id in line_ids:
            await switch_rich_menu(line_id, rich_menu_id)
        logger.info(f"Switched rich menu to {rich_menu_id}")
        
    reply_to_user(
        reply_token, f"モード変更しました:\n{mode.value}"
    )

    if user_id in LINE_USER1:
        person_label = f"住職_{'Android' if LINE_USER1.index(user_id) == 0 else 'iPhone'}"
    else:
        person_label = f"奥様"

    for _, line_id in enumerate(line_ids):
        if line_id != user_id:
            message = f"{person_label}が「{mode.value}」に変更しました。"
            ResponseNotiMessage(line_id, message).send()
