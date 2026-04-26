from ddgs import DDGS


def search_web(query: str, max_results: int = 5) -> list:
    try:
        results = list(DDGS().text(query, max_results=max_results))
        return [
            {"title": r["title"], "url": r["href"], "snippet": r["body"]}
            for r in results
        ]
    except Exception as e:
        return [{"error": str(e)}]
