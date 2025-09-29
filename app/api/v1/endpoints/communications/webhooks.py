"""
Communications webhooks for Voice, SMS, and WhatsApp.
- Minimal, modern endpoints that integrate with existing Chat Flow Router and Supabase models
- Graceful fallbacks if external providers (Twilio/etc.) are not configured
"""
from __future__ import annotations

from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Response
from fastapi import status
from fastapi import HTTPException
from app.config.database import get_supabase_client
from app.api.v1.chat_flow_router import get_chat_flow_router
from app.config.settings import settings
from app.services.external.twilio_service import TwilioService
import html
import logging

router = APIRouter(prefix="/communications", tags=["Communications"])
logger = logging.getLogger(__name__)

twilio_service = TwilioService()
chat_flow_router = get_chat_flow_router()


async def _resolve_business_by_number(to_number: str, channel: str = "voice") -> Optional[str]:
    """Resolve business_id from inbound number using Supabase tables.
    1) Try phone_numbers table
    2) Fall back to businesses.custom_phone_number / custom_whatsapp_number
    """
    try:
        supabase = get_supabase_client()

        # Normalize number minimal (keep as-is; real normalization could be added)
        num = to_number.strip() if to_number else to_number

        # phone_numbers direct lookup (matches Twilio target or direct custom/virtual)
        resp = supabase.table("phone_numbers").select("*").eq("phone_number", num).execute()
        if resp.data:
            return resp.data[0].get("business_id")

        # Fallback: mapping where this number is a forwarding target (Twilio provisioned number)
        try:
            map_resp = (
                supabase
                .table("phone_numbers")
                .select("business_id, phone_number, forwarding_number, is_forwarding_target")
                .eq("forwarding_number", num)
                .execute()
            )
            if map_resp.data:
                return map_resp.data[0].get("business_id")
        except Exception:
            pass

        # businesses fallback
        if channel == "whatsapp":
            resp2 = supabase.table("businesses").select("id").eq("custom_whatsapp_number", num).execute()
        else:
            resp2 = supabase.table("businesses").select("id").eq("custom_phone_number", num).execute()
        if resp2.data:
            return str(resp2.data[0].get("id"))

    except Exception as e:
        logger.warning(f"Business resolve failed for {to_number}: {e}")
    return None


async def _get_business_name(business_id: Optional[str]) -> Optional[str]:
    if not business_id:
        return None
    try:
        supabase = get_supabase_client()
        resp = supabase.table("businesses").select("name").eq("id", business_id).execute()
        if resp.data:
            return resp.data[0].get("name")
    except Exception as e:
        logger.warning(f"Fetch business name failed: {e}")
    return None


async def _ai_reply(message: str, business_id: Optional[str]) -> str:
    """Send message through existing Chat Flow and return AI text response."""
    try:
        req: Dict[str, Any] = {
            "message": message or "Hello",
            "flow_type": "dedicated" if business_id else "global",
            "business_id": business_id,
        }
        result = await chat_flow_router.route_chat_request(req)
        return str(result.get("response", ""))
    except Exception as e:
        logger.error(f"AI processing failed: {e}")
        return "I'm having trouble right now. Please try again in a moment."


def _twiml_say(text: str, business_id: Optional[str], loop_action: Optional[str] = None) -> str:
    """Generate simple TwiML with <Say> and optional <Gather> for next turn."""
    safe = html.escape(text or "")
    gather = ""
    if loop_action:
        gather = (
            f'    <Gather input="speech dtmf" action="{html.escape(loop_action)}" '
            f'method="POST" timeout="5" speechTimeout="auto" />\n'
        )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Response>\n"
        f"    <Say voice=\"alice\">{safe}</Say>\n"
        f"{gather}"
        "</Response>"
    )


@router.post("/voice/incoming")
async def voice_incoming(request: Request) -> Response:
    """
    Inbound Voice webhook (e.g., Twilio). Starts a simple gather loop to capture speech, 
    routes to AI, and responds with TWiML.
    """
    form = await request.form()
    to_number = str(form.get("To", ""))
    business_id = await _resolve_business_by_number(to_number, channel="voice")
    business_name = await _get_business_name(business_id)

    greet = (
        f"Thanks for calling {business_name}. How may I help you today?"
        if business_name else "Thanks for calling. How may I help you today?"
    )
    action = f"{settings.API_URL}{settings.API_V1_STR}/communications/voice/process?business_id={business_id or ''}"
    twiml = _twiml_say(greet, business_id, loop_action=action)
    return Response(content=twiml, media_type="application/xml", status_code=status.HTTP_200_OK)


@router.post("/voice/process")
async def voice_process(request: Request) -> Response:
    """
    Continues the voice conversation. Expects speech transcription in provider payload.
    """
    form = await request.form()
    speech = str(form.get("SpeechResult") or form.get("TranscriptionText") or form.get("Digits") or "")
    business_id = request.query_params.get("business_id") or None

    # AI response
    reply = await _ai_reply(speech, business_id)

    # Continue loop
    action = f"{settings.API_URL}{settings.API_V1_STR}/communications/voice/process?business_id={business_id or ''}"
    twiml = _twiml_say(reply, business_id, loop_action=action)
    return Response(content=twiml, media_type="application/xml", status_code=status.HTTP_200_OK)


@router.post("/sms/incoming")
async def sms_incoming(request: Request):
    """Inbound SMS webhook. Replies with AI-generated text via provider service."""
    form = await request.form()
    from_number = str(form.get("From", ""))
    to_number = str(form.get("To", ""))
    body = str(form.get("Body", "")).strip()

    if not body:
        body = "Hello"

    business_id = await _resolve_business_by_number(to_number, channel="sms")
    reply = await _ai_reply(body, business_id)

    # Send reply (graceful no-op if provider not configured)
    try:
        await twilio_service.send_sms(to_number=from_number, message=reply, from_number=to_number)
    except Exception as e:
        logger.warning(f"SMS reply send failed (graceful): {e}")

    return {"success": True}


@router.post("/whatsapp/incoming")
async def whatsapp_incoming(request: Request):
    """Inbound WhatsApp webhook (Twilio-style). Replies with AI-generated text."""
    form = await request.form()
    from_number = str(form.get("From", "")).replace("whatsapp:", "")
    to_number = str(form.get("To", "")).replace("whatsapp:", "")
    body = str(form.get("Body", "")).strip()

    if not body:
        body = "Hello"

    business_id = await _resolve_business_by_number(to_number, channel="whatsapp")
    reply = await _ai_reply(body, business_id)

    # Send reply via WhatsApp (graceful no-op if provider not configured)
    try:
        await twilio_service.send_whatsapp_message(to_number=f"whatsapp:{from_number}", message=reply, from_number=f"whatsapp:{to_number}")
    except Exception as e:
        logger.warning(f"WhatsApp reply send failed (graceful): {e}")

    return {"success": True}
