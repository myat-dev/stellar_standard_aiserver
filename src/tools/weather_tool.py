from typing import Optional, Type, Union

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools import BaseTool
from pydantic.v1 import BaseModel

from src.api.websocket_manager import WebSocketManager
from src.agent.session_manager import ChatSessionManager
from src.helpers.enums import ActionType
from src.message_templates.websocket_message_template import WebsocketMessageTemplate


class ShowWeatherToolInput(BaseModel):
    pass


class ShowWeatherTool(BaseTool):
    name: str = "weather_info"
    description: str = "天気についての話しの時に役に立つツール"
    args_schema: Type[BaseModel] = ShowWeatherToolInput
    ws_manager: Optional[WebSocketManager] = None
    message_manager: Optional[WebsocketMessageTemplate] = None
    session_manager: Optional[ChatSessionManager] = None
    return_direct: bool = True

    async def show_weather_info(self):
        action_message = self.message_manager.action_message(
            ActionType.SHOW_WEATHER.value
        )
        await self.ws_manager.send_to_client(action_message)
        return "天気予報はこちらの画面からご覧ください。"

    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self.show_weather_info()

    async def _arun(
        self,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        self.session_manager.context.last_tool_name = self.name
        return await self.show_weather_info()
