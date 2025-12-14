from fastapi import APIRouter
from app.youtube_service import get_youtube_service, search_channels
from app.transcript_service import fetch_transcript
from app.cache import get_cached, set_cached

router = APIRouter(prefix="/influencers", tags=["Influencers"])

@router.get("/search")
async def influencer_search(q: str):
    cache_key = f"search:{q}"
    cached = await get_cached(cache_key)
    if cached:
        return {"cached": True, "results": cached}

    service = await get_youtube_service(access_token=None)  # or pass token
    results = await search_channels(query=q, service=service)

    await set_cached(cache_key, results)
    return {"cached": False, "results": results}

@router.get("/transcript/{video_id}")
async def get_transcript(video_id: str):
    cache_key = f"transcript:{video_id}"
    cached = await get_cached(cache_key)
    if cached:
        return {"cached": True, "transcript": cached}

    transcript = await fetch_transcript(video_id)
    await set_cached(cache_key, transcript)
    return {"cached": False, "transcript": transcript}
