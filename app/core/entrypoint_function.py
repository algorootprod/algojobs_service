
from app.core.single_agent import SingleAgent
from app.helpers.agent_builder import build_llm_instance, build_stt_instance, build_tts_instance
from app.schemas import AgentConfig ,Agent
from datetime import datetime
import json
import os
from livekit import agents 
from livekit.agents.voice import AgentSession
from app.services.mongoDB_service import MongoService

mongo = MongoService(db_name="algojobs")

async def entrypoint(ctx: agents.JobContext):

    metadata = json.loads(ctx.job.metadata)
    prompt = metadata.get("prompt", "You are an AI assistant helping with interviews.")
    agent_id = metadata.get("agent_id", "unknown_agent")

    agent_doc= mongo.get_agent_config_by_id(agent_id)
    agent_doc = Agent.model_validate(agent_doc)
    agent_config = getattr(agent_doc, "agentConfig", None)
    agent_config = AgentConfig.model_validate(agent_config).model_dump()

    llm = build_llm_instance(agent_config.llm.provider, agent_config.llm.model, agent_config.llm.api_key, agent_config.llm.temperature)
    stt = build_stt_instance(agent_config.stt.provider, agent_config.stt.model, agent_config.stt.language, agent_config.stt.api_key)
    tts = build_tts_instance(agent_config.tts.provider, agent_config.tts.model, agent_config.tts.sample_rate, agent_config.tts.language,
                                credentials_info=agent_config.tts.api_key)

    async def write_transcript():
        current_date = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Ensure directory exists
        save_dir = "transcriptions"   # relative to project root
        os.makedirs(save_dir, exist_ok=True)

        filename = os.path.join(save_dir, f"transcript_{ctx.room.name}_{current_date}.json")

        with open(filename, 'w') as f:
            json.dump(session.history.to_dict(), f, indent=2)

        print(f"Transcript for {ctx.room.name} saved to {filename}")
        # result = evaluate_candidate(session.history.to_dict(),evaluation_template=evaluation_template,jd_text=jd,resume_text=resume ,save_dir="evaluations")
        # print("Evaluation Result:")
        # print("-" * 20)
        # print(json.dumps(result, indent=2))

    ctx.add_shutdown_callback(write_transcript)
    await ctx.connect()

    session = AgentSession(stt=stt, llm=llm, tts=tts, vad=ctx.proc.userdata["vad"])

    agent = SingleAgent(prompt=prompt)

    await session.start(
        agent=agent, 
        room=ctx.room,
        # room_input_options=room_io.RoomInputOptions(
        #     # noise_cancellation=noise_cancellation.BVC(),
        # ),
    )

    await session.generate_reply()

    # TODO: implement time warning feature

    # async def _time_warning():
    #     try:
    #         await asyncio.sleep(40)  # wait 1 minute
    #         # Try to prompt participants to wrap up. This attempts to let the agent speak a reminder.
    #         try:
    #             print("Time warning: please wrap up — time is limited.")
    #             # await session.generate_reply(
    #             #     instructions="Time is running out, please conclude soon."
    #             #     )  # generate a normal reply (agent will speak)
    #             # asyncio.sleep(2)  # brief pause
    #             await session.say("Time is running out, please conclude soon.")  # direct TTS
    #         except TypeError:
    #             # If generate_reply requires context and fails, log and fallback to printing
    #             print("Time warning: please wrap up — time is limited.")
    #         except Exception as e:
    #             print("Failed to generate time warning via agent:", e)
    #             print("Time warning: please wrap up — time is limited.")
    #     except asyncio.CancelledError:
    #         return

    # # start background timer that will prompt after 1 minute
    # _warning_task = asyncio.create_task(_time_warning())

    # # ensure the warning task is cancelled on shutdown
    # async def _cancel_warning():
    #     # request cancellation
    #     _warning_task.cancel()
    #     # await it so cancellation completes and exceptions are handled
    #     try:
    #         await _warning_task
    #     except asyncio.CancelledError:
    #         # expected; swallow
    #         pass
    # ctx.add_shutdown_callback(_cancel_warning)
    # continue normal flow
    
