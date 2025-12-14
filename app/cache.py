import json
import os
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Any

# SQLite cache configuration
DB_PATH = os.path.join("data", "cache.db")

def ensure_db_dir():
    """Ensure data directory exists"""
    os.makedirs("data", exist_ok=True)

def init_cache_db():
    """Initialize SQLite cache database - call this in FastAPI startup"""
    ensure_db_dir()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create cache table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            video_id TEXT,
            cache_type TEXT,
            value TEXT NOT NULL,
            content_hash TEXT,
            ttl_hours INTEGER DEFAULT 24,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_video_id ON cache(video_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_cache_type ON cache(cache_type)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_created_at ON cache(created_at)
    ''')
    
    conn.commit()
    conn.close()
    print(f"✅ SQLite cache database initialized at {DB_PATH}")

def close_cache_db():
    """Close cache database connection - call this in FastAPI shutdown"""
    # SQLite connections are closed per-operation, nothing special needed
    print("✅ SQLite cache database closed")

def generate_cache_key(video_id: str, cache_type: str, content_hash: Optional[str] = None) -> str:
    """
    Generate consistent cache keys
    Args:
        video_id: YouTube video ID
        cache_type: Type of cache ('transcript' or 'llm_analysis')
        content_hash: Optional hash for detecting content changes
    Returns:
        Hashed cache key
    """
    key_str = f"{video_id}|{cache_type}"
    if content_hash:
        key_str += f"|{content_hash}"
    return hashlib.md5(key_str.encode()).hexdigest()

def generate_content_hash(content: str) -> str:
    """
    Generate a short hash of content for cache key uniqueness
    Useful for detecting when transcript/comments have changed
    Args:
        content: Content to hash
    Returns:
        First 8 characters of SHA256 hash
    """
    return hashlib.sha256(content.encode()).hexdigest()[:8]

def get_cached(key: str, ttl_hours: int = 24) -> Optional[dict]:
    """
    Get cached value from SQLite if not expired
    Args:
        key: Cache key
        ttl_hours: Time to live in hours (default: 24)
    Returns:
        Cached value or None
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT value, created_at FROM cache WHERE key = ?
        ''', (key,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        value, created_at = result
        created_dt = datetime.fromisoformat(created_at)
        
        # Check if expired
        if datetime.now() - created_dt > timedelta(hours=ttl_hours):
            delete_cached(key)
            return None
        
        return json.loads(value)
    except Exception as e:
        print(f"❌ Cache get error for key {key}: {e}")
        return None

def set_cached(key: str, video_id: str, cache_type: str, value: dict, 
               content_hash: Optional[str] = None, ttl_hours: int = 24) -> bool:
    """
    Save data to SQLite cache with TTL
    Args:
        key: Cache key
        video_id: YouTube video ID
        cache_type: Type of cache ('transcript' or 'llm_analysis')
        value: Data to cache (will be JSON serialized)
        content_hash: Optional hash for detecting content changes
        ttl_hours: Time to live in hours (default: 24)
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO cache 
            (key, video_id, cache_type, value, content_hash, ttl_hours)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (key, video_id, cache_type, json.dumps(value), content_hash, ttl_hours))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Cache set error for key {key}: {e}")
        return False

def delete_cached(key: str) -> bool:
    """
    Delete value from cache
    Args:
        key: Cache key
    Returns:
        True if deleted, False otherwise
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM cache WHERE key = ?', (key,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Cache delete error for key {key}: {e}")
        return False

def clear_expired_cache() -> int:
    """
    Remove all expired cache entries
    Useful as a background cleanup task (run daily)
    Returns:
        Number of expired entries deleted
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM cache 
            WHERE datetime(created_at, '+' || ttl_hours || ' hours') < datetime('now')
        ''')
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            print(f"🧹 Cleaned up {deleted} expired cache entries")
        return deleted
    except Exception as e:
        print(f"❌ Cache cleanup error: {e}")
        return 0

def clear_cache_by_pattern(cache_type: str) -> int:
    """
    Delete all cache entries of a specific type
    Useful for clearing all transcripts or all LLM analyses
    Args:
        cache_type: Type of cache to clear ('transcript' or 'llm_analysis')
    Returns:
        Number of entries deleted
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM cache WHERE cache_type = ?', (cache_type,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"🗑️ Deleted {deleted} cache entries of type '{cache_type}'")
        return deleted
    except Exception as e:
        print(f"❌ Cache pattern delete error: {e}")
        return 0

def get_cache_stats() -> dict:
    """
    Get cache statistics (useful for monitoring)
    Returns:
        Dictionary with cache stats
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM cache')
        total = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM cache WHERE cache_type = "transcript"')
        transcripts = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM cache WHERE cache_type = "llm_analysis"')
        llm_analyses = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(LENGTH(value)) FROM cache')
        size_bytes = cursor.fetchone()[0] or 0
        
        # Get oldest and newest entries
        cursor.execute('SELECT MIN(created_at) FROM cache')
        oldest = cursor.fetchone()[0]
        
        cursor.execute('SELECT MAX(created_at) FROM cache')
        newest = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "status": "Connected",
            "total_entries": total,
            "transcripts": transcripts,
            "llm_analyses": llm_analyses,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "database_file": DB_PATH,
            "oldest_entry": oldest,
            "newest_entry": newest
        }
    except Exception as e:
        print(f"❌ Cache stats error: {e}")
        return {"status": "Error", "error": str(e)}
