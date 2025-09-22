import asyncio
import re
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
from src.helpers.availability_storage import (
    availability_responses,
    mark_message_sent,
    pop_response,
    rank_responses,
)
from src.helpers.conf_loader import (
    DAILOGUE,
    DISPLAY_TXT,
    LINE_USER1,
    LINE_USER2,
    LINE_WAIT_TIME,
    server_config_loader,
)
from src.helpers.enums import ActionType, Mode
from src.helpers.logger import logger
from src.helpers.maps import BUTTON_USER_ID
from src.llm.llm_manager import extract_name_purpose, extract_phone, extract_gyosha_name_purpose, is_valid_japanese_phone_number
from src.message_templates.line_push_template import (
    CallButtonMessage,
    CheckAvailablityMessage,
    ImageMessage,
    ResponseNotiMessage,
)
from src.message_templates.websocket_message_template import (
    UserProfile,
    WebsocketMessageTemplate,
)
from src.tools.base_contact_tool import BaseContactTool


class CallPersonToolInput(BaseModel):
    tool_input: str


class CallPersonTool(BaseContactTool):
    name: str = "call_person"
    description: str = "担当者と繋ぐためのツールです。"
    args_schema: Type[BaseModel] = CallPersonToolInput
    ws_manager: Optional[WebSocketManager] = None
    message_manager: Optional[WebsocketMessageTemplate] = None
    session_manager: Optional[ChatSessionManager] = None
    user_profile: Optional[UserProfile] = None
    return_direct: bool = True
    context_memory: Optional[ContextMemory] = None
    first_run: bool = True

    async def gather_info(self, user_input: str, mode: str) -> str:
        self.context_memory = self.session_manager.get_context_memory()
        if self.context_memory.button_id == "button_4":
            extracted_name, extracted_purpose = await extract_gyosha_name_purpose(user_input)
            if extracted_name and not self.context_memory.name:
                self.context_memory.name = extracted_name
            if extracted_purpose and not self.context_memory.purpose:
                self.context_memory.purpose = extracted_purpose
        else:
            if self.first_run and not self.context_memory.button_id == "button_1":
                self.set_purpose()  ## manual setting for pet button
                self.first_run = False
            # user_input = await improve_recognition(user_input)
            extracted_name, extracted_purpose = await extract_name_purpose(user_input)

            if extracted_name and not self.context_memory.name:
                self.context_memory.name = extracted_name
            if extracted_purpose and not self.context_memory.purpose:
                normalized_purpose = re.sub(r"[,\、\s　]", "", extracted_purpose)
                if "睡蓮" in normalized_purpose:
                    await self.send_chat_msg(
                        "睡蓮墓地については、メイスンワーク株式会社へお問合せください。"
                    )
                    await self.send_action_msg_with_param(ActionType.SHOW_BOCHI.value, UserProfile(purpose="睡蓮墓地については、"))
                    await self.send_action_msg(ActionType.END_SESSION.value)
                    return "__exit__"
                elif "樹木葬" in normalized_purpose:
                    await self.send_chat_msg(
                        "じゅもくそう墓地については、メイスンワーク株式会社へお問合せください。"
                    )
                    await self.send_action_msg_with_param(ActionType.SHOW_BOCHI.value, UserProfile(purpose="樹木葬墓地については、"))
                    await self.send_action_msg(ActionType.END_SESSION.value)
                    return "__exit__"
                elif "ペット供養" in normalized_purpose:
                    await self.send_action_msg(ActionType.SHOW_PET.value)
                self.context_memory.purpose = extracted_purpose

        if not self.context_memory.purpose and self.context_memory.purpose_retry < 2:
            self.context_memory.purpose_retry += 1
            return [
                DAILOGUE["ask_purpose_retry_message"],
                DAILOGUE["ask_retry_message"].format(identity="ご用件"),
            ][self.context_memory.purpose_retry - 1]

        if not self.context_memory.name and self.context_memory.name_retry < 3:
            self.context_memory.name_retry += 1
            if self.context_memory.name_retry < 3:
                if self.context_memory.button_id == "button_4":
                    return [
                    DAILOGUE["ask_company_name_message"],
                    DAILOGUE["ask_retry_message"].format(identity="会社名とお名前"),
                ][self.context_memory.name_retry - 1]
                else:
                    return [
                        DAILOGUE["ask_otakiage_message"] if not self.context_memory.purpose==None and "お焚き上げ" in self.context_memory.purpose else DAILOGUE["ask_name_message"],
                        DAILOGUE["ask_retry_message"].format(identity="お名前"),
                    ][self.context_memory.name_retry - 1]
            else:
                await self.send_action_msg(ActionType.SHOW_NAME.value)
                await self.send_action_msg(ActionType.SHOW_KEYBOARD.value)
                return DAILOGUE["ask_kb_message"]
        self.context_memory.conversation_state = ConversationState.CONFIRM_USER_INFO
        return await self.show_confirm_info("confirm user info", mode)

    async def show_confirm_info(self, user_input: str, mode:str) -> str:
        self.reload_memory()
        name = self.context_memory.name
        purpose = self.context_memory.purpose
        confirm_message = DAILOGUE["confirm_message_default"]
        if name or purpose:
            if name and purpose:
                confirm_message = DAILOGUE["confirm_message"].format(
                    name=name, purpose=purpose
                )
            elif name:
                confirm_message = DAILOGUE["confirm_message_name_only"].format(
                    name=name
                )
            else:
                confirm_message = DAILOGUE["confirm_message_purpose_only"].format(
                    purpose=purpose
                )
        while True:
            await self.send_chat_action_msg(
                confirm_message, ActionType.SHOW_CONFIRM_INFO.value, self.user_profile
            )
            user_reply = await self.ws_manager.wait_for_user_response()
            self.session_manager.update_chat_history(user_reply, "")

            if user_reply is None:
                logger.info("待ってる途中でセッション停止されました。")
                return "__exit__"

            if user_reply == "timeout":
                return await self.handle_timeout()
            
            nmpurpose_confirmed = await self.is_confirmed_correction(user_reply)
            logger.info(f"User reply: {user_reply}, Info confirmed: {nmpurpose_confirmed}")   
            if nmpurpose_confirmed == "confirmation":
                self.context_memory.conversation_state = (
                ConversationState.CHECK_LINE_AVAILABILITY
                )
                self.reload_memory()
                if mode == Mode.ZAITAKU.value or (
                    mode == Mode.HANZAITAKU.value
                    and self.context_memory.button_id == "button_1"
                ):
                    await self.send_action_msg(ActionType.CHOOSE_CONTACT.value)
                    return await self.send_chat_msg(DAILOGUE["decide_contact_message"])

                if mode in (Mode.FUZAI.value, Mode.HANZAITAKU.value):
                    return await self.contact_line(user_input, mode)
            elif nmpurpose_confirmed == "correction":
                confirm_message = DAILOGUE["correct_info_message"]
                continue
            else:
                confirm_message = DAILOGUE["confirm_message_retry"]
                continue


    async def contact_line(self, user_input: str, mode: str) -> str:
        logger.info(f"モード: {mode}, ボタンID: {self.context_memory.button_id}")
        self.reload_memory()
        button_id = self.context_memory.button_id
        person2contact = BUTTON_USER_ID.get(button_id, [])

        line_ids = self.decide_person2contact(mode, person2contact)

        if mode not in [Mode.ZAITAKU.value, Mode.HANZAITAKU.value] or not any(
            person2contact
        ):
            await self.send_confirm_action_msg(
                DISPLAY_TXT["ask_phone_text"], ActionType.SHOW_CONFRIM_YESNO.value
            )
            await self.send_chat_msg(
                DAILOGUE["unavailable_message"].format(identity="ご連絡先")
            )
            return await self.handle_unavailable()
        else:
            await self.send_action_msg(ActionType.SHOW_WAIT.value)
            await self.send_chat_msg(DAILOGUE["wait_message"])
            person_label, availability = await self.check_availability(line_ids, mode)

            if availability == "今すぐ対応する":
                await self.send_action_msg(ActionType.SHOW_TOP.value)
                self.session_manager.end_session()
                return DAILOGUE["available_message"].format(person=person_label)
            elif availability == "2分以内に対応する":
                await self.send_confirm_action_msg(
                    DISPLAY_TXT["ask_wait_text"], ActionType.SHOW_CONFRIM_YESNO.value
                )
                await self.send_chat_msg(
                    DAILOGUE["wait_2min_message"].format(person=person_label)
                )
                while True:
                    user_reply = await self.ws_manager.wait_for_user_response()
                    self.session_manager.update_chat_history(user_reply, "")
                    if user_reply is None:
                        logger.info("待ってる途中でセッション停止されました。")
                        return "__exit__"
                    if user_reply == "timeout":
                        timeout_msg = await self.handle_timeout()
                        await self.send_chat_msg(timeout_msg)
                        return "__exit__"
                    waitpermission = await self.is_confirmed_yesno(user_reply)
                    logger.info(f"User reply wait permission: {user_reply}, Permission: {waitpermission}")
                    if waitpermission == "confirmation":
                        await self.send_action_msg(ActionType.SHOW_TOP.value)
                        await self.send_action_msg(ActionType.SHOW_SORRY.value)
                        self.session_manager.end_session()
                        return DAILOGUE["can_wait_2min_message"]
                    else:
                        if waitpermission == "unknown":
                            await self.send_chat_msg(DAILOGUE["confirm_message_retry"])
                            continue
                        else:
                            await self.send_confirm_action_msg(
                                DISPLAY_TXT["ask_phone_text"],
                                ActionType.SHOW_CONFRIM_YESNO.value,
                            )
                            await self.send_chat_msg(
                                DAILOGUE["cannot_wait_2min_message"].format(
                                    identity="ご連絡先"
                                )
                            )
                            return await self.handle_unavailable()
            else:
                await self.send_confirm_action_msg(
                    DISPLAY_TXT["ask_phone_text"], ActionType.SHOW_CONFRIM_YESNO.value
                )
                await self.send_chat_msg(
                    DAILOGUE["unavailable_message"].format(identity="ご連絡先")
                )
                return await self.handle_unavailable()

    async def handle_unavailable(self):
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
            logger.info(f"User reply phone confirmed: {user_reply}, Confirmed: {phone_confirmed}")
            if phone_confirmed == "confirmation":
                self.reload_memory()
                self.context_memory.phone_retry += 1
                await self.send_action_msg(ActionType.SHOW_CONVERSATION.value)
                return DAILOGUE["ask_phone_message"]
            
            elif phone_confirmed == "unknown":
                await self.send_chat_msg(DAILOGUE["confirm_message_retry"])
                continue
            else:
                await self.send_action_msg(ActionType.SHOW_TOP.value)
                await self.send_action_msg(ActionType.SHOW_SORRY.value)

                self.context_memory.workflow_active = False
                message = (
                    DAILOGUE["sonaemono_message"]
                    if self.context_memory.button_id == "button_2"
                    else ""
                )
                self.session_manager.end_session()
                return DAILOGUE["apology_message"].format(new_line=message)

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
            confirm_message = DAILOGUE["confirm_message_phone"]
            self.reload_memory()
            await self.send_chat_action_msg(
                confirm_message, ActionType.SHOW_CONFIRM_INFO.value, self.user_profile
            )
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
                    if phonecorrection_confirmed == "confirmation" and self.context_memory.phone_correct:
                        purpose_display = f"{self.context_memory.name}様が訪問しました。ご用件は「{self.context_memory.purpose}」です。" if self.context_memory.purpose else "ご用件は未確認です。"
                        line_id = LINE_USER1[0]
                        
                        CallButtonMessage(
                            line_id,
                            self.context_memory.name,
                            self.context_memory.phone,
                            purpose_display,
                            self.get_title_text(),
                        ).send()

                        if mode == Mode.FUZAI.value:
                            ImageMessage(line_id, self.context_memory.session_id).send()

                        dialogue_key = "apology_callback_message"
                    elif phonecorrection_confirmed == "confirmation" and not self.context_memory.phone_correct:
                        dialogue_key = "end_ask_phone"
                    else:
                        dialogue_key = "apology_message"
                    await self.send_action_msg(ActionType.SHOW_TOP.value)
                    await self.send_action_msg(ActionType.SHOW_SORRY.value)
                    self.context_memory.workflow_active = False
                    message = (
                        DAILOGUE["sonaemono_message"]
                        if self.context_memory.button_id == "button_2"
                        else ""
                    )
                    self.session_manager.end_session()
                    return DAILOGUE[dialogue_key].format(new_line=message)

    async def check_availability(self, line_ids: list, mode: str) -> str:
        line_message = self.get_line_message()
        title_text = self.get_title_text()
        reply_messages = []

        for line_id in line_ids:
            CheckAvailablityMessage(line_id, line_message, title_text).send()
            ImageMessage(line_id, self.context_memory.session_id).send()
            mark_message_sent(line_id)

        for _ in range(LINE_WAIT_TIME):
            await asyncio.sleep(1)

        for i,line_id in enumerate(line_ids):
            if line_id in availability_responses: 
                response = pop_response(line_id)
                reply_messages.append(response)
                if line_id in LINE_USER1:
                    person_label = f"住職_{'Android' if LINE_USER1.index(line_id) == 0 else 'iPhone'}"
                else:
                    person_label = f"奥様" 
                message = f"{person_label}は「{response}」と返信しました。"
                for j,line_id in enumerate(line_ids):
                    if i != j:
                        ResponseNotiMessage(line_id, message).send()
                        pass
                
        if len(reply_messages) == 1:
            return "対応できるもの", reply_messages[0]
        elif len(reply_messages) > 1:
            return "対応できるもの", rank_responses(reply_messages)
        
        return "", "対応出来ない"
    
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
            return f"{name}様が「{purpose}」の為に受付に来ています。ご対応できますか？"
        elif name:
            return f"{name}様が受付に来ていますが、来訪目的を理解できませんでした。ご対応できますか？"
        elif purpose:
            return f"来訪者が「{purpose}」の為に受付に来ていますが、来訪者の名前を理解できませんでした。ご対応できますか？"
        else:
            return "来訪者が受付に来ていますが、名前と目的を理解できませんでした。ご対応できますか？"

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
        self.session_manager.context.last_tool_name = self.name
        mode = server_config_loader.get_mode()
        self.context_memory = self.session_manager.get_context_memory()
        if (
            self.context_memory.conversation_state
            == ConversationState.CONFIRM_USER_INFO
        ):
            return await self.show_confirm_info(tool_input, mode)
        if (
            self.context_memory.conversation_state
            == ConversationState.CHECK_LINE_AVAILABILITY
        ):
            return await self.contact_line(tool_input, mode)
        if (
            self.context_memory.conversation_state
            == ConversationState.GATHER_CONTACT_INFO
        ):
            return await self.gather_contact_info(tool_input, mode)

        return await self.gather_info(tool_input, mode)
