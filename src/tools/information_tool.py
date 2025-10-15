from typing import Optional, Type, Any
from pydantic.v1 import BaseModel, Field
from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.tools import BaseTool

from src.helpers.enums import ActionType
from src.api.websocket_manager import WebSocketManager
from src.agent.session_manager import ChatSessionManager
from src.message_templates.websocket_message_template import (
    UserProfile,
    WebsocketMessageTemplate,
)
from src.helpers.conf_loader import DAILOGUE


class InformationInput(BaseModel):
    """Schema for InformationTool input."""
    question: str = Field(description="ユーザーからの質問内容。")


class InformationTool(BaseTool):
    """Generic RAG-based tool for retrieving knowledge from a specific dataset."""
    name: str = "information_tool"
    description: str = "知識ベース（FAQやサポート情報など）から情報を検索し、回答するためのツール。"
    args_schema: Type[BaseModel] = InformationInput

    retriever: Optional[Any] = None
    ws_manager: Optional[WebSocketManager] = None
    message_manager: Optional[WebsocketMessageTemplate] = None
    session_manager: Optional[ChatSessionManager] = None
    user_profile: Optional[UserProfile] = None
    return_direct: bool = False

    # ----------- Main sync execution -----------
    def _run(
        self,
        question: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Synchronously retrieve and return relevant information."""
        if not self.retriever:
            return "RAG Retrieverが設定されていません。"

        try:
            results = self.retriever.invoke(question)
        except Exception as e:
            print(f"[RAG Error] {e}")
            return DAILOGUE.get("rag_fallback_message", "情報を取得できませんでした。")

        if not results:
            return DAILOGUE.get("rag_fallback_message", "関連する情報が見つかりませんでした。")

        # Combine multiple retrieved answers
        combined_answer = self._format_results(results)
        return combined_answer

    # ----------- Async version -----------
    async def _arun(
        self,
        question: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Asynchronous retrieval version."""
        if not self.retriever:
            return "RAG Retrieverが設定されていません。"

        self.session_manager.context.last_tool_name = self.name

        try:
            results = await self.retriever.ainvoke(question)
        except Exception as e:
            print(f"[RAG Async Error] {e}")
            return DAILOGUE.get("rag_fallback_message", "情報を取得できませんでした。")

        if not results:
            return DAILOGUE.get("rag_fallback_message", "関連する情報が見つかりませんでした。")

        combined_answer = self._format_results(results)
        return combined_answer

    # ----------- Helper -----------
    def _format_results(self, results: list) -> str:
        """Combine retrieved documents into a readable text."""
        contents = []
        for doc in results:
            text = doc.page_content.strip()
            # Extract only the "Answer:" part if it exists
            if "Answer:" in text:
                text = text.split("Answer:", 1)[1].strip()
            contents.append(text)

        # Remove duplicates & join neatly
        unique_answers = list(dict.fromkeys(contents))
        formatted = "\n\n".join(unique_answers)
        return formatted or DAILOGUE.get("rag_fallback_message", "関連する情報が見つかりませんでした。")
