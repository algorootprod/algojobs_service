from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
import json
import os
import asyncio
from livekit import agents 
from livekit.agents.voice import AgentSession, Agent
from livekit.plugins import google, deepgram, silero, openai
from app.services.mongoDB_service import MongoService

mongo = MongoService(db_name="algojobs")

async def entrypoint(ctx: agents.JobContext):

    metadata = json.loads(ctx.job.metadata)
    prompt = metadata.get("prompt", "You are an AI assistant helping with interviews.")
    agent_id = metadata.get("agent_id", "unknown_agent")

    agent_config= mongo.get_agent_config_by_id(agent_id)

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

    agent = Agent(
        instructions=prompt,
        vad=silero.VAD.load(),
        stt=deepgram.STT(  # Whisper model
        model="nova-2-general",
        language="en",
        ),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=google.TTS(
            voice_name="en-IN-Chirp3-HD-Charon",
            language="en-IN",
            credentials_file=r"D:\livekit-meet\ciplaxalgovox-23eb479f0a6f.json"
        ),
        # tools=[query_info],
    )

    session = AgentSession()
    await session.start(
        agent=agent, 
        room=ctx.room,
        # room_input_options=room_io.RoomInputOptions(
        #     # noise_cancellation=noise_cancellation.BVC(),
        # ),
    )

    await session.generate_reply()

    #TODO: implement time warning feature

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
    
