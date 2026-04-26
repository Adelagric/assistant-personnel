import os
import requests


BLAND_API = "https://api.bland.ai/v1"


def _headers():
    return {"authorization": os.getenv("BLAND_API_KEY", "")}


def make_phone_call(phone_number: str, task: str, max_duration: int = 5) -> dict:
    """
    Passe un appel téléphonique IA via Bland.ai.
    phone_number : format international ex: +33612345678
    task         : instructions en langage naturel pour l'IA
    max_duration : durée max en minutes
    """
    api_key = os.getenv("BLAND_API_KEY")
    if not api_key:
        return {"error": "BLAND_API_KEY manquant dans le fichier .env"}

    payload = {
        "phone_number": phone_number,
        "task": task,
        "voice": "june",
        "language": "fr",
        "model": "enhanced",
        "max_duration": max_duration,
        "record": True,
        "wait_for_greeting": True,
        "temperature": 0.5,
    }
    try:
        r = requests.post(f"{BLAND_API}/calls", headers=_headers(), json=payload, timeout=15)
        data = r.json()
        if r.status_code == 200 and data.get("status") == "success":
            return {
                "status": "appel_lancé",
                "call_id": data.get("call_id"),
                "message": f"Appel en cours vers {phone_number}. call_id : {data.get('call_id')}",
            }
        return {"error": data.get("message", str(data))}
    except Exception as e:
        return {"error": str(e)}


def get_call_status(call_id: str) -> dict:
    """Récupère le statut et la transcription d'un appel."""
    try:
        r = requests.get(f"{BLAND_API}/calls/{call_id}", headers=_headers(), timeout=15)
        data = r.json()
        return {
            "status": data.get("status"),
            "duration": data.get("call_length"),
            "transcription": data.get("transcripts", []),
            "summary": data.get("summary", ""),
            "recording_url": data.get("recording_url", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def list_recent_calls(limit: int = 5) -> list:
    """Liste les derniers appels passés."""
    try:
        r = requests.get(
            f"{BLAND_API}/calls",
            headers=_headers(),
            params={"limit": limit},
            timeout=15
        )
        calls = r.json().get("calls", [])
        return [
            {
                "call_id": c.get("c_id"),
                "to": c.get("to"),
                "status": c.get("status"),
                "duration": c.get("call_length"),
                "date": c.get("created_at"),
                "summary": c.get("summary", ""),
            }
            for c in calls
        ]
    except Exception as e:
        return [{"error": str(e)}]
