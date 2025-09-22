import os
from typing import Any, List, Tuple

from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import AIMessage, HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_openai import ChatOpenAI
from pydantic.v1 import BaseModel, Field

from src.helpers.conf_loader import MODELS_CONF
from src.helpers.env_loader import OPENAI_API_KEY


class ChatHistoryFormatter:
    """Formats chat history for OpenAI models.""" 

    @staticmethod
    def format_chat_history(chat_history: List[Tuple[str, str]]) -> List[Any]:
        buffer = []
        for human, ai in chat_history:
            buffer.append(HumanMessage(content=human))
            buffer.append(AIMessage(content=ai))
        return buffer


class OpenAIAgent:
    def __init__(self, tools: List[Any], prompt_manager=None):
        self.tools = tools
        self.prompt_manager = prompt_manager
        self.llm = self._initialize_llm()
        self.prompt = self._initialize_prompt()
        self.agent = self._initialize_agent()

    def _initialize_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            api_key=OPENAI_API_KEY,
            temperature=0,
            model=MODELS_CONF["llm"]["version"],
            streaming=True,
        ).bind(functions=[convert_to_openai_function(t) for t in self.tools])

    def _initialize_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt_manager.get_prompt("default")),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

    def _initialize_agent(self) -> Any:
        return (
            {
                "input": lambda x: x["input"],
                "chat_history": lambda x: ChatHistoryFormatter.format_chat_history(
                    x["chat_history"]
                )
                if x.get("chat_history")
                else [],
                "agent_scratchpad": lambda x: format_to_openai_function_messages(
                    x["intermediate_steps"]
                ),
            }
            | self.prompt
            | self.llm
            | OpenAIFunctionsAgentOutputParser()
        )

    def update_prompt(self, prompt_text: str):
        """Update the system prompt dynamically."""
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", prompt_text),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )
        # self._rebuild_agent()

    def update_tools(self, tools: List[Any]):
        """Update tools and rebuild the LLM + agent pipeline."""
        self.tools = tools
        self.llm = self._initialize_llm()
        self._rebuild_agent()

    def _rebuild_agent(self):
        """Rebuild the agent after updating tools or prompt."""
        self.agent = (
            {
                "input": lambda x: x["input"],
                "chat_history": lambda x: ChatHistoryFormatter.format_chat_history(
                    x["chat_history"]
                )
                if x.get("chat_history")
                else [],
                "agent_scratchpad": lambda x: format_to_openai_function_messages(
                    x["intermediate_steps"]
                ),
            }
            | self.prompt
            | self.llm
            | OpenAIFunctionsAgentOutputParser()
        )

class AgentIO(BaseModel):
    """Input and output models for agent execution."""

    input: str
    chat_history: List[Tuple[str, str]] = Field(
        ..., extra={"widget": {"type": "chat", "input": "input", "output": "output"}}
    )

class Output(BaseModel):
    output: Any

