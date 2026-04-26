import requests
import re


def search_opentable(restaurant: str, city: str, date: str,
                     time: str, guests: int = 2) -> dict:
    """
    Cherche un restaurant sur OpenTable et retourne les disponibilités + lien de réservation.
    date : format YYYY-MM-DD
    time : format HH:MM
    """
    try:
        # API de recherche OpenTable
        url = "https://www.opentable.com/dapi/fe/gql"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        query = {
            "operationName": "Autocomplete",
            "variables": {"term": f"{restaurant} {city}", "pageSize": 5},
            "query": """
            query Autocomplete($term: String!, $pageSize: Int) {
              autocomplete(term: $term, pageSize: $pageSize) {
                restaurants { rid name address { city } urlSlug }
              }
            }
            """
        }
        r = requests.post(url, json=query, headers=headers, timeout=10)
        results = r.json().get("data", {}).get("autocomplete", {}).get("restaurants", [])

        if not results:
            return {
                "found": False,
                "message": f"Aucun résultat OpenTable pour '{restaurant}' à {city}.",
                "suggestion": f"https://www.opentable.fr/s?covers={guests}&dateTime={date}T{time}&term={restaurant}+{city}"
            }

        resto = results[0]
        booking_url = (
            f"https://www.opentable.fr/r/{resto['urlSlug']}"
            f"?covers={guests}&dateTime={date}T{time}"
        )
        return {
            "found": True,
            "nom": resto["name"],
            "ville": resto.get("address", {}).get("city", city),
            "lien_reservation": booking_url,
            "rid": resto["rid"],
        }
    except Exception as e:
        return {"error": str(e)}


def search_thefork(restaurant: str, city: str, date: str,
                   time: str, guests: int = 2) -> dict:
    """Cherche sur TheFork (LaFourchette) et retourne le lien de réservation."""
    try:
        base = "https://www.thefork.fr/recherche"
        search_url = (
            f"{base}?citySlug={city.lower()}&date={date}&hour={time.replace(':', '')}"
            f"&partySize={guests}&query={requests.utils.quote(restaurant)}"
        )
        return {
            "found": True,
            "lien_recherche": search_url,
            "message": f"Recherche TheFork pour '{restaurant}' à {city} le {date} à {time} pour {guests} personnes.",
        }
    except Exception as e:
        return {"error": str(e)}


def find_business_phone(business_name: str, city: str) -> dict:
    """Cherche le numéro de téléphone d'un établissement via Pages Jaunes."""
    try:
        query = requests.utils.quote(f"{business_name} {city}")
        pj_url = f"https://www.pagesjaunes.fr/recherche/{city}/{requests.utils.quote(business_name)}"

        # Recherche via DuckDuckGo pour trouver le numéro
        from ddgs import DDGS
        results = list(DDGS().text(
            f"{business_name} {city} téléphone numéro réservation",
            max_results=3
        ))

        # Chercher un numéro de téléphone dans les résultats
        phone_pattern = re.compile(r"(?:\+33|0)[1-9](?:[\s.\-]?\d{2}){4}")
        phones_found = []
        for r in results:
            phones = phone_pattern.findall(r.get("snippet", "") + r.get("title", ""))
            phones_found.extend(phones)

        return {
            "etablissement": business_name,
            "ville": city,
            "telephones": list(set(phones_found[:3])),
            "pages_jaunes": pj_url,
            "resultats_web": [{"titre": r["title"], "url": r["href"]} for r in results[:2]],
        }
    except Exception as e:
        return {"error": str(e)}
