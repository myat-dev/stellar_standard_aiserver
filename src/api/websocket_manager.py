import asyncio
from typing import Optional

from fastapi import WebSocket

from src.helpers import logger
from src.helpers.enums import ActionType
from src.message_templates.websocket_message_template import ActionMessage, ChatActionMessage

class WebSocketManager:
    """WebSocketの接続とメッセージ管理を行うクラス。"""

    def __init__(self):
        self.active_client: WebSocket | None = None
        self.response_queue = asyncio.Queue()
        self.waiting_for_response = False
        self.connected = False
        self.button_id: Optional[str] = None
        self.session_end_event = asyncio.Event()
        self.touch_event = None

    def set_button_id(self, button_id: str):
        self.button_id = button_id

    def get_button_id(self) -> Optional[str]:
        return self.button_id

    def clear_button_id(self):
        """ボタンIDをクリアする。"""
        self.button_id = None

    async def connect(self, websocket: WebSocket):
        """WebSocket接続を受け付ける。"""
        if self.active_client and self.connected:
            logger.warning(
                "新しいクライアントが接続しようとしています。既存の接続を切断します..."
            )
            try:
                await self.active_client.close()
            except RuntimeError:
                logger.warning("既存の接続はすでに切断されています。無視します。")

        await websocket.accept()
        self.active_client = websocket
        self.connected = True
        logger.info("クライアントが接続されました。")

    async def disconnect(self):
        """WebSocket接続を切断する。"""
        if self.active_client and self.connected:
            try:
                await self.active_client.close()
                logger.info("クライアントの接続を切断しました。")
            except RuntimeError:
                logger.warning("接続はすでに切断されています。無視します。")
            finally:
                self.connected = False
                self.active_client = None

    async def send_to_client(self, message: object):
        """クライアントにメッセージを送信する。"""
        allow_send = (
            self.button_id is not None
            or (isinstance(message, ActionMessage) and message.action_type == ActionType.SHOW_TOP.value)
            or (isinstance(message, ChatActionMessage) and message.action.action_type == ActionType.SHOW_TOP.value)
            or (isinstance(message, ActionMessage) and message.action_type == ActionType.PHONEEND_ACTION.value)
            or (isinstance(message, ChatActionMessage) and message.action.action_type == ActionType.SHOW_PHONE_PAGE.value)
            or (isinstance(message, ActionMessage) and message.action_type == ActionType.SET_LANGUAGE.value)
        )
        if self.active_client and self.connected:
            
            if allow_send:
                try:
                    logger.info(f"Websocket Message sent: {message.__dict__}")
                    await self.active_client.send_text(message.to_json())
                except Exception as e:
                    logger.error(
                        f"クライアントへのメッセージ送信中にエラーが発生しました: {e}"
                    )
                    # await self.disconnect()
            else:
                logger.warning(
                    "ボタンIDが設定されていません。メッセージを送信できません。"
                )

    def notify_touch(self):
        if self.touch_event and not self.touch_event.is_set():
            self.touch_event.set()

    async def wait_for_user_response(self, timeout: int = 30) -> str:
        """ユーザーの応答を指定時間まで待機する。"""
        self.waiting_for_response = True
        self.session_end_event = asyncio.Event()
        self.touch_event = asyncio.Event()
        # logger.info("ユーザーの応答を待機中... LOL")

        response_task = asyncio.create_task(self.response_queue.get())
        end_session_task = asyncio.create_task(self.session_end_event.wait())
        timeout_task = asyncio.create_task(asyncio.sleep(timeout))
        touch_task = asyncio.create_task(self.touch_event.wait())

        try:
            while True:
                # end_session_task = asyncio.create_task(self.session_end_event.wait())
                # touch_reset_task = asyncio.create_task(self.touch_event.wait())

                done, _ = await asyncio.wait(
                    [response_task, end_session_task, timeout_task, touch_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if end_session_task in done:
                    logger.info("セッション終了を検出。応答待機を中断。")
                    return None  # Signal to stop the session gracefully

                if response_task in done:
                    user_response = await response_task
                    return user_response.strip()
                
                if touch_task in done:
                    # logger.info("タッチが検出されました。タイマーをリセットします。")
                    self.touch_event.clear()

                    # Cancel and restart the timeout timer
                    timeout_task.cancel()
                    try:
                        await timeout_task
                    except asyncio.CancelledError:
                        pass
                    timeout_task = asyncio.create_task(asyncio.sleep(timeout))

                    # Restart touch_task too
                    touch_task = asyncio.create_task(self.touch_event.wait())

                if timeout_task in done:
                    logger.info("タイムアウトしました。")
                    return "timeout"

        finally:
            self.waiting_for_response = False
            for task in [response_task, end_session_task, timeout_task, touch_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    async def receive_message(self, message: str):
        """ユーザーからのメッセージを受信する。"""
        if self.waiting_for_response:
            await self.response_queue.put(message)
        else:
            logger.info("通常メッセージを処理中:", message)
