import requests


def get_weather(city: str = "Paris") -> dict:
    try:
        resp = requests.get(
            f"https://wttr.in/{city}",
            params={"format": "j1", "lang": "fr"},
            timeout=10,
        )
        data = resp.json()
        current = data["current_condition"][0]
        desc = (
            current["lang_fr"][0]["value"]
            if current.get("lang_fr")
            else current["weatherDesc"][0]["value"]
        )
        area = data["nearest_area"][0]
        today = data["weather"][0]
        return {
            "ville": f"{area['areaName'][0]['value']}, {area['country'][0]['value']}",
            "condition": desc,
            "temperature": f"{current['temp_C']}°C (ressenti {current['FeelsLikeC']}°C)",
            "humidite": f"{current['humidity']}%",
            "vent": f"{current['windspeedKmph']} km/h",
            "min_max_jour": f"{today['mintempC']}°C — {today['maxtempC']}°C",
        }
    except Exception as e:
        return {"erreur": str(e)}
