from typing import Optional, Type, Union

from ddgs import DDGS
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools import BaseTool
from pydantic.v1 import BaseModel

from src.agent.session_manager import ChatSessionManager
from src.api.websocket_manager import WebSocketManager
from src.helpers.enums import ActionType
from src.llm.llm_manager import generate_search_query
from src.message_templates.websocket_message_template import WebsocketMessageTemplate


class WebSearchToolInput(BaseModel):
    tool_input: str


class WebSearchTool(BaseTool):
    name: str = "websearch"
    description: str = (
        "Useful to search from internet when you need to answer questions about current events or to find more recent information."
    )
    args_schema: Type[BaseModel] = WebSearchToolInput
    ws_manager: Optional[WebSocketManager] = None
    message_manager: Optional[WebsocketMessageTemplate] = None
    session_manager: Optional[ChatSessionManager] = None
    return_direct: bool = False

    async def websearch(self, user_input: str) -> str:
        search_query = await generate_search_query(user_input)
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(search_query, max_results=5):
                results.append(f"{r['title']}: {r['href']}")

        # Return results as a single string (you can also format as JSON if needed)
        return "\n".join(results) if results else "No results found."

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
