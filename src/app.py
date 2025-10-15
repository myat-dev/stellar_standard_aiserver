import asyncio
import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.api.webhook_api import router as webhook_router
from src.api.phone_api import router as phone_router
from src.helpers import logger
from src.helpers.conf_loader import GREET_MSG, server_config_loader, DAILOGUE
from src.helpers.enums import ActionType, MessageType, Mode
from src.helpers import system_flags
from src.helpers.website_handler import handle_phonecall_action
from src.llm.llm_manager import is_valid_japanese_phone_number
from src.message_templates.websocket_message_template import UserProfile
from src.main import (
    agent_executor,
    message_manager,
    session_manager,
    user_profile,
    ws_manager,
)

app = FastAPI()
app.include_router(webhook_router)  
app.include_router(phone_router)

app.mount(
    "/line_images",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "line_images")),
    name="line_images",
)

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
    name="static",
)

@app.get("/", response_class=HTMLResponse)
def read_root():
    html_path = Path(__file__).parent / "static" / "index.html"
    return html_path.read_text(encoding="utf-8")

@app.get("/contactlist", response_class=HTMLResponse)
def contact_list():
    html_path = Path(__file__).parent / "static" / "namelist.html"
    return html_path.read_text(encoding="utf-8")

@app.get("/phone", response_class=HTMLResponse)
def read_phone():
    html_path = Path(__file__).parent / "static" / "phone.html"
    return html_path.read_text(encoding="utf-8")

@app.on_event("shutdown")
def shutdown_event():
    logger.info("Server is shutting down!")
    session_manager.line_images_delete()
    session_manager.end_session()


@app.post("/shutdown")
def shutdown():
    import threading

    logger.info("Server is shutting down from /shutdown route!")
    session_manager.line_images_delete()
    session_manager.end_session()    

    def delayed_exit():
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=delayed_exit).start()
    return {"status": "shutting down"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint to handle chat and triggers."""
    await ws_manager.connect(websocket)
    #send current language
    await ws_manager.send_to_client(
        message_manager.action_message(ActionType.SET_LANGUAGE.value, UserProfile(name=server_config_loader.get_language()))
    )
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=60)
                
            except asyncio.TimeoutError:
                logger.info("Waiting for conection")
                if not system_flags.get_phone_call_active():
                    await ws_manager.send_to_client(
                        message_manager.action_message(ActionType.SHOW_TOP.value)
                    )
                    # if session_manager.get_context_memory().session_id:
                    #     await ws_manager.send_to_client(message_manager.chat_message("タイムアウトしました。もう一度ボタンを押してください。"))
                    #     await end_session()
                continue

            if message == "exit":
                break

            data = message_manager.parse_message(json.loads(message))
            if not(data.type == MessageType.ACTION.value and data.action_type == ActionType.TOUCH_ACTION.value):
                logger.info(f"Websocket Message received: {data.__dict__}")

            if ws_manager.waiting_for_response:
                if session_manager.get_context_memory().session_id is not None:
                    if data.type == MessageType.CHAT.value:
                        logger.info("Received chat message while waiting for response.")
                        await ws_manager.receive_message(data.message)
                        continue
                    if data.type == MessageType.ACTION.value and data.action_type == ActionType.TOUCH_ACTION.value:
                        ws_manager.notify_touch()  
                        continue

            if data.type == MessageType.CHAT.value:
                if session_manager.get_context_memory().session_id is not None:
                    if session_manager.get_context_memory().last_tool_name == "weather_info" or session_manager.get_context_memory().last_tool_name == "contact_person":
                        await ws_manager.send_to_client(
                            message_manager.action_message(ActionType.HIDE_WEBVIEW.value)
                        )
                        session_manager.get_context_memory().last_tool_name = None
                    asyncio.create_task(process_chat(data.message))
                        
            elif data.type == MessageType.ACTION.value:
                if session_manager.get_context_memory().session_id is not None or data.action_type == ActionType.START_SESSION.value or data.action_type == ActionType.PHONECALL_ACTION.value or data.action_type == ActionType.PHONEEND_ACTION.value or data.action_type == ActionType.CHECK_CURRENT_MODE.value or data.action_type == ActionType.SET_LANGUAGE.value:
                    asyncio.create_task(process_action(data.action_type, data.params))

            elif data.type == MessageType.CHAT_ACTION.value:
                if session_manager.get_context_memory().session_id is not None or data.action.action_type == ActionType.START_SESSION.value:
                    asyncio.create_task(
                        process_chat_action(
                            data.message, data.action.action_type, data.action.params
                        )
                    )

    except WebSocketDisconnect:
        await end_session()
        logger.info(f"Client disconnected")
    finally:
        if ws_manager.connected:
            await ws_manager.disconnect()


async def process_action(action_type: str, params):
    match action_type:

        case ActionType.START_SESSION.value:
            await start_new_session_and_greet()

        case ActionType.END_SESSION.value:
            ws_manager.session_end_event.set()
            await end_session()
        
        case ActionType.SET_LANGUAGE.value:
            logger.debug(f"Language selected: {params.name}")  # Debugging output
            if params.name:
                server_config_loader.update_language(params.name)

        case ActionType.INPUT_NAME.value:
            logger.debug(f"Name received: {params.name}")  # Debugging output
            if params.name:
                user_profile.name = params.name
                session_manager.get_context_memory().name = params.name
                session_manager.update_chat_history(params.name, "")

        case ActionType.INPUT_PHONE.value:
            logger.debug(f"Contact received: {params.contact}")  # Debugging output
            if params.contact:
                user_profile.contact = params.contact
                session_manager.get_context_memory().contact = params.contact
                session_manager.update_chat_history(params.contact, "")

        case ActionType.SHOW_CONFIRM_INFO.value:

            ctx = session_manager.get_context_memory()

            # Only overwrite if param is non-empty
            if params.purpose and params.purpose.strip():
                user_profile.purpose = params.purpose
                ctx.purpose = params.purpose

            if params.name and params.name.strip():
                user_profile.name = params.name
                ctx.name = params.name

            if params.contact and params.contact.strip():
                logger.debug(
                    f"validating contact: {params.contact}"
                )  # Debugging output
                if await is_valid_japanese_phone_number(params.contact):
                    user_profile.contact = params.contact
                    ctx.phone = params.contact
                    ctx.phone_correct = True
                else:
                    ctx.phone_correct = False
                    logger.error(f"ERRORFORMAT: {params.contact}")  # Debugging output
        
        case ActionType.TOUCH_ACTION.value:
            pass

        case ActionType.PHONECALL_ACTION.value:
            system_flags.set_phone_call_active(True)
            await handle_phonecall_action()

        case ActionType.PHONEEND_ACTION.value:
            system_flags.set_phone_call_active(False)
            # logger.info(f"System flag {system_flags.get_phone_call_active()}")
        
        case ActionType.CHECK_CURRENT_MODE.value:
            # アポインのある業者様ボタン用
            mode = server_config_loader.get_mode()
            logger.info(f"Current mode: {mode}")
            if mode in (Mode.ZAITAKU.value, Mode.HANZAITAKU.value):
                await ws_manager.send_to_client(
                    message_manager.chat_action_message(DAILOGUE["message_for_direct_call"], ActionType.SHOW_PHONE_PAGE.value)
                )
            else:
                await ws_manager.send_to_client(
                    message_manager.chat_action_message(DAILOGUE["reply_message_for_yoyaku_nashi"], ActionType.SHOW_TOP.value)
                )
            
        case ActionType.END_OF_TTS.value:
            if session_manager.get_context_memory().session_id is not None:
                if session_manager.get_context_memory().last_tool_name == "weather_info":
                    await ws_manager.send_to_client(
                        message_manager.action_message(ActionType.SHOW_POINT_OUT.value)
                    )

async def process_chat(user_input: str):
    """Process chat input and get agent response."""

    session_manager.update_chat_history(user_input, "")
    language_instruction = _get_language_instruction(server_config_loader.get_language()) 
    response = await agent_executor.run(
        {
            "input": f"{language_instruction}\n{user_input}",
            "chat_history": session_manager.get_chat_data()["chat_history"],
            "mode": server_config_loader.get_mode(),
        }
    )

    if not response:
        logger.info("Bot response is empty — skipping reply.")
        return

    bot_response = ""
    if isinstance(response, dict):
        bot_response = response.get("output", "") or ""
    elif response is not None:
        bot_response = getattr(response, "output", "") or ""
    else:
        logger.warning("エージェント出力はありません")

    if not bot_response:
        logger.info("Bot response is empty after parsing — skipping message.")
        return

    if bot_response == "__exit__":
        logger.info("Exiting tool early — no message sent.")
        return
    bot_response = bot_response.strip("「」")

    if session_manager.latest_input and user_input != session_manager.latest_input:
        user_input = session_manager.latest_input
    session_manager.update_chat_history(user_input, bot_response)

    await ws_manager.send_to_client(message_manager.chat_message(bot_response))
        
async def process_chat_action(message: str, action_type: str, params):

    if action_type == ActionType.START_SESSION.value:
        ws_manager.set_button_id(message)
    await process_action(action_type, params)


async def start_new_session_and_greet():
    """Start a new session, configure button, and greet user."""
    session_manager.start_new_session()
    button_id = ws_manager.get_button_id()
    session_manager.get_context_memory().button_id = button_id
    agent_executor.configure_for_button(button_id)
    agent_executor.setup(initial_prompt=True)

    greet_message = GREET_MSG[f"greet_{server_config_loader.get_language()}"]
    session_manager.update_chat_history(greet_message, "")
    await ws_manager.send_to_client(message_manager.chat_message(greet_message))


async def end_session():
    session_manager.end_session()
    await ws_manager.send_to_client(
        message_manager.action_message(ActionType.END_SESSION.value)
    )
    ws_manager.clear_button_id()
    ws_manager.waiting_for_response = False

def _get_language_instruction(current_language: str) -> str:
    """Get strong language instruction"""
    instructions = {
        'ja-JP': "【必ず日本語で回答】",
        'en-US': "【YOU MUST RESPOND IN ENGLISH】",
        'zh-CN': "【必须用中文回答】",
        'ko-KR': "【반드시 한국어로 답변】",
        'es-ES': "【DEBES RESPONDER EN ESPAÑOL】"
    }
    return instructions.get(current_language, instructions['ja-JP'])


