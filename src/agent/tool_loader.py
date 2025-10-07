from typing import Any, Callable, Dict, List, Tuple

from src.tools.call_person_tool import CallPersonTool
from src.tools.delivery_tool import DeliveryTool
from src.tools.dengon_tool import DengonTool
from src.tools.information_tool import InformationTool, create_retriever
from src.tools.train_tool import ShowTrainTool
from src.tools.weather_tool import ShowWeatherTool
from src.tools.websearch_tool import WebSearchTool


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
        self.retriever = create_retriever()

        self.tool_factories: Dict[str, Callable[[], Any]] = {
            "call_person": lambda: CallPersonTool(
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
                user_profile=self.user_profile,
            ),
            "delivery": lambda: DeliveryTool(
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
                user_profile=self.user_profile,
            ),
            "dengon": lambda: DengonTool(
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
                user_profile=self.user_profile,
            ),
            "weather_info": lambda: ShowWeatherTool(
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
            ),
            "train_info": lambda: ShowTrainTool(
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
            ),
            "websearch": lambda: WebSearchTool(
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
            ),
            "information": lambda: InformationTool(
                retriever=self.retriever,
                ws_manager=self.ws_manager,
                message_manager=self.message_manager,
                session_manager=self.session_manager,
                user_profile=self.user_profile,
            ),
        }

        # Map button ID to list of tools and their default
        self.button_tool_map: Dict[str, List[str]] = {
            "button_1": ["weather_info", "websearch", "information"],
        }

        self.default_tool_map: Dict[str, str] = {
            "button_1": "information",
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
