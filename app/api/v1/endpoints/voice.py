"""
Updated voice endpoints to handle multiple providers and forwarding.
"""
from typing import Optional
from app.models import Business, PhoneNumber
from fastapi import APIRouter, Request, Form, Depends
from sqlalchemy.orm import Session
from app.config.database import get_db
from app.services.ai.voice_handler import VoiceHandler
from app.services.ai.universalbot.universal_bot import UniversalBot
from app.services.phone.providers.multi_provider_manager import MultiProviderPhoneManager
import logging
import uuid

# Optional Twilio TwiML import with safe fallbacks
try:
    from twilio.twiml.voice_response import VoiceResponse as _TwilioVoiceResponse, Gather as _TwilioGather  # type: ignore
    _TWIML_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    _TwilioVoiceResponse = None  # type: ignore
    _TwilioGather = None  # type: ignore
    _TWIML_AVAILABLE = False


if not _TWIML_AVAILABLE:
    class VoiceResponse:  # minimal fallback
        def __init__(self) -> None:
            self._parts = []

        def say(self, text: str, voice: Optional[str] = None) -> None:
            voice_attr = f' voice="{voice}"' if voice else ""
            self._parts.append(f"<Say{voice_attr}>{text}</Say>")

        def append(self, element: object) -> None:
            self._parts.append(str(element))

        def redirect(self, url: str) -> None:
            self._parts.append(f"<Redirect>{url}</Redirect>")

        def __str__(self) -> str:  # noqa: D401
            return "<Response>" + "".join(self._parts) + "</Response>"

    class Gather:  # minimal fallback
        def __init__(
            self,
            input: str = "speech",
            timeout: int = 5,
            language: str = "en-US",
            action: Optional[str] = None,
            method: str = "POST",
        ) -> None:
            attrs = [
                f'input="{input}"',
                f'timeout="{timeout}"',
                f'language="{language}"',
            ]
            if action:
                attrs.append(f'action="{action}"')
            if method:
                attrs.append(f'method="{method}"')
            self._rendered = f"<Gather {' '.join(attrs)} />"

        def __str__(self) -> str:
            return self._rendered
else:
    # Use real Twilio TwiML classes
    VoiceResponse = _TwilioVoiceResponse  # type: ignore
    Gather = _TwilioGather  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/incoming")
async def handle_incoming_call(
    request: Request,
    From: str = Form(...),
    To: str = Form(...),
    CallSid: str = Form(...),
    ForwardedFrom: Optional[str] = Form(None),  # For forwarded calls
    SipHeader_X_Extension: Optional[str] = Form(None),  # Extension code
    db: Session = Depends(get_db)
):
    """Handle incoming voice call from any provider."""

    # Check for extension code (forwarded calls)
    extension = SipHeader_X_Extension or request.headers.get("X-Extension")

    # Route the call
    phone_manager = MultiProviderPhoneManager(db)
    business_id = await phone_manager.route_incoming_call(
        to_number=To,
        from_number=From,
        extension=extension
    )

    # Generate session ID for this call
    session_id = str(uuid.uuid4())
    
    # If specific business found, load their context
    if business_id:
        logger.info(f"Routed call to business {business_id}")
        # Load business-specific greeting
        business = db.query(Business).filter(Business.id == business_id).first()
        if business:
            greeting = f"Welcome to {business.name}. How can I help you today?"
        else:
            greeting = "Welcome. How can I help you today?"
    else:
        # Universal number - needs café selection
        greeting = "Welcome to X-SevenAI! I can help you order food or make reservations. Which café would you like to connect to?"

    # Generate the TwiML response with speech gathering
    response = VoiceResponse()
    response.say(greeting, voice="Polly.Joanna")
    
    # Gather speech input for conversation
    gather = Gather(
        input="speech",
        timeout=5,
        language="en-US",
        action=f"/api/v1/voice/process?session_id={session_id}&business_id={business_id or 'universal'}",
        method="POST"
    )
    response.append(gather)
    
    # If no input, repeat the greeting
    response.say("I didn't catch that. Please try again.")
    response.redirect(f"/api/v1/voice/incoming?session_id={session_id}")
    
    return str(response)


@router.post("/process")
async def process_voice_input(
    request: Request,
    SpeechResult: Optional[str] = Form(None),
    session_id: str = Form(...),
    business_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Process voice input and continue conversation."""
    
    # Handle case where no speech was detected
    if not SpeechResult:
        response = VoiceResponse()
        response.say("I didn't catch that. Please try again.")
        response.redirect(f"/api/v1/voice/incoming?session_id={session_id}")
        return str(response)
    
    logger.info(f"Processing voice input: {SpeechResult} for session {session_id}")
    
    # Initialize UniversalBot for conversation
    universal_bot = UniversalBot(db)
    
    # Process the message through the universal bot
    bot_response = await universal_bot.process_message(
        session_id=session_id,
        message=SpeechResult,
        channel="voice",
        phone_number=request.form().get("From"),
        language="en"
    )
    
    # Get the response message
    response_message = bot_response.get("message", "I'm sorry, I didn't understand that.")
    
    # Generate TwiML response
    response = VoiceResponse()
    response.say(response_message, voice="Polly.Joanna")
    
    # Continue gathering input for ongoing conversation
    gather = Gather(
        input="speech",
        timeout=5,
        language="en-US",
        action=f"/api/v1/voice/process?session_id={session_id}&business_id={business_id or 'universal'}",
        method="POST"
    )
    response.append(gather)
    
    # If no input, ask if they need anything else
    response.say("Is there anything else I can help you with?")
    response.redirect(f"/api/v1/voice/incoming?session_id={session_id}")
    
    return str(response)


@router.post("/forward")
async def handle_forwarding_request(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle call forwarding setup requests."""

    # This endpoint handles the forwarding logic
    # when a café's existing number forwards to us

    data = await request.form()
    extension = data.get("Digits")  # Extension entered by system

    if extension:
        # Verify extension and route to business
        phone_manager = MultiProviderPhoneManager(db)

        # Find business by extension
        phone_record = db.query(PhoneNumber).filter(
            PhoneNumber.metadata["extension_code"].astext == extension
        ).first()

        if phone_record:
            # Route to business bot
            return f"""
            <Response>
                <Say>Connecting to {phone_record.business.name}</Say>
                <Redirect>/api/v1/voice/business/{phone_record.business.id}</Redirect>
            </Response>
            """

    # Extension not found
    return """
    <Response>
        <Say>Invalid extension code. Please check your setup.</Say>
        <Hangup/>
    </Response>
    """