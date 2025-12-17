from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import logging

from app.youtube_service import (
    search_channels,
    get_channel_details,
    get_recent_videos,
    get_video_comments,
)
from app.transcript_service import get_video_transcript
from app.llm_service import analyze_with_llm
from app.cache import init_cache_db, close_cache_db
from app.config import validate_config, log_config, ENV, IS_LOCAL_ENV
# from app.logging_config import setup_logging, get_logger, log_startup_info
import json

from app.logging_config import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

# # ==========================================
# # SETUP LOGGING FIRST (before anything else)
# # ==========================================
# log_level = "DEBUG" if IS_LOCAL_ENV else "INFO"
# setup_logging(
#     app_name="search-influencers",
#     log_level=log_level,
#     log_file="/var/log/search-influencers/app.log" if not IS_LOCAL_ENV else None,
#     use_systemd=not IS_LOCAL_ENV  # Use systemd on cloud, not local
# )

# logger = get_logger(__name__)

# ----------------------
# CONFIG (hard-coded)
# ----------------------
MAX_CHANNELS = 10
MAX_VIDEOS_PER_CHANNEL = 1
MAX_COMMENTS_PER_VIDEO = 1
MIN_SUBS = 5000
MAX_SUBS = 1000000
COUNTRY_CODE = "IN"  # India

app = FastAPI(title="YouTube Influencer Finder")

# SQLite lifecycle events
@app.on_event("startup")
async def startup():
    """Initialize and validate everything on app startup"""
    logger.info("🚀 Starting application startup sequence...")
    
    # Step 1: Validate configuration
    try:
        validate_config()
        log_config()
        logger.info("✅ Configuration validation passed")
    except ValueError as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        raise
    
    # Step 2: Log environment info
    logger.info(f"📍 Running in {'LOCAL' if IS_LOCAL_ENV else 'CLOUD'} environment")
    
    # Step 3: Initialize cache database
    try:
        init_cache_db()
        logger.info("✅ Cache database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize cache database: {e}")
        raise
    
    logger.info("✅ Startup sequence completed successfully")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on app shutdown"""
    logger.info("🛑 Shutting down application...")
    try:
        close_cache_db()
        logger.info("✅ Cache database closed")
    except Exception as e:
        logger.error(f"❌ Error closing cache database: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.get("/search")
async def search_all(keyword: str = Query(..., min_length=1),
    min_subscribers: int | None = MIN_SUBS,
    max_subscribers: int | None = MAX_SUBS,
    country: str | None = COUNTRY_CODE,  # 2-letter ISO code e.g., "IN"
    page_token: str | None = None,
):
    """
    Single API endpoint performing the full influencer search pipeline with pagination support.
    """
    try:
        # 1. Search channels
        search_result = await search_channels(keyword, max_results=MAX_CHANNELS, page_token=page_token)
        discovered = search_result["items"]
        next_page_token = search_result.get("nextPageToken")
        channel_ids = [c["channel_id"] for c in discovered]

        # 2. Channel details
        details = await get_channel_details(channel_ids)

         # --------------------------------------
        # ⭐ NEW FILTERING LOGIC
        # --------------------------------------
        def passes_filters(ch):
            subs = ch.get("subscribers")
            country_code = (ch.get("country") or "").upper() if ch.get("country") else None

            # Filter by min subscribers
            if min_subscribers is not None and subs is not None:
                if subs < min_subscribers:
                    return False

            # Filter by max subscribers
            if max_subscribers is not None and subs is not None:
                if subs > max_subscribers:
                    return False

            # Filter by country
            if country is not None:
                if not country_code or country_code != country.upper():
                    return False

            return True

        # Apply filters
        filtered_channels = [ch for ch in details if passes_filters(ch)]

        print("\n==== Channel Filtering Summary ====")
        print(f"Total discovered: {len(details)}")
        print(f"After filtering: {len(filtered_channels)}")
        print("===================================\n")

        # If no channel matches filters → early return
        if not filtered_channels:
            print(f"Total details: {details}")
            return {
                "keyword": keyword,
                "message": "No channels match filters.",
                "rows": []
            }

        # --------------------------------------

        # 3. For each channel → get videos → transcripts → comments → LLM
        rows = []

        for ch in filtered_channels:
            ch_id = ch["channel_id"]
            videos = await get_recent_videos(ch_id, max_results=MAX_VIDEOS_PER_CHANNEL)
            print(f"Processing channel {ch_id} with {len(videos)} videos")
            for v in videos:
                vid = v["video_id"]

                transcript = await get_video_transcript(vid)
                if transcript:
                    print(f"Transcript for video {vid}: {transcript[:100]}...")
                comments = await get_video_comments(vid, max_results=MAX_COMMENTS_PER_VIDEO)
                print(f"Comments for video {vid}: {comments}")
                llm = await analyze_with_llm(vid, transcript, comments)
                print(f"LLM Analysis for video {vid}: {llm}")
                # clean_json_string = llm.content.replace("```json\n", "").replace("\n```", "")
                # llm_content = json.loads(clean_json_string)
                print(f"Parsed LLM content: {llm}")

                rows.append({
                    "keyword": keyword,
                    "channel_id": ch_id,
                    "channel_title": ch["title"],
                    "subscribers": ch["subscribers"],
                    "video_count": ch["video_count"],
                    "country": ch["country"],

                    "video_id": vid,
                    "video_title": v["title"],
                    "video_publishedAt": v["publishedAt"],

                    "transcript_snippet": (transcript or "")[:250],
                    "comments_count": len(comments),

                    "llm_product_mentions": llm.get("product_mentions") or [],
                    "llm_review_tone": llm.get("review_tone") or [],
                    "llm_audience_sentiment": llm.get("audience_sentiment") or [],
                    "llm_video_selling_product": llm.get("video_already_selling_product") or [],
                    "llm_affiliate_marketing": llm.get("affiliate_marketing") or [],
                })

        # Create DataFrame & print on console
        df = pd.DataFrame(rows)
        # print("\n========== DataFrame Output ==========")
        # print(df)
        # print("======================================\n")

        return {
            "keyword": keyword,
            "rows": rows,
            "nextPageToken": next_page_token,
            "total_in_batch": len(rows)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/health/cache")
async def cache_health():
    """Check cache statistics"""
    from app.cache import get_cache_stats
    stats = get_cache_stats()
    return stats

@app.post("/cache/cleanup")
async def cleanup_cache():
    """Manually trigger cache cleanup (remove expired entries)"""
    from app.cache import clear_expired_cache
    deleted = clear_expired_cache()
    return {"status": "success", "deleted_entries": deleted}

@app.post("/cache/clear/{cache_type}")
async def clear_cache(cache_type: str):
    """Clear all cache entries of a specific type (transcript or llm_analysis)"""
    from app.cache import clear_cache_by_pattern
    if cache_type not in ["transcript", "llm_analysis"]:
        raise HTTPException(status_code=400, detail="cache_type must be 'transcript' or 'llm_analysis'")
    deleted = clear_cache_by_pattern(cache_type)
    return {"status": "success", "cache_type": cache_type, "deleted_entries": deleted}
