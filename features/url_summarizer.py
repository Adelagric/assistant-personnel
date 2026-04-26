"""Scraping et résumé de liens / articles."""
import re
import requests


def extract_article_text(url: str) -> dict:
    """Extrait le contenu texte principal d'une URL."""
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        html = resp.text

        # Essayer avec BeautifulSoup si disponible
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Supprimer scripts, styles, nav, footer
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            # Chercher le contenu principal
            article = soup.find("article") or soup.find("main") or soup.find("body")
            title = soup.find("title")
            title_text = title.get_text(strip=True) if title else ""

            text = article.get_text(separator="\n", strip=True) if article else ""
        except ImportError:
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s{2,}", " ", text).strip()
            title_text = ""
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            if title_match:
                title_text = title_match.group(1).strip()

        return {
            "title": title_text,
            "text": text[:8000],
            "url": url,
            "length": len(text),
        }
    except Exception as e:
        return {"error": str(e), "url": url}
