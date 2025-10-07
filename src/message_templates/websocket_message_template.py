import json
from src.helpers.logger import logger
from src.helpers.enums import MessageType


class ChatMessage:
    def __init__(self, message: str):
        self.type = MessageType.CHAT.value
        self.message = message

    def to_json(self) -> str:
        return json.dumps(self.__dict__)
    
    def __str__(self):
        return f"ChatMessage(type='{self.type}', message='{self.message}')"

    def __repr__(self):
        return self.__str__()


class UserProfile:
    def __init__(self, name: str = None, contact: str = None, purpose: str = None):
        self.name = name
        self.contact = contact
        self.purpose = purpose

    def to_dict(self) -> dict:
        """Convert UserProfile to a dictionary, replacing None with empty strings."""
        return {
            "name": self.name or "",
            "contact": self.contact or "",
            "purpose": self.purpose or "",
        }

    def to_json(self) -> str:
        """Convert UserProfile to JSON."""
        return json.dumps(self.to_dict())
    
    def __str__(self):
        """Return a human-readable string when printing the object."""
        return f"UserProfile(name='{self.name}', contact='{self.contact}', purpose='{self.purpose}')"

    def __repr__(self):
        """Return the official string representation."""
        return self.__str__()


class ActionMessage:
    def __init__(self, action_type: str, params: UserProfile):
        self.type = MessageType.ACTION.value
        self.action_type = action_type
        self.params = params or UserProfile()

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.type,
                "action_type": self.action_type,
                "params": self.params.to_dict(),
            }
        )
    
    def __str__(self):
        return f"ActionMessage(type='{self.type}', action_type='{self.action_type}', params={self.params})"

    def __repr__(self):
        return self.__str__()


class ChatActionMessage:
    def __init__(self, message: str, action_type: str, params: UserProfile):
        self.type = MessageType.CHAT_ACTION.value
        self.message = message
        self.action = ActionMessage(action_type, params)

    def to_json(self) -> str:
        # print(self.action.params.to_dict())
        return json.dumps(
            {
                "type": self.type,
                "message": self.message,
                "action": {
                    "action_type": self.action.action_type,
                    "params": self.action.params.to_dict(),
                },
            }
        )

    def __str__(self):
        return f"ChatActionMessage(type='{self.type}', message='{self.message}', action={self.action})"

    def __repr__(self):
        return self.__str__()
    
class URLActionMessage:
    def __init__(self, url: str, action_type: str, params: UserProfile):
        self.type = MessageType.URL_ACTION.value
        self.url = url
        self.action = ActionMessage(action_type, params)

    def to_json(self) -> str:
        # print(self.action.params.to_dict())
        return json.dumps(
            {
                "type": self.type,
                "message": self.url,
                "action": {
                    "action_type": self.action.action_type,
                    "params": self.action.params.to_dict(),
                },
            }
        )

    def __str__(self):
        return f"URLActionMessage(type='{self.type}', url='{self.url}', action={self.action})"

    def __repr__(self):
        return self.__str__()
    
class ConfirmActionMessage:
    def __init__(self, message: str, action_type: str, params: UserProfile):
        self.type = MessageType.CONFIRM_ACTION.value
        self.message = message
        self.action = ActionMessage(action_type, params)

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.type,
                "message": self.message,
                "action": {
                    "action_type": self.action.action_type,
                    "params": self.action.params.to_dict(),
                },
            }
        )

    def __str__(self):
        return f"ConfirmActionMessage(type='{self.type}', message='{self.message}', action={self.action})"

    def __repr__(self):
        return self.__str__()


class WebsocketMessageTemplate:
    def __init__(self):
        pass

    def chat_message(self, message: str) -> ChatMessage:
        """Create a chat message."""
        return ChatMessage(message)

    def action_message(
        self, action_type: str, params: UserProfile = None
    ) -> ActionMessage:
        """Create an action message."""
        return ActionMessage(action_type, params)

    def chat_action_message(
        self, message: str, action_type: str, params: UserProfile = None
    ) -> ChatActionMessage:
        """Create a chat action message."""
        return ChatActionMessage(message, action_type, params)

    def url_action_message(
        self, url: str, action_type: str, params: UserProfile = None
    ) -> URLActionMessage:
        """Create a URL action message."""
        return URLActionMessage(url, action_type, params)
    
    def confirm_action_message(
        self, message: str, action_type: str, params: UserProfile = None
    ) -> ConfirmActionMessage:
        """Create a chat action message."""
        return ConfirmActionMessage(message, action_type, params)

    def contact_param(
        self, name: str = None, contact: str = None, purpose: str = None
    ) -> UserProfile:
        """Create a UserProfile object with optional params."""
        return UserProfile(name, contact, purpose)

    def parse_message(self, message: dict):
        """Parse incoming message and return the appropriate object."""
        message_type = message.get("type")

        if message_type == MessageType.CHAT.value:
            return ChatMessage(message.get("message"))

        elif message_type == MessageType.ACTION.value:
            action_type = message.get("action_type")
            params_data = message.get("params", {})

            # Ensure params is a dictionary, not an object reference
            if isinstance(
                params_data, UserProfile
            ):  # Check if incorrectly parsed as object
                params_data = params_data.to_dict()

            params = UserProfile(
                params_data.get("name"),
                params_data.get("contact"),
                params_data.get("purpose"),
            )
            return ActionMessage(action_type, params)

        elif message_type == MessageType.CHAT_ACTION.value:
            chat_text = message.get("message")
            action_data = message.get("action", {})
            action_type = action_data.get("action_type")
            params_data = action_data.get("params", {})

            if isinstance(params_data, UserProfile):
                params_data = params_data.to_dict()

            params = UserProfile(
                params_data.get("name"),
                params_data.get("contact"),
                params_data.get("purpose"),
            )

            return ChatActionMessage(chat_text, action_type, params)

        else:
            raise ValueError(f"Unknown message type: {message_type}")
