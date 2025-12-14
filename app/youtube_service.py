import os
from typing import List, Dict, Any
from googleapiclient.discovery import build
from fastapi.concurrency import run_in_threadpool
from app.config import GOOGLE_API_KEY


def _client():
    return build("youtube", "v3", developerKey=GOOGLE_API_KEY, static_discovery=False)


# -----------------------------------------
# 1. Search channels
# -----------------------------------------
async def search_channels(keyword: str, max_results: int = 5, page_token: str | None = None):
    def _call():
        yt = _client()
        req = yt.search().list(
            q=keyword, type="channel",
            part="snippet",
            maxResults=max_results,
            pageToken=page_token
        )
        return req.execute()

    resp = await run_in_threadpool(_call)

    items = []
    for it in resp.get("items", [])[:max_results]:
        snip = it["snippet"]
        channel_id = snip.get("channelId") or it.get("id", {}).get("channelId")

        items.append({
            "channel_id": channel_id,
            "title": snip.get("title"),
            "description": snip.get("description", "")[:300],
        })

    return {
        "items": items,
        "nextPageToken": resp.get("nextPageToken"),
        "prevPageToken": resp.get("prevPageToken")
    }


# -----------------------------------------
# 2. Get channel details
# -----------------------------------------
async def get_channel_details(channel_ids: List[str]) -> List[Dict[str, Any]]:
    if not channel_ids:
        return []

    def _call(ids):
        yt = _client()
        req = yt.channels().list(
            part="snippet,statistics",
            id=",".join(ids)
        )
        return req.execute()

    resp = await run_in_threadpool(_call, channel_ids)

    out = []
    for it in resp.get("items", []):
        snip = it["snippet"]
        stats = it["statistics"]

        out.append({
            "channel_id": it["id"],
            "title": snip.get("title"),
            "country": snip.get("country"),
            "subscribers": int(stats["subscriberCount"]) if not stats.get("hiddenSubscriberCount") else None,
            "video_count": int(stats["videoCount"]),
        })

    return out


# -----------------------------------------
# 3. Get recent videos
# -----------------------------------------
async def get_recent_videos(channel_id: str, max_results: int = 5):
    def _call():
        yt = _client()
        req = yt.search().list(
            channelId=channel_id,
            order="date",
            part="snippet",
            maxResults=max_results
        )
        return req.execute()

    resp = await run_in_threadpool(_call)

    out = []
    for it in resp.get("items", [])[:max_results]:  #TBD: since we are slicing with max_results, we should sort first here.
        if it["id"]["kind"] != "youtube#video":
            continue

        out.append({
            "video_id": it["id"]["videoId"],
            "title": it["snippet"]["title"],
            "publishedAt": it["snippet"]["publishedAt"],
        })

    return out


# -----------------------------------------
# 4. Get comments
# -----------------------------------------
async def get_video_comments(video_id: str, max_results: int = 10):
    def _call():
        yt = _client()
        req = yt.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results,
            textFormat="plainText"
        )
        return req.execute()

    try:
        resp = await run_in_threadpool(_call)
    except:
        return []

    comments = []
    for it in resp.get("items", [])[:max_results]:
        try:
            comments.append(it["snippet"]["topLevelComment"]["snippet"]["textDisplay"])
        except:
            pass

    return comments
