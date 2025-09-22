from src.agent.agent_manager import AgentManager
from src.agent.prompt_manager import PromptManager
from src.agent.session_manager import ChatSessionManager
from src.api.websocket_manager import WebSocketManager
from src.message_templates.websocket_message_template import WebsocketMessageTemplate

# Initialize managers
session_manager = ChatSessionManager()
ws_manager = WebSocketManager()
message_manager = WebsocketMessageTemplate()
user_profile = message_manager.contact_param()

prompt_manager = PromptManager()
agent_executor = AgentManager(
    ws_manager, message_manager, session_manager, user_profile, prompt_manager
)
