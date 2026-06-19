from duckduckgo_search import DDGS

def fetch_latest_news(ticker: str, industry: str = None) -> str:
    """
    Scrapes the latest news and industry trends using DuckDuckGo.
    """
    ticker = ticker.upper().strip()
    query = f"{ticker} stock latest market news"
    if industry:
        query += f" OR \"{industry}\" industry market trends news"
        
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=6))
            
        if not results:
            return "No recent news headlines or industry updates found."
            
        news_entries = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No Title")
            href = r.get("href", "#")
            body = r.get("body", "No content description available.")
            news_entries.append(
                f"[{i}] {title}\n"
                f"URL: {href}\n"
                f"Summary: {body}\n"
            )
        return "\n".join(news_entries)
    except Exception as e:
        return f"Failed to retrieve news due to: {str(e)}"
