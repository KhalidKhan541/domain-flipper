from __future__ import annotations

import logging
import re
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
TWITTER_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class SocialSearcher:
    def __init__(self, twitter_bearer_token: Optional[str] = None) -> None:
        self.twitter_bearer_token = twitter_bearer_token

    async def search_all(self, domain_name: str, niche: str, keywords: list[str]) -> dict[str, Any]:
        results: dict[str, Any] = {
            "reddit": [],
            "twitter": [],
            "hackernews": [],
            "total": 0,
        }

        reddit = await self._search_reddit(keywords)
        results["reddit"] = reddit

        twitter = await self._search_twitter(keywords)
        results["twitter"] = twitter

        hn = await self._search_hackernews(keywords)
        results["hackernews"] = hn

        results["total"] = len(reddit) + len(twitter) + len(hn)
        return results

    async def _search_reddit(self, keywords: list[str]) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []
        query = " ".join(keywords[:3])

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                params = {
                    "q": f"{query} domain OR buying OR looking for",
                    "sort": "relevance",
                    "t": "month",
                    "limit": 10,
                }
                headers = {"User-Agent": USER_AGENT}
                async with session.get(REDDIT_SEARCH_URL, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        logger.warning("Reddit search returned %d", resp.status)
                        return signals

                    data = await resp.json()
                    posts = data.get("data", {}).get("children", [])

                    for post in posts:
                        pdata = post.get("data", {})
                        title = pdata.get("title", "")
                        selftext = pdata.get("selftext", "")
                        combined = f"{title} {selftext}".lower()

                        if any(kw.lower() in combined for kw in keywords) or "domain" in combined:
                            signals.append({
                                "platform": "reddit",
                                "title": title,
                                "url": f"https://reddit.com{pdata.get('permalink', '')}",
                                "author": pdata.get("author", ""),
                                "score": pdata.get("score", 0),
                                "snippet": selftext[:200] if selftext else "",
                                "posted": pdata.get("created_utc", 0),
                            })

        except Exception as exc:
            logger.error("Reddit search failed: %s", exc)

        return signals

    async def _search_twitter(self, keywords: list[str]) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []

        if not self.twitter_bearer_token:
            logger.debug("Twitter bearer token not configured — skipping Twitter search")
            return signals

        query = " OR ".join(f'"{kw}"' for kw in keywords[:3]) + " domain OR buying OR looking"
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {"Authorization": f"Bearer {self.twitter_bearer_token}"}
                params = {
                    "query": f"({query}) -is:retweet lang:en",
                    "max_results": 10,
                    "tweet.fields": "created_at,public_metrics,author_id",
                }
                async with session.get(TWITTER_SEARCH_URL, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        logger.warning("Twitter search returned %d", resp.status)
                        return signals

                    data = await resp.json()
                    tweets = data.get("data", [])

                    for tweet in tweets:
                        metrics = tweet.get("public_metrics", {})
                        signals.append({
                            "platform": "twitter",
                            "text": tweet.get("text", ""),
                            "url": f"https://twitter.com/i/status/{tweet.get('id', '')}",
                            "author_id": tweet.get("author_id", ""),
                            "likes": metrics.get("like_count", 0),
                            "retweets": metrics.get("retweet_count", 0),
                            "posted": tweet.get("created_at", ""),
                        })

        except Exception as exc:
            logger.error("Twitter search failed: %s", exc)

        return signals

    async def _search_hackernews(self, keywords: list[str]) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []
        query = " ".join(keywords[:3])

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                params = {
                    "query": f"{query} domain OR buy OR looking for",
                    "tags": "story",
                    "hitsPerPage": 10,
                }
                async with session.get(HN_SEARCH_URL, params=params) as resp:
                    if resp.status != 200:
                        logger.warning("HN search returned %d", resp.status)
                        return signals

                    data = await resp.json()
                    hits = data.get("hits", [])

                    for hit in hits:
                        title = hit.get("title", "")
                        points = hit.get("points", 0)
                        num_comments = hit.get("num_comments", 0)

                        if points >= 5 or num_comments >= 3:
                            signals.append({
                                "platform": "hackernews",
                                "title": title,
                                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                                "points": points,
                                "comments": num_comments,
                                "author": hit.get("author", ""),
                                "posted": hit.get("created_at_i", 0),
                            })

        except Exception as exc:
            logger.error("HN search failed: %s", exc)

        return signals

    def extract_intent_signals(self, social_results: dict[str, Any]) -> list[str]:
        signals: list[str] = []

        for post in social_results.get("reddit", []):
            title_lower = post.get("title", "").lower()
            snippet_lower = post.get("snippet", "").lower()
            combined = f"{title_lower} {snippet_lower}"

            if any(kw in combined for kw in ["looking for", "want to buy", "seeking", "need a", "searching for"]):
                signals.append(f"Reddit post looking for domain: {post.get('title', '')[:80]}")

        for tweet in social_results.get("twitter", []):
            text_lower = tweet.get("text", "").lower()
            if any(kw in text_lower for kw in ["looking for", "want to buy", "need a domain", "anyone have"]):
                signals.append(f"Twitter post expressing domain interest: {tweet.get('text', '')[:80]}")

        for story in social_results.get("hackernews", []):
            title_lower = story.get("title", "").lower()
            if any(kw in title_lower for kw in ["looking for", "want to buy", "domain", "acquiring"]):
                signals.append(f"HN discussion about domain: {story.get('title', '')[:80]}")

        return signals
