"""
Transcript Service - Hybrid Strategy for Fetching Video Transcripts

Strategy:
1. Check cache first (fastest)
2. Try YouTube Data API (official, works everywhere including cloud)
3. If API fails, try youtube-transcript-api on LOCAL only
4. Return None if all methods fail (don't cache errors)

Environment detection:
- LOCAL: Uses youtube-transcript-api as fallback
- CLOUD (AWS Lightsail, etc): Only uses YouTube Data API
"""

import logging
from typing import Optional
from fastapi.concurrency import run_in_threadpool
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from app.cache import get_cached, set_cached, generate_cache_key
from app.youtube_captions_service import get_transcript_via_youtube_api, test_youtube_api_access
from app.config import ENV, IS_LOCAL_ENV, SUPADATA_API_KEY, SUPADATA_API_BASE_URL, SUPADATA_TIMEOUT
import time
import random
import requests
import json

# Configure logging
logger = logging.getLogger(__name__)

# Rate limiting configuration
MIN_DELAY_BETWEEN_REQUESTS = 2  # Minimum 2 seconds between requests
MAX_DELAY_BETWEEN_REQUESTS = 5  # Maximum 5 seconds between requests
LAST_REQUEST_TIME = 0
YOUTUBE_API_ACCESSIBLE = None  # Will be determined on first call


async def get_video_transcript(video_id: str) -> Optional[str]:
    """
    Get video transcript using hybrid strategy with intelligent fallback
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Transcript text (string) or None if not available
        
    Strategy:
        1. Cache HIT -> return immediately
        2. Try YouTube Data API (official, most reliable)
        3. Try supadata.ai API (if API key available)
        4. Try youtube-transcript-api on LOCAL only (blocks on cloud)
        5. Return None if all fail (don't cache errors)
    """
    logger.info(f"🎬 Starting transcript fetch for video {video_id}")
    
    # ==========================================
    # STEP 1: CHECK CACHE
    # ==========================================
    cache_key = generate_cache_key(video_id, "transcript")
    cached_transcript = get_cached(cache_key)
    
    if cached_transcript is not None:
        logger.info(f"✅ CACHE HIT: Retrieved transcript for {video_id} from cache")
        return cached_transcript.get('transcript')
    
    logger.info(f"❌ CACHE MISS: No cached transcript for {video_id}, fetching from API")
    
    # ==========================================
    # STEP 2: TRY YOUTUBE DATA API (Primary)
    # ==========================================
    # logger.info(f"📡 [STEP 2] Attempting YouTube Data API for {video_id}")
    # transcript = await get_transcript_via_youtube_api(video_id)
    
    # if transcript and not transcript.startswith("TRANSCRIPT_ERROR"):
    #     logger.info(f"✅ SUCCESS: Got transcript from YouTube API for {video_id}")
    #     _cache_transcript(cache_key, video_id, transcript)
    #     return transcript
    
    # logger.warning(f"⚠️ YouTube API failed for {video_id}")
    
    # ==========================================
    # STEP 3: TRY SUPDATA.AI API (Secondary)
    # ==========================================
    if SUPADATA_API_KEY:
        logger.info(f"📡 [STEP 3] Attempting supadata.ai API for {video_id}")
        transcript = await _fetch_via_supdata_api(video_id)
        
        if transcript and not transcript.startswith("TRANSCRIPT_ERROR"):
            logger.info(f"✅ SUCCESS: Got transcript from supadata.ai for {video_id}")
            _cache_transcript(cache_key, video_id, transcript)
            return transcript
        
        logger.warning(f"⚠️ supadata.ai API failed for {video_id}")
    else:
        logger.debug(f"⏭️  [STEP 3] SKIPPED: supadata.ai API key not configured")
    
    # ==========================================
    # STEP 4: TRY YOUTUBE-TRANSCRIPT-API (Fallback - LOCAL only)
    # ==========================================
    # if IS_LOCAL_ENV:
    #     logger.info(f"📡 [STEP 4] Environment is LOCAL, attempting youtube-transcript-api for {video_id}")
    #     transcript = await _fetch_via_youtube_transcript_api(video_id)
        
    #     if transcript and not transcript.startswith("TRANSCRIPT_ERROR"):
    #         logger.info(f"✅ SUCCESS: Got transcript from youtube-transcript-api for {video_id}")
    #         _cache_transcript(cache_key, video_id, transcript)
    #         return transcript
        
    #     logger.warning(f"⚠️ youtube-transcript-api also failed for {video_id}")
    # else:
    #     logger.warning(
    #         f"⚠️ [STEP 4] SKIPPED: Environment is CLOUD ({ENV}), "
    #         f"youtube-transcript-api is disabled to prevent blocking"
    #     )
    
    # ==========================================
    # STEP 5: ALL FAILED
    # ==========================================
    logger.error(
        f"❌ TRANSCRIPT UNAVAILABLE: All methods failed for {video_id}\n"
        f"   - YouTube API: Failed\n"
        f"   - supadata.ai API: {'Not configured' if not SUPADATA_API_KEY else 'Failed'}\n"
        f"   - youtube-transcript-api: {'Disabled (cloud)' if not IS_LOCAL_ENV else 'Failed'}\n"
        f"   Continuing without transcript for this video"
    )
    
    return None


async def _fetch_via_supdata_api(video_id: str) -> Optional[str]:
    """
    Fetch transcript using supadata.ai API
    Works on both local and cloud environments
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Transcript text or None if failed
    """
    
    def _call():
        try:
            logger.debug(f"🔍 Calling supadata.ai API for {video_id}")
            
            headers = {
                "x-api-key": f"{SUPADATA_API_KEY}",
                "Content-Type": "application/json",
            }
            
            # payload = {
            #     "video_id": video_id,
            #     "languages": ["en", "hi", "en-US", "en-IN"]
            # }
            
            url = f"{SUPADATA_API_BASE_URL}/transcript?url=https://www.youtube.com/watch?v={video_id}&text=true&mode=native&lang=en"
            
            logger.info(f"📤 Sending request to {url} for video {video_id}")
            
            response = requests.get(
                url,
                headers=headers,
                timeout=SUPADATA_TIMEOUT
            )
            
            logger.info(f"📥 Received response status: {response.status_code}")
            
            # Handle HTTP errors
            if response.status_code == 401:
                logger.error(f"❌ supadata.ai authentication failed: Invalid API key")
                return f"TRANSCRIPT_ERROR: Authentication failed (401)"
            elif response.status_code == 429:
                logger.warning(f"⚠️ supadata.ai rate limit exceeded for {video_id}")
                return f"TRANSCRIPT_ERROR: Rate limit exceeded (429)"
            elif response.status_code == 404:
                logger.warning(f"⚠️ Video not found or transcripts disabled for {video_id}")
                return f"TRANSCRIPT_ERROR: Video not found (404)"
            elif response.status_code >= 500:
                logger.error(f"❌ supadata.ai server error: {response.status_code}")
                return f"TRANSCRIPT_ERROR: Server error ({response.status_code})"
            elif response.status_code >= 400:
                logger.error(f"❌ supadata.ai client error: {response.status_code} - {response.text}")
                return f"TRANSCRIPT_ERROR: Client error ({response.status_code})"
            
            # Parse response
            data = response.json()
            
            # if not data.get("success"):
            #     error_msg = data.get("error", "Unknown error")
            #     logger.warning(f"⚠️ supadata.ai returned failure: {error_msg}")
            #     return f"TRANSCRIPT_ERROR: {error_msg}"
            
            transcript = data.get("content", {})
            lang = data.get("lang", "unknown")
            availableLangs = data.get("availableLangs")
            
            if not transcript:
                logger.warning(f"⚠️ supadata.ai returned empty transcript for {video_id}")
                return f"TRANSCRIPT_ERROR: Empty transcript"
            
            logger.info(
                f"✅ supadata.ai success for {video_id}\n"
                f"   - Language: {lang}\n"
                f"   - Length: {len(transcript)} characters"
            )
            
            return transcript
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ supadata.ai API timeout for {video_id} (>{SUPADATA_TIMEOUT}s)")
            return f"TRANSCRIPT_ERROR: API timeout"
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ supadata.ai API connection error for {video_id}: {e}")
            return f"TRANSCRIPT_ERROR: Connection error"
        except json.JSONDecodeError as e:
            logger.error(f"❌ supadata.ai returned invalid JSON for {video_id}: {e}")
            return f"TRANSCRIPT_ERROR: Invalid JSON response"
        except Exception as e:
            logger.error(
                f"❌ supadata.ai API error for {video_id}: {type(e).__name__}: {str(e)}"
            )
            return f"TRANSCRIPT_ERROR: {e}"
    
    return await run_in_threadpool(_call)


async def _fetch_via_youtube_transcript_api(video_id: str) -> Optional[str]:
    """
    Fallback method using youtube-transcript-api
    With rate limiting to respect YouTube limits
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Transcript text or None if failed
    """
    global LAST_REQUEST_TIME
    
    def _call():
        global LAST_REQUEST_TIME
        
        # Apply rate limiting - wait before making request
        current_time = time.time()
        time_since_last_request = current_time - LAST_REQUEST_TIME
        
        if time_since_last_request < MIN_DELAY_BETWEEN_REQUESTS:
            wait_time = MIN_DELAY_BETWEEN_REQUESTS - time_since_last_request
            logger.debug(f"⏳ Rate limiting: waiting {wait_time:.2f}s before youtube-transcript-api call")
            time.sleep(wait_time)
        
        # Add random jitter to avoid predictable patterns
        jitter = random.uniform(0.5, 1.5)
        time.sleep(jitter)
        
        LAST_REQUEST_TIME = time.time()
        
        try:
            logger.debug(f"🔍 Calling YouTubeTranscriptApi for {video_id}")
            yt_api = YouTubeTranscriptApi().fetch(video_id, languages=['en', 'hi', 'en-US', 'en-IN'])

            # Combine transcript segments into single text
            transcript_text = " ".join([seg["text"] for seg in yt_api.to_raw_data()])
            logger.debug(f"✅ YouTubeTranscriptApi returned {len(transcript_text)} characters")
            return transcript_text
            
        except TranscriptsDisabled as e:
            logger.warning(f"⚠️ Transcripts are disabled for video {video_id}")
            return f"TRANSCRIPT_ERROR: {e}"
        except NoTranscriptFound as e:
            logger.warning(f"⚠️ No transcript found for video {video_id}")
            return f"TRANSCRIPT_ERROR: {e}"
        except Exception as e:
            logger.error(
                f"❌ YouTubeTranscriptApi error for {video_id}: {type(e).__name__}: {str(e)}"
            )
            return f"TRANSCRIPT_ERROR: {e}"
    
    return await run_in_threadpool(_call)


def _cache_transcript(cache_key: str, video_id: str, transcript: str) -> bool:
    """
    Cache a successfully retrieved transcript
    
    Args:
        cache_key: Generated cache key
        video_id: YouTube video ID
        transcript: Transcript text to cache
        
    Returns:
        True if cached successfully, False otherwise
    """
    try:
        was_cached = set_cached(
            key=cache_key,
            video_id=video_id,
            cache_type="transcript",
            value={'transcript': transcript},
            ttl_hours=24
        )
        
        if was_cached:
            logger.info(f"💾 Cached transcript for {video_id} (24h TTL)")
            return True
        else:
            logger.warning(f"⚠️ Failed to cache transcript for {video_id}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error caching transcript for {video_id}: {e}")
        return False


async def check_transcript_availability(video_id: str) -> dict:
    """
    Check which transcript methods are available for a video
    Useful for debugging and monitoring
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Dictionary with availability status
        
    Example:
        {
            "video_id": "dQw4w9WgXcQ",
            "youtube_api_available": True,
            "youtube_transcript_api_available": False,
            "captions_found": ["en", "hi"],
            "recommended_method": "youtube_api"
        }
    """
    logger.info(f"� Checking transcript availability for {video_id}")
    
    result = {
        "video_id": video_id,
        "youtube_api_available": False,
        "supdata_api_available": False,
        "youtube_transcript_api_available": False,
        "environment": ENV,
        "recommended_method": None,
        "availability_chain": []
    }
    
    # Check YouTube API
    try:
        transcript = await get_transcript_via_youtube_api(video_id)
        if transcript and not transcript.startswith("TRANSCRIPT_ERROR"):
            result["youtube_api_available"] = True
            result["availability_chain"].append("✅ YouTube API")
            logger.info(f"✅ YouTube API: Available")
        else:
            result["availability_chain"].append("❌ YouTube API")
    except Exception as e:
        logger.warning(f"⚠️ YouTube API check failed: {e}")
        result["availability_chain"].append(f"❌ YouTube API ({e})")
    
    # Check supadata.ai API
    if SUPADATA_API_KEY:
        try:
            transcript = await _fetch_via_supdata_api(video_id)
            if transcript and not transcript.startswith("TRANSCRIPT_ERROR"):
                result["supdata_api_available"] = True
                result["availability_chain"].append("✅ supadata.ai")
                logger.info(f"✅ supadata.ai API: Available")
            else:
                result["availability_chain"].append("❌ supadata.ai")
        except Exception as e:
            logger.warning(f"⚠️ supadata.ai check failed: {e}")
            result["availability_chain"].append(f"❌ supadata.ai ({e})")
    else:
        result["availability_chain"].append("⏭️  supadata.ai (not configured)")
        logger.info(f"⏭️  supadata.ai: Not configured")
    
    # Check youtube-transcript-api (LOCAL only)
    if IS_LOCAL_ENV:
        try:
            def _call():
                yt_api = YouTubeTranscriptApi()
                yt_api.get_transcript(video_id, languages=['en', 'hi'])
                return True
            
            result["youtube_transcript_api_available"] = await run_in_threadpool(_call)
            result["availability_chain"].append("✅ youtube-transcript-api")
            logger.info(f"✅ youtube-transcript-api: Available")
        except Exception as e:
            logger.warning(f"⚠️ youtube-transcript-api check failed: {e}")
            result["availability_chain"].append(f"❌ youtube-transcript-api ({e})")
    else:
        result["availability_chain"].append("⏭️  youtube-transcript-api (cloud disabled)")
        logger.info(f"⏭️  youtube-transcript-api: Skipped (cloud environment)")
    
    # Recommend best method
    if result["youtube_api_available"]:
        result["recommended_method"] = "youtube_api"
    elif result["supdata_api_available"]:
        result["recommended_method"] = "supdata_api"
    elif result["youtube_transcript_api_available"]:
        result["recommended_method"] = "youtube_transcript_api"
    else:
        result["recommended_method"] = "none"
    
    logger.info(
        f"📊 Availability summary for {video_id}:\n"
        f"   - YouTube API: {result['youtube_api_available']}\n"
        f"   - supadata.ai API: {result['supdata_api_available']}\n"
        f"   - youtube-transcript-api: {result['youtube_transcript_api_available']}\n"
        f"   - Recommended: {result['recommended_method']}"
    )
    
    return result

