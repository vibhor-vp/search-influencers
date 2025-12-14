from youtube_transcript_api import YouTubeTranscriptApi
from fastapi.concurrency import run_in_threadpool
from app.cache import get_cached, set_cached, generate_cache_key
import time
import random

# Rate limiting configuration
MIN_DELAY_BETWEEN_REQUESTS = 5  # Minimum 5 seconds between requests
MAX_DELAY_BETWEEN_REQUESTS = 10  # Maximum 10 seconds between requests
LAST_REQUEST_TIME = 0

async def get_video_transcript(video_id: str):
    """
    Get video transcript with SQLite caching and rate limiting
    Args:
        video_id: YouTube video ID
    Returns:
        Transcript text or error message
    """
    # Try to get from cache first
    cache_key = generate_cache_key(video_id, "transcript")
    cached_transcript = get_cached(cache_key)
    
    if cached_transcript is not None:
        print(f"✅ Cache HIT: Transcript for {video_id}")
        return cached_transcript.get('transcript')
    
    print(f"❌ Cache MISS: Fetching transcript for {video_id}")
    
    # Not in cache, fetch from API with rate limiting
    global LAST_REQUEST_TIME
    
    def _call():
        global LAST_REQUEST_TIME
        
        # Apply rate limiting - wait before making request
        current_time = time.time()
        time_since_last_request = current_time - LAST_REQUEST_TIME
        
        if time_since_last_request < MIN_DELAY_BETWEEN_REQUESTS:
            wait_time = MIN_DELAY_BETWEEN_REQUESTS - time_since_last_request
            print(f"⏳ Rate limiting: waiting {wait_time:.2f}s before fetching transcript for {video_id}")
            time.sleep(wait_time)
        
        # Add random jitter to avoid predictable patterns
        jitter = random.uniform(0, 1)
        time.sleep(jitter)
        
        LAST_REQUEST_TIME = time.time()
        
        try:
            # YouTubeTranscriptApi is now directly imported
            t = YouTubeTranscriptApi().fetch(video_id, languages=['en', 'hi'])
            return " ".join([seg["text"] for seg in t.to_raw_data()])
        except Exception as e:
            return f"TRANSCRIPT_ERROR: {e}"

    transcript = await run_in_threadpool(_call)
    
    # Cache successful transcripts (but not errors)
    if not transcript.startswith("TRANSCRIPT_ERROR"):
        transcript_cached = set_cached(
            key=cache_key,
            video_id=video_id,
            cache_type="transcript",
            value={'transcript': transcript},
            ttl_hours=24
        )
        if transcript_cached:
            print(f"💾 Cached transcript for {video_id}")
    else:
        print(f"⚠️ Not caching transcript error for {video_id}: {transcript}")
    
    return transcript

