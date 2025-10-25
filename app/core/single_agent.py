import logging
from typing import Optional, List
from livekit.agents.voice import Agent
from livekit.agents.llm import function_tool
from livekit.agents import ModelSettings, llm, FunctionTool, Agent
from typing import AsyncIterable
from app.helpers.call_control import hangup
from app.helpers.preprocessor import preprocess_text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SingleAgent")

class SingleAgent(Agent):
    def __init__(
        self,
        prompt: str,
    ):
        # tools=None
        super().__init__(
            instructions=prompt,
            # tools=tools,
        )

    async def on_enter(self):
        await self.session.generate_reply()

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list[FunctionTool],
        model_settings: ModelSettings
    ) -> AsyncIterable[llm.ChatChunk]:
        async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
            if chunk.delta and chunk.delta.content:
               chunk.delta.content = preprocess_text(chunk.delta.content)
            yield chunk

    @function_tool()
    async def end_call(self) -> None:
        """Use this tool to end the call"""
        await self.session.generate_reply()
        current_speech = self.session.current_speech
        if current_speech:
            await current_speech.wait_for_playout()
        await hangup(reason="Agent ended the call")
