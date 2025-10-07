from typing import Any, Dict, List

from langchain.agents import AgentExecutor

from src.agent.agent import AgentIO, OpenAIAgent, Output
from src.agent.tool_loader import ToolLoader
from src.helpers.conf_loader import AGENT_TOOLS, MODELS_CONF
from src.helpers.logger import logger
class AgentManager:
    """Manages the agent execution and setup."""

    def __init__(
        self,
        ws_manager=None,
        message_manager=None,
        session_manager=None,
        user_profile=None,
        prompt_manager=None,
    ):
        self.tool_loader = ToolLoader(
            AGENT_TOOLS,
            ws_manager=ws_manager,
            message_manager=message_manager,
            session_manager=session_manager,
            user_profile=user_profile,
        )

        # Load default tools and setup
        tools = self.tool_loader.load_enabled_tools()
        self.agent = OpenAIAgent(tools, prompt_manager)
        self.executor = self._initialize_executor(tools)
        self.prompt_manager = prompt_manager
        self.default_tool = None
        self.session_manager = session_manager
        self.session_context = session_manager.get_context_memory()
        self.prompts = ""
        self.default_prompt = ""
        self.tools = []
        self.workflow_cleanup_done = False

    def _initialize_executor(self, tools: List[Any]) -> AgentExecutor:
        return AgentExecutor(
            agent=self.agent.agent,
            tools=tools,
            verbose=MODELS_CONF["llm"]["agent_thinking_visible"],
        ).with_types(input_type=AgentIO, output_type=Output)

    async def greet(self, input_data: Dict[str, Any]) -> Output:
        result = await self.executor.ainvoke(input_data, force_tool=False)
        return result

    async def run_with_lock_tool(self, input_data: Dict[str, Any]) -> Output:
        if self.session_context.button_id != "button_1":
            # Phase 1: If locked, force run call_person
            if self.session_context.workflow_active:
                return await self._run_locked_tool(self.default_tool, input_data)

            # # Update the prompt and tools
            if not self.session_context.workflow_active and not self.workflow_cleanup_done:
                self.setup(initial_prompt=False) 
                self.workflow_cleanup_done = True
            # Phase 2: Normal agent flow (let LLM choose)
            result = await self.executor.ainvoke(input_data, force_tool=True)
        else:
            
            if self.session_context.workflow_active and self.session_context.last_tool_name == "call_person":
                # If workflow is active, run the last tool
                return await self._run_locked_tool(self.session_context.last_tool_name, input_data)
            
            result = await self.executor.ainvoke(input_data, force_tool=True)

        return result

    async def run(self, input_data: Dict[str, Any]) -> Output:
        return await self.executor.ainvoke(input_data, force_tool=True)

    async def _run_locked_tool(
        self, tool_name: str, input_data: Dict[str, Any]
    ) -> Output:
        # Find the matching tool
        tool = next((t for t in self.executor.tools if t.name == tool_name), None)
        if not tool:
            return Output(output=f"話したい内容はボタンを押して話してください。")

        # output = await tool.arun(tool_input=input_data)
        user_input = input_data.get("input", "")
        output = await tool.arun(tool_input=user_input)

        if output == "__exit__":
            logger.warning("ツールプロセス停止されました。")
            # self.session_manager.end_session()
            self.session_context.workflow_active = False
            return Output(output="")
        return Output(output=output)

    def _get_last_tool_name(self, result: Output) -> str:
        # Extract last tool used from intermediate_steps (if available)
        steps = getattr(result, "intermediate_steps", [])
        if steps:
            last_step = steps[-1]
            tool_name = getattr(last_step[0], "tool", None)
            return tool_name
        return ""

    def configure_for_button(self, button_id: str):
        """Configure prompt and tools based on the button ID."""
        # Define prompts per button
        # prompt_map = {
        #     button_id: self.prompt_manager.get_prompt(prompt_key)
        #     for button_id, prompt_key in BUTTON_PROMPT_MAP.items()
        # }

        # self.prompts = prompt_map.get(button_id, self.prompt_manager.get_prompt("default"))
        self.default_prompt = self.prompt_manager.get_prompt("default")
        self.tools = self.tool_loader.get_tools_for_button(button_id)
        self.default_tool = self.tool_loader.get_default_tool_for_button(button_id)

    def setup(self, initial_prompt: bool):
        if initial_prompt:
            # self.agent.update_prompt(self.prompts)
            # self.agent.update_tools(self.tools)
            self.executor = self._initialize_executor(self.tools)
        else:
            self.session_manager.clear_history()
            self.session_manager.update_chat_history(f"{self.session_context.name}です。{self.session_context.purpose}の為来訪しています。", "何かお手伝えることがあったら教えてください。天気予報と京王線の時刻表を見せることができます。")
            self.agent.update_prompt(self.default_prompt)
            self.__remove_tool()

    def __remove_tool(self):
        self.tools = [t for t in self.tools if t.name != self.default_tool]
        self.agent.update_tools(self.tools)
        self.executor = self._initialize_executor(self.tools)

