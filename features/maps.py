"""
Maps & trajets via OpenStreetMap — 100% gratuit, sans clé API.
- Nominatim pour le geocoding (adresse → lat/lon)
- OSRM pour le routing (temps de trajet, itinéraire)
"""
import requests
import time


_USER_AGENT = "AssistantPersonnel/1.0 (github.com/open-source-project)"
_last_nominatim_call = 0.0


def _rate_limit_nominatim():
    """Nominatim demande max 1 req/sec."""
    global _last_nominatim_call
    elapsed = time.time() - _last_nominatim_call
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _last_nominatim_call = time.time()


def geocode(address: str) -> dict:
    """Convertit une adresse en coordonnées lat/lon via Nominatim."""
    try:
        _rate_limit_nominatim()
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1, "addressdetails": 1},
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        results = resp.json()
        if not results:
            return {"error": f"Adresse introuvable : {address}"}
        r = results[0]
        return {
            "address": r.get("display_name", address),
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "type": r.get("type", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def travel_time(origin: str, destination: str, mode: str = "driving") -> dict:
    """
    Calcule le temps de trajet entre deux adresses.
    mode : driving | walking | cycling
    """
    try:
        orig = geocode(origin)
        if "error" in orig:
            return {"error": f"Origine : {orig['error']}"}
        dest = geocode(destination)
        if "error" in dest:
            return {"error": f"Destination : {dest['error']}"}

        profile = {"driving": "car", "walking": "foot", "cycling": "bike"}.get(mode, "car")
        url = (
            f"https://router.project-osrm.org/route/v1/{profile}/"
            f"{orig['lon']},{orig['lat']};{dest['lon']},{dest['lat']}"
            "?overview=false"
        )
        resp = requests.get(url, timeout=15)
        data = resp.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            return {"error": "Itinéraire introuvable."}

        route = data["routes"][0]
        duration_sec = route["duration"]
        distance_m = route["distance"]
        hours = int(duration_sec // 3600)
        minutes = int((duration_sec % 3600) // 60)
        duration_str = f"{hours}h{minutes:02d}" if hours else f"{minutes} min"

        return {
            "origin": orig["address"],
            "destination": dest["address"],
            "mode": mode,
            "distance_km": round(distance_m / 1000, 1),
            "duration": duration_str,
            "duration_minutes": int(duration_sec // 60),
        }
    except Exception as e:
        return {"error": str(e)}


def get_directions(origin: str, destination: str, mode: str = "driving") -> dict:
    """
    Itinéraire détaillé avec étapes (turn-by-turn).
    mode : driving | walking | cycling
    """
    try:
        orig = geocode(origin)
        if "error" in orig:
            return {"error": f"Origine : {orig['error']}"}
        dest = geocode(destination)
        if "error" in dest:
            return {"error": f"Destination : {dest['error']}"}

        profile = {"driving": "car", "walking": "foot", "cycling": "bike"}.get(mode, "car")
        url = (
            f"https://router.project-osrm.org/route/v1/{profile}/"
            f"{orig['lon']},{orig['lat']};{dest['lon']},{dest['lat']}"
            "?steps=true&overview=false"
        )
        resp = requests.get(url, timeout=15)
        data = resp.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            return {"error": "Itinéraire introuvable."}

        route = data["routes"][0]
        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                maneuver = step.get("maneuver", {})
                name = step.get("name", "")
                dist_m = step.get("distance", 0)
                instr = maneuver.get("type", "")
                modifier = maneuver.get("modifier", "")
                desc = f"{instr}"
                if modifier:
                    desc += f" {modifier}"
                if name:
                    desc += f" sur {name}"
                desc += f" ({int(dist_m)}m)"
                steps.append(desc)

        duration_sec = route["duration"]
        distance_m = route["distance"]
        minutes = int(duration_sec // 60)

        return {
            "origin": orig["address"],
            "destination": dest["address"],
            "mode": mode,
            "distance_km": round(distance_m / 1000, 1),
            "duration_minutes": minutes,
            "steps": steps[:20],  # limiter à 20 étapes
            "map_link": f"https://www.openstreetmap.org/directions?from={orig['lat']},{orig['lon']}&to={dest['lat']},{dest['lon']}",
        }
    except Exception as e:
        return {"error": str(e)}


def should_leave_by(destination: str, arrival_time_iso: str, origin: str = None,
                    mode: str = "driving", buffer_minutes: int = 10) -> dict:
    """
    Calcule l'heure à laquelle partir pour arriver à l'heure à un RDV.
    origin : si None, on prend la ville mémorisée de l'utilisateur.
    """
    from datetime import datetime, timedelta
    if not origin:
        return {"error": "Origine manquante (précise ton adresse de départ)."}
    try:
        result = travel_time(origin, destination, mode)
        if "error" in result:
            return result
        arrival = datetime.fromisoformat(arrival_time_iso.replace("Z", "+00:00"))
        departure = arrival - timedelta(minutes=result["duration_minutes"] + buffer_minutes)
        return {
            "leave_at": departure.strftime("%Y-%m-%d %H:%M"),
            "travel_time": result["duration"],
            "distance_km": result["distance_km"],
            "buffer_minutes": buffer_minutes,
            "mode": mode,
        }
    except Exception as e:
        return {"error": str(e)}
