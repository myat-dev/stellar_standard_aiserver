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
from src.helpers.availability_storage import (
    availability_responses,
    mark_message_sent,
    pop_response,
    rank_responses
)
from src.helpers.conf_loader import (
    DAILOGUE,
    DISPLAY_TXT,
    LINE_IDS,
    LINE_USER1,
    LINE_USER2,
    LINE_WAIT_TIME,
    server_config_loader,
)
from src.helpers.enums import ActionType, Mode
from src.helpers.logger import logger
from src.helpers.maps import BUTTON_USER_ID
from src.llm.intent_classifier import intent_chain
from src.message_templates.line_push_template import (
    CheckAvailablityMessage,
    ImageMessage,
    ImageWithTextMessage,
    ResponseNotiMessage
)
from src.message_templates.websocket_message_template import (
    UserProfile,
    WebsocketMessageTemplate,
)
from src.tools.base_contact_tool import BaseContactTool


class DeliveryToolInput(BaseModel):
    tool_input: str


class DeliveryTool(BaseContactTool):
    name: str = "delivery"
    description: str = "担当者と繋ぐためのツールです。"
    args_schema: Type[BaseModel] = DeliveryToolInput
    ws_manager: Optional[WebSocketManager] = None
    message_manager: Optional[WebsocketMessageTemplate] = None
    session_manager: Optional[ChatSessionManager] = None
    user_profile: Optional[UserProfile] = None
    return_direct: bool = True
    context_memory: Optional[ContextMemory] = None
    
    async def decide_contact_way(self, user_input: str, mode: str) -> str:
        if mode == Mode.FUZAI.value:
            return await self.contact_line_fuzai(mode)
        else:
            self.context_memory.conversation_state = ConversationState.CHECK_LINE_AVAILABILITY
            if mode == Mode.ZAITAKU.value:
                await self.send_action_msg(ActionType.CHOOSE_CONTACT.value)
                return await self.send_chat_msg(DAILOGUE["decide_contact_message"])
            else:
                return await self.contact_line(user_input, mode)
            
    async def contact_line_fuzai(self, mode: str) -> str:
        logger.info(f"モード: {mode}, ボタンID: {self.context_memory.button_id}")
        self.reload_memory()
        ImageWithTextMessage(LINE_USER1[0], self.context_memory.session_id, "郵便・宅急便が来ました。").send()
        return await self.handle_unavailable(DAILOGUE["unavailable_deli_message"])

    async def contact_line(self, user_input: str, mode: str) -> str:
        logger.info(f"モード: {mode}, ボタンID: {self.context_memory.button_id}")
        await self.send_action_msg(ActionType.SHOW_WAIT.value)
        await self.send_chat_msg(DAILOGUE["wait_message"])
        self.reload_memory()
        button_id = self.context_memory.button_id
        person2contact = BUTTON_USER_ID.get(button_id, [])

        line_ids = self.decide_person2contact(mode, person2contact)

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
                if waitpermission == "confirmation":
                    return await self.handle_unavailable(DAILOGUE["can_wait_2min_message"])
                else:
                    if waitpermission == "unknown":
                        await self.send_chat_msg(DAILOGUE["confirm_message_retry"])
                        continue
                    else:
                        return await self.handle_unavailable(DAILOGUE["unavailable_deli_message"])
        else:
            return await self.handle_unavailable(DAILOGUE["unavailable_deli_message"])
            

    async def check_availability(self, line_ids: str, mode: str) -> str:
        line_message = "郵便・宅急便で対面対応が必要です。対応可能性を連絡してください"
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
    
    async def handle_unavailable(self, dialogue: str) -> str:
        await self.send_action_msg(ActionType.SHOW_TOP.value)
        await self.send_action_msg(ActionType.SHOW_SORRY.value)
        self.session_manager.end_session()
        return dialogue

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
        self.context_memory.purpose = "郵便・宅急便で対面対応"
        if self.context_memory.conversation_state == ConversationState.CHECK_LINE_AVAILABILITY:
            return await self.contact_line(tool_input, mode)
        return await self.decide_contact_way(tool_input, mode)
