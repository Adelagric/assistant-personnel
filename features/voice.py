import os
import tempfile


def transcribe_voice(audio_bytes: bytes, suffix: str = ".ogg") -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "OPENAI_API_KEY manquant pour la transcription vocale."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="fr",
                )
            return transcript.text
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        return f"Erreur transcription : {str(e)}"


def extract_pdf_text(file_bytes: bytes) -> str:
    try:
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text[:8000]
    except Exception as e:
        return f"Erreur lecture PDF : {str(e)}"
