from typing import Any, Callable, Dict, List, Tuple

from src.tools.information_tool import InformationTool
from src.tools.contact_person_tool import ContactPersonTool
from src.tools.weather_tool import ShowWeatherTool
from src.tools.websearch_tool import WebSearchTool
from src.tools.showmap_tool import ShowMapTool
from src.tools.rag_builder import build_all_retrievers

class ToolLoader:
    def __init__(
        self,
        agent_tools: Dict[str, bool],
        ws_manager=None,
        message_manager=None,
        session_manager=None,
        user_profile=None,
    ):
        self.agent_tools = agent_tools
        self.ws_manager = ws_manager
        self.message_manager = message_manager
        self.session_manager = session_manager
        self.user_profile = user_profile
        self.retrievers = build_all_retrievers()

        self.tool_factories: Dict[str, Callable[[], Any]] = {
            "weather_info": lambda: ShowWeatherTool(
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
            ), 
            "contact_person": lambda: ContactPersonTool(
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
            ),
            "websearch": lambda: WebSearchTool(
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
            ),
            "faq_tool": lambda: InformationTool(
                retriever=self.retrievers["company_faq"],
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
                user_profile=self.user_profile,
                name="faq_tool",
                description="会社やステラリンクに関するFAQ情報を取得するツール。",
            ),
            "support_tool": lambda: InformationTool(
                retriever=self.retrievers["customer_service"],
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
                user_profile=self.user_profile,
                name="support_tool",
                description="訪問者対応や顧客サポートに関する質問に答えるツール。",
            ),
            "show_map": lambda: ShowMapTool(
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
                trigger_keywords=["地図", "マップ", "アクセス", "行き方", "map", "案内図", "場所"]
            ),
        }

        # Map button ID to list of tools and their default
        self.button_tool_map: Dict[str, List[str]] = {
            "button_1": ["weather_info", "websearch", "support_tool", "contact_person", "faq_tool", "show_map"],
        }

        self.default_tool_map: Dict[str, str] = {
            "button_1": "support_tool",
        }

    def get_tools_by_keys(self, tool_keys: List[str]) -> List[Any]:
        """Load only specific tools by their keys."""
        return [
            self.tool_factories[key]()
            for key in tool_keys
            if key in self.tool_factories
        ]

    def get_tools_for_button(self, button_id: str) -> List[Any]:
        """Return a predefined toolset based on button ID."""
        selected_keys = self.button_tool_map.get(button_id, [])
        return self.get_tools_by_keys(selected_keys)

    def load_enabled_tools(self) -> List[Any]:
        """Load tools based on initial config (agent_tools)."""
        return [
            self.tool_factories[key]()
            for key, enabled in self.agent_tools.items()
            if enabled and key in self.tool_factories
        ]

    def get_default_tool_for_button(self, button_id: str) -> str:
        """Return the default tool name for the given button."""
        return self.default_tool_map.get(button_id)
