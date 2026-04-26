"""Surveillance de pages web / prix — polling périodique + détection de changements."""
import hashlib
import requests


def fetch_page_text(url: str, css_selector: str = None) -> dict:
    """Récupère le contenu texte d'une page web. Optionnellement filtre par sélecteur CSS."""
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        html = resp.text

        if css_selector:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                elements = soup.select(css_selector)
                text = "\n".join(el.get_text(strip=True) for el in elements)
            except ImportError:
                import re
                text = re.sub(r"<[^>]+>", " ", html)
                text = re.sub(r"\s{2,}", " ", text).strip()
        else:
            import re
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s{2,}", " ", text).strip()

        text = text[:5000]
        content_hash = hashlib.md5(text.encode()).hexdigest()
        return {"text": text, "hash": content_hash, "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}


def compare_snapshots(old_text: str, new_text: str) -> str:
    """Retourne un résumé des différences entre deux snapshots."""
    if old_text == new_text:
        return ""
    # Trouver les lignes ajoutées/supprimées
    old_lines = set(old_text.split("\n"))
    new_lines = set(new_text.split("\n"))
    added = new_lines - old_lines
    removed = old_lines - new_lines
    parts = []
    if added:
        parts.append(f"Ajouté : {' | '.join(list(added)[:5])}")
    if removed:
        parts.append(f"Supprimé : {' | '.join(list(removed)[:5])}")
    return "\n".join(parts)[:1000]
