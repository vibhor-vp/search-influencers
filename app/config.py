"""
Centralized configuration management
Loads environment variables safely with validation
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =====================================
# VALIDATION HELPER
# =====================================
def _get_required_env(key: str, description: str = "") -> str:
    """
    Get a required environment variable.
    Raises ValueError if not found.
    
    Args:
        key: Environment variable name
        description: Human-readable description for error message
        
    Returns:
        Environment variable value
        
    Raises:
        ValueError: If environment variable is not set
    """
    value = os.getenv(key)
    if not value:
        error_msg = f"❌ Missing required environment variable: {key}"
        if description:
            error_msg += f" ({description})"
        error_msg += f"\n   Please set it in your .env file or system environment"
        raise ValueError(error_msg)
    return value


def _get_optional_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get an optional environment variable with a default fallback.
    
    Args:
        key: Environment variable name
        default: Default value if not set
        
    Returns:
        Environment variable value or default
    """
    return os.getenv(key, default)


# =====================================
# REQUIRED API KEYS
# =====================================
try:
    GOOGLE_API_KEY = _get_required_env(
        "GOOGLE_API_KEY",
        "YouTube API key from https://console.cloud.google.com/"
    )
except ValueError as e:
    print(str(e))
    GOOGLE_API_KEY = None

try:
    OPENAI_API_KEY = _get_required_env(
        "OPENAI_API_KEY",
        "OpenAI API key from https://platform.openai.com/account/api-keys"
    )
except ValueError as e:
    print(str(e))
    OPENAI_API_KEY = None


# =====================================
# OPTIONAL CREDENTIALS
# =====================================
GOOGLE_CLIENT_ID = _get_optional_env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _get_optional_env("GOOGLE_CLIENT_SECRET")


# =====================================
# SUPADATA.AI API (Transcript Service)
# =====================================
SUPADATA_API_KEY = _get_optional_env("SUPADATA_API_KEY")
SUPADATA_API_BASE_URL = "https://api.supadata.ai/v1"
SUPADATA_TIMEOUT = 30  # seconds


# =====================================
# APPLICATION CONFIG
# =====================================
BASE_URL = _get_optional_env("BASE_URL", "http://localhost:8000")
ENV = _get_optional_env("ENV", "development")
DEBUG = _get_optional_env("DEBUG", "False").lower() in ("true", "1", "yes")


# =====================================
# ENVIRONMENT DETECTION
# =====================================
# Detect if we're running locally or on cloud infrastructure
# This is used by transcript_service to decide whether to use youtube-transcript-api
_LOCAL_INDICATORS = [
    "localhost",
    "127.0.0.1",
    "local",
    "development",
    "staging-local"
]

# Determine if running locally based on environment
IS_LOCAL_ENV = any(indicator in ENV.lower() for indicator in _LOCAL_INDICATORS)

# If environment is not explicitly local, check other indicators
if not IS_LOCAL_ENV:
    # Also check if running via localhost
    IS_LOCAL_ENV = "localhost" in BASE_URL.lower() or "127.0.0.1" in BASE_URL



# =====================================
# DATABASE CONFIG
# =====================================
DATABASE_URL = _get_optional_env(
    "DATABASE_URL",
    "sqlite:///./data/cache.db"
)


# =====================================
# VALIDATION ON STARTUP
# =====================================
def validate_config() -> bool:
    """
    Validate all required configuration is present.
    Call this in FastAPI startup event.
    
    Returns:
        True if all required config is valid
        
    Raises:
        ValueError: If any required config is missing
    """
    missing = []
    
    if not GOOGLE_API_KEY:
        missing.append("GOOGLE_API_KEY")
    
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    
    if missing:
        error_msg = f"❌ Missing required configuration: {', '.join(missing)}\n"
        error_msg += "   Please set these environment variables in your .env file or system environment\n"
        error_msg += "   See .env.sample for reference"
        raise ValueError(error_msg)
    
    print("✅ Configuration validated successfully")
    return True


# =====================================
# LOGGING CONFIG INFO (NO SECRETS!)
# =====================================
def log_config() -> None:
    """
    Log non-sensitive configuration for debugging.
    Never logs actual API keys!
    """
    print("\n" + "=" * 50)
    print("📋 APPLICATION CONFIGURATION")
    print("=" * 50)
    print(f"Environment: {ENV}")
    print(f"Is Local: {IS_LOCAL_ENV}")
    print(f"Debug Mode: {DEBUG}")
    print(f"Base URL: {BASE_URL}")
    print(f"Database: {DATABASE_URL}")
    print(f"Google API Key: {'✅ Set' if GOOGLE_API_KEY else '❌ Missing'}")
    print(f"OpenAI API Key: {'✅ Set' if OPENAI_API_KEY else '❌ Missing'}")
    print("=" * 50 + "\n")
