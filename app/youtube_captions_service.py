"""
YouTube Captions Service - Fetch transcripts via YouTube Data API
Uses official YouTube API captions instead of scraping
"""

import logging
from typing import Optional, Dict, List
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from fastapi.concurrency import run_in_threadpool
from app.config import GOOGLE_API_KEY
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


def _get_youtube_client():
    """Create YouTube API client"""
    return build("youtube", "v3", developerKey=GOOGLE_API_KEY, static_discovery=False)


async def get_available_captions(video_id: str) -> Optional[List[Dict[str, str]]]:
    """
    Get list of available captions for a video
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        List of caption tracks with language info, or None if error
        
    Format:
        [
            {"kind": "standard", "language": "en", "id": "..."},
            {"kind": "asr", "language": "en", "id": "..."},
        ]
    """
    def _call():
        try:
            yt = _get_youtube_client()
            request = yt.captions().list(
                part="snippet",
                videoId=video_id
            )
            response = request.execute()
            
            captions = []
            for item in response.get("items", []):
                caption = {
                    "kind": item["snippet"]["trackKind"],
                    "language": item["snippet"]["language"],
                    "id": item["id"]
                }
                captions.append(caption)
            
            logger.info(f"✅ Found {len(captions)} caption tracks for video {video_id}")
            for cap in captions:
                logger.debug(f"   - {cap['language']} ({cap['kind']})")
            
            return captions if captions else None
            
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"⚠️ No captions found for video {video_id} (404)")
            else:
                logger.error(f"❌ YouTube API error getting captions for {video_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error getting captions for {video_id}: {e}")
            return None
    
    return await run_in_threadpool(_call)


async def download_caption_track(video_id: str, caption_id: str) -> Optional[str]:
    """
    Download actual caption text for a specific caption track
    
    Args:
        video_id: YouTube video ID
        caption_id: Caption track ID from get_available_captions()
        
    Returns:
        Caption text joined with spaces, or None if error
    """
    def _call():
        try:
            yt = _get_youtube_client()
            request = yt.captions().download(
                id=caption_id,
                tfmt="srt"  # SubRip format
            )
            response = request.execute()
            
            # Parse SRT format and extract text
            caption_text = _parse_srt(response.decode('utf-8'))
            
            if caption_text:
                logger.info(f"✅ Downloaded caption track {caption_id} ({len(caption_text)} chars)")
                return caption_text
            else:
                logger.warning(f"⚠️ Caption track {caption_id} is empty")
                return None
                
        except HttpError as e:
            logger.error(f"❌ YouTube API error downloading caption {caption_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error downloading caption {caption_id}: {e}")
            return None
    
    return await run_in_threadpool(_call)


def _parse_srt(srt_content: str) -> str:
    """
    Parse SRT format and extract just the text
    
    Args:
        srt_content: SRT file content
        
    Returns:
        Extracted text joined with spaces
        
    Example SRT format:
        1
        00:00:00,000 --> 00:00:02,000
        This is the caption text
        
        2
        00:00:02,000 --> 00:00:05,000
        More caption text
    """
    lines = srt_content.split('\n')
    text_parts = []
    
    for line in lines:
        # Skip empty lines, timestamps, and sequence numbers
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            continue
        
        # Skip sequence numbers (usually just digits)
        if stripped.isdigit():
            continue
        
        # Skip timestamps (contain -->)
        if '-->' in stripped:
            continue
        
        # This is actual caption text
        text_parts.append(stripped)
    
    return ' '.join(text_parts)


async def get_transcript_via_youtube_api(
    video_id: str,
    preferred_languages: List[str] = None
) -> Optional[str]:
    """
    Get transcript using YouTube Data API
    Tries preferred languages in order, falls back to first available
    
    Args:
        video_id: YouTube video ID
        preferred_languages: List of language codes to try in order
                           Defaults to ['en', 'hi', 'en-US']
    
    Returns:
        Transcript text or None if not available
    """
    if preferred_languages is None:
        preferred_languages = ['en', 'hi', 'en-US', 'en-IN']
    
    logger.info(f"🔍 Fetching captions for video {video_id} via YouTube API")
    
    # Get available captions
    captions = await get_available_captions(video_id)
    
    if not captions:
        logger.warning(f"⚠️ No captions available for video {video_id}")
        return None
    
    # Extract caption IDs by language
    caption_map = {cap['language']: cap['id'] for cap in captions}
    
    # Try preferred languages first
    caption_id = None
    used_language = None
    
    for lang in preferred_languages:
        if lang in caption_map:
            caption_id = caption_map[lang]
            used_language = lang
            logger.info(f"📝 Using {lang} caption track for {video_id}")
            break
    
    # If no preferred language found, use first available
    if not caption_id and captions:
        caption_id = captions[0]['id']
        used_language = captions[0]['language']
        logger.info(f"📝 Preferred language not found, using {used_language} for {video_id}")
    
    if not caption_id:
        logger.warning(f"⚠️ Could not select caption track for {video_id}")
        return None
    
    # Download the selected caption
    transcript = await download_caption_track(video_id, caption_id)
    
    if transcript:
        logger.info(f"✅ Successfully retrieved transcript for {video_id} (language: {used_language})")
    else:
        logger.warning(f"⚠️ Failed to download caption content for {video_id}")
    
    return transcript


async def test_youtube_api_access() -> bool:
    """
    Test if YouTube API is accessible from current environment
    Useful for checking if we're on cloud/restricted network
    
    Returns:
        True if API is accessible, False otherwise
    """
    def _call():
        try:
            yt = _get_youtube_client()
            # Try a simple API call
            request = yt.videos().list(
                part="snippet",
                id="dQw4w9WgXcQ"  # Rick roll video - always exists
            )
            response = request.execute()
            
            if response.get("items"):
                logger.info("✅ YouTube API is accessible")
                return True
            else:
                logger.warning("⚠️ YouTube API responded but with empty results")
                return False
                
        except HttpError as e:
            logger.warning(f"⚠️ YouTube API returned HTTP error: {e.resp.status}")
            return False
        except Exception as e:
            logger.error(f"❌ YouTube API not accessible: {e}")
            return False
    
    return await run_in_threadpool(_call)
