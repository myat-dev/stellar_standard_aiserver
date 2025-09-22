import re
from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse, Response
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import Dial, VoiceResponse
from src.helpers.env_loader import TWILIO_CALLER_ID, TWILIO_ACCOUNT_SID, TWILIO_TWIML_APP_SID, TWILIO_API_KEY, TWILIO_API_SECRET 

router = APIRouter()

@router.get("/token")
async def twilio_voice_token():
    identity = "ai_avatar" 

    # Create access token with credentials
    token = AccessToken(TWILIO_ACCOUNT_SID, TWILIO_API_KEY, TWILIO_API_SECRET, identity=identity)
    # Create a Voice grant and add to token
    voice_grant = VoiceGrant(
        outgoing_application_sid=TWILIO_TWIML_APP_SID,
        incoming_allow=True,
    )
    token.add_grant(voice_grant)

    token = token.to_jwt()

    return JSONResponse(content={"identity": identity, "token": token.decode() if isinstance(token, bytes) else token})


@router.post("/voice")
async def voice(To: str = Form(None)):
    resp = VoiceResponse()
    if To == TWILIO_CALLER_ID:
        dial = Dial()
        dial.client("ai_avatar")
        resp.append(dial)
    elif To:
        dial = Dial(caller_id=TWILIO_CALLER_ID)
        phone_pattern = re.compile(r"^[\d\+\-\(\) ]+$")
        if phone_pattern.match(To):
            dial.number(To)
        else:
            dial.client(To)
        resp.append(dial)
    else:
        resp.say("Thanks for calling!")

    return Response(content=str(resp), media_type="text/xml")