from typing import Optional, Type, Union

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools import BaseTool
from langchain_community.utilities import SerpAPIWrapper
from pydantic.v1 import BaseModel

from src.agent.session_manager import ChatSessionManager
from src.api.websocket_manager import WebSocketManager
from src.helpers.env_loader import SERP_API_KEY
from src.message_templates.websocket_message_template import WebsocketMessageTemplate


class WebSearchToolInput(BaseModel):
    tool_input: str


class WebSearchTool(BaseTool):
    name: str = "websearch"
    description: str = (
        "Useful for retrieving real-time information from the internet, such as current news and time, and general search queries. "
        "It should not be used for harmful or unethical purposes."
    )
    args_schema: Type[BaseModel] = WebSearchToolInput
    ws_manager: Optional[WebSocketManager] = None
    message_manager: Optional[WebsocketMessageTemplate] = None
    session_manager: Optional[ChatSessionManager] = None
    return_direct: bool = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._serpAPI = SerpAPIWrapper(serpapi_api_key=SERP_API_KEY)

    async def websearch(self, user_input: str) -> str:
        return self._serpAPI.run(user_input)
        
    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self.websearch(tool_input)

    async def _arun(
        self,
        tool_input: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        self.session_manager.context.last_tool_name = self.name
        return await self.websearch(tool_input)
