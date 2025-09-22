import asyncio
from typing import Optional, Type

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from pydantic.v1 import BaseModel

from src.agent.context_variables import ContextMemory
from src.agent.conversation_state import ConversationState
from src.agent.session_manager import ChatSessionManager
from src.api.websocket_manager import WebSocketManager
from src.helpers.conf_loader import (
    DAILOGUE,
    DISPLAY_TXT,
    LINE_USER1,
    server_config_loader,
)
from src.helpers.enums import ActionType, Mode
from src.helpers.logger import logger
from src.helpers.maps import BUTTON_USER_ID
from src.llm.llm_manager import extract_gyosha_name_purpose, extract_phone, is_valid_japanese_phone_number
from src.message_templates.line_push_template import (
    CallButtonMessage,
    SendOnlyMessage,
    ImageMessage,
)
from src.message_templates.websocket_message_template import (
    UserProfile,
    WebsocketMessageTemplate,
)
from src.tools.base_contact_tool import BaseContactTool


class DengonToolInput(BaseModel):
    tool_input: str


class DengonTool(BaseContactTool):
    name: str = "dengon"
    description: str = "住職に伝言を残すツールです。"
    args_schema: Type[BaseModel] = DengonToolInput
    ws_manager: Optional[WebSocketManager] = None
    message_manager: Optional[WebsocketMessageTemplate] = None
    session_manager: Optional[ChatSessionManager] = None
    user_profile: Optional[UserProfile] = None
    return_direct: bool = True
    context_memory: Optional[ContextMemory] = None
    first_run: bool = True

    async def gather_info(self, user_input: str, mode: str) -> str:
        self.context_memory = self.session_manager.get_context_memory()

        extracted_name, extracted_purpose = await extract_gyosha_name_purpose(user_input)
        if not self.context_memory.purpose:
            extracted_purpose = user_input
            self.context_memory.purpose = extracted_purpose
        if extracted_name and not self.context_memory.name:
            self.context_memory.name = extracted_name

        if not self.context_memory.name and self.context_memory.name_retry < 3:
            self.context_memory.name_retry += 1
            if self.context_memory.name_retry < 3:
                return [
                    DAILOGUE["ask_name_message"],
                    DAILOGUE["ask_retry_message"].format(identity="お名前"),
                ][self.context_memory.name_retry - 1]
            else:
                await self.send_action_msg(ActionType.SHOW_NAME.value)
                await self.send_action_msg(ActionType.SHOW_KEYBOARD.value)
                return DAILOGUE["ask_kb_message"]

        await self.send_confirm_action_msg(
            DISPLAY_TXT["ask_need_callback_text"], ActionType.SHOW_CONFRIM_YESNO.value
        )
        await self.send_chat_msg(DAILOGUE["confirm_need_callback_text"])
        return await self.check_need_callback()

    async def check_need_callback(self):
        self.context_memory.conversation_state = ConversationState.GATHER_CONTACT_INFO

        while True:
            user_reply = await self.ws_manager.wait_for_user_response()
            self.session_manager.update_chat_history(user_reply, "")
            if user_reply is None:
                logger.info("待ってる途中でセッション停止されました。")
                return "__exit__"
            if user_reply == "timeout":
                return await self.handle_timeout()
            phone_confirmed = await self.is_confirmed_yesno(user_reply)
            if phone_confirmed == "confirmation":
                self.reload_memory()
                self.context_memory.phone_retry += 1
                await self.send_action_msg(ActionType.SHOW_CONVERSATION.value)
                return DAILOGUE["ask_phone_message"]
            elif phone_confirmed == "unknown":
                await self.send_chat_msg(DAILOGUE["confirm_message_retry"])
                continue
            else:
                self.context_memory.conversation_state = ConversationState.CONFIRM_USER_INFO
                return await self.show_confirm_info("confirm user info")

    async def gather_contact_info(self, user_input: str, mode: str) -> str:

        self.reload_memory()
        if not self.context_memory.phone and self.context_memory.phone_retry <= 3:
            extracted_phone = await extract_phone(user_input)

            if extracted_phone and extracted_phone != "wrongformat":
                self.context_memory.phone = extracted_phone
                # 音声対応の為、バリデーションフラグ立てる
                self.context_memory.phone_correct = True
                self.reload_memory()

            elif extracted_phone == "wrongformat":
                self.context_memory.phone_retry += 1
                await self.send_action_msg(ActionType.SHOW_PHONE.value)
                await self.send_action_msg(ActionType.SHOW_NUM_KEYBOARD.value)
                return DAILOGUE["ask_phone_kb_message"]

            else:
                self.context_memory.phone_retry += 1
                await self.send_action_msg(ActionType.SHOW_PHONE.value)
                await self.send_action_msg(ActionType.SHOW_NUM_KEYBOARD.value)

                if self.context_memory.phone_retry == 2:
                    return DAILOGUE["ask_kb_message"]
                else:
                    return DAILOGUE["ask_correct_phone_message"]

        if self.context_memory.phone_retry > 3 and self.context_memory.phone is None:
            self.context_memory.workflow_active = False
            await self.send_action_msg(ActionType.SHOW_TOP.value)
            self.session_manager.end_session()
            return DAILOGUE["end_ask_phone"]

        # --- All info collected ---
        if self.context_memory.phone:
            confirm_message = DAILOGUE["confirm_message_dengon"].format(
                name=self.context_memory.name,
            )
            self.reload_memory()
            await self.send_chat_action_msg(
                "", ActionType.SHOW_CONFIRM_FOR_DENGON.value, self.user_profile
            )
            await self.send_chat_msg(confirm_message)

            while True:
                user_reply = await self.ws_manager.wait_for_user_response()
                self.session_manager.update_chat_history(user_reply, "")
                if user_reply is None:
                    logger.info("待ってる途中でセッション停止されました。")
                    return "__exit__"
                if user_reply == "timeout":
                    return await self.handle_timeout(end_message=DAILOGUE["end_ask_phone"])

                phonecorrection_confirmed = await self.is_confirmed_correction(user_reply)
                if phonecorrection_confirmed == "confirmation":
                    self.reload_memory()
                else:
                    None

                if phonecorrection_confirmed == "unknown":
                    await self.send_chat_msg(DAILOGUE["confirm_message_retry"])
                    continue
                elif phonecorrection_confirmed == "correction":
                    await self.send_chat_msg(DAILOGUE["correct_info_message"])
                    continue
                else:
                    line_message = self.get_line_message()
                    line_id = LINE_USER1[0] 
                    if phonecorrection_confirmed == "confirmation" and self.context_memory.phone_correct:                        
                        
                        CallButtonMessage(
                            line_id,
                            self.context_memory.name,
                            self.context_memory.phone,
                            line_message,
                            self.get_title_text(),
                        ).send()
                        ImageMessage(line_id, self.context_memory.session_id).send()
                        dialogue_key = "dengon_message"                    
                    else:
                        SendOnlyMessage(line_id, line_message, self.get_title_text()).send()
                        ImageMessage(line_id, self.context_memory.session_id).send()
                        dialogue_key = "end_ask_phone_dengon"
                    await self.send_action_msg(ActionType.SHOW_TOP.value)
                    self.context_memory.workflow_active = False
                    self.session_manager.end_session()
                    return DAILOGUE[dialogue_key]

    async def show_confirm_info(self, user_input: str) -> str:
        self.reload_memory()
        name = self.context_memory.name
        purpose = self.context_memory.purpose
        confirm_message = DAILOGUE["confirm_message_default"]
        if name or purpose:
            if name and purpose:
                confirm_message = DAILOGUE["confirm_message_dengon"].format(name=name)
            elif name:
                confirm_message = DAILOGUE["confirm_message_name_only"].format(name=name)
            else:
                confirm_message = DAILOGUE["confirm_message_dengon"].format(name=name)
        
        await self.send_chat_action_msg(
            "", ActionType.SHOW_CONFIRM_FOR_DENGON.value, self.user_profile
        )
        await self.send_chat_msg(confirm_message)
        return await self.send_dengon()

    async def send_dengon(self) -> str:
        while True:
            user_reply = await self.ws_manager.wait_for_user_response()
            self.session_manager.update_chat_history(user_reply, "")
            if user_reply is None:
                logger.info("待ってる途中でセッション停止されました。")
                return "__exit__"
            if user_reply == "timeout":
                return await self.handle_timeout()
            info_confirmed = await self.is_confirmed_correction(user_reply)
            logger.info(f"User reply: {user_reply}, Info confirmed: {info_confirmed}")
            if info_confirmed == "confirmation":
                line_message = self.get_line_message()
                title_text = self.get_title_text()
                line_id = LINE_USER1[0] 
                SendOnlyMessage(line_id, line_message, title_text).send()
                ImageMessage(line_id, self.context_memory.session_id).send()

                await self.send_action_msg(ActionType.SHOW_TOP.value)
                self.context_memory.workflow_active = False
                self.session_manager.end_session()
                return DAILOGUE["dengon_message"]
            elif info_confirmed == "correction":
                await self.send_chat_msg(DAILOGUE["correct_info_message"])
                continue
            else:
                await self.send_chat_msg(DAILOGUE["confirm_message_retry"])
                continue

    def get_line_message(self) -> str:
        self.reload_memory()
        name = self.context_memory.name
        purpose = self.context_memory.purpose
        return self.__line_dailogue(name, purpose)

    async def send_chat_action_msg(
        self, message: str, action: ActionType, param: object = None
    ):
        self.session_manager.update_chat_history("", message)
        confirm_message = self.message_manager.chat_action_message(
            message, action, param
        )
        await self.ws_manager.send_to_client(confirm_message)

    def __line_dailogue(self, name: str, purpose: str):
        if name and purpose:
            return f"{name}様が伝言を残しました。伝言内容は「{purpose}」 です。"
        elif purpose:
            return f"来訪者が伝言を残しました。伝言内容は「{purpose}」です。"
        else:
            return "来訪者が伝言を残したと思いますが、伝言内容は未確認です。"

    def _run(
        self, tool_input: str, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        mode = server_config_loader.get_mode()
        return self.gather_info(tool_input, mode)  # type: ignore

    async def _arun(
        self,
        tool_input: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        mode = server_config_loader.get_mode()
        self.context_memory = self.session_manager.get_context_memory()
        if self.context_memory.conversation_state == ConversationState.GATHER_CONTACT_INFO:
            return await self.gather_contact_info(tool_input, mode)
        if self.context_memory.conversation_state == ConversationState.CONFIRM_USER_INFO:
            return await self.show_confirm_info(tool_input)        
        return await self.gather_info(tool_input, mode)
