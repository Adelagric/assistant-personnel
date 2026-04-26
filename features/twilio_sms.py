"""Envoi de SMS via Twilio."""
import os


def send_sms(to: str, body: str) -> dict:
    """Envoie un SMS via Twilio."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    if not all([account_sid, auth_token, from_number]):
        return {"error": "Configuration Twilio manquante (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER)"}

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to,
        )
        return {
            "status": "envoyé",
            "sid": message.sid,
            "to": to,
        }
    except ImportError:
        return {"error": "Le package 'twilio' n'est pas installé. Exécute : pip install twilio"}
    except Exception as e:
        return {"error": str(e)}


def send_whatsapp(to: str, body: str) -> dict:
    """Envoie un message WhatsApp via Twilio."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    whatsapp_from = os.getenv("TWILIO_WHATSAPP_NUMBER", "")

    if not all([account_sid, auth_token, whatsapp_from]):
        return {"error": "Configuration Twilio WhatsApp manquante"}

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body,
            from_=f"whatsapp:{whatsapp_from}",
            to=f"whatsapp:{to}",
        )
        return {
            "status": "envoyé",
            "sid": message.sid,
            "to": to,
        }
    except ImportError:
        return {"error": "Le package 'twilio' n'est pas installé. Exécute : pip install twilio"}
    except Exception as e:
        return {"error": str(e)}
