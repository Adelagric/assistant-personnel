import feedparser

RSS_FEEDS = {
    "france": "https://www.lemonde.fr/rss/une.xml",
    "international": "https://www.lemonde.fr/international/rss_full.xml",
    "tech": "https://www.lemonde.fr/pixels/rss_full.xml",
    "economie": "https://www.lemonde.fr/economie/rss_full.xml",
    "sport": "https://www.lemonde.fr/sport/rss_full.xml",
    "politique": "https://www.lemonde.fr/politique/rss_full.xml",
}


def get_news(topic: str = "france", max_results: int = 5) -> list:
    url = RSS_FEEDS.get(topic.lower(), RSS_FEEDS["france"])
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_results]:
        items.append({
            "titre": entry.title,
            "resume": entry.get("summary", "")[:300],
            "date": entry.get("published", ""),
        })
    return items
