# llm_service.py
# NOTE: This mirrors the LLM logic in your notebook.
# save_llm_result is commented out as requested.

import json
from fastapi.concurrency import run_in_threadpool
from langchain_core.prompts import PromptTemplate
from langchain_openai.chat_models import ChatOpenAI
from app.cache import get_cached, set_cached, generate_cache_key, generate_content_hash
from app.config import OPENAI_API_KEY

# If you used langchain in the notebook, you can wire it here.
# For now, a minimal example calling OpenAI directly (or stub) is provided.

def _analyze_prompt(video_id: str, transcript: str, comments: list) -> str:
    """
    Build a prompt to send to an LLM. This returns a JSON string expected from the LLM.
    """
    # Truncate very long transcript to safe length
    t = (transcript or "")[:3000]
    c = " ".join((comments or [])[:20])[:2000]
    prompt = f"""
        You are an expert content analyzer. Return ONLY a valid JSON object with keys:
          - product_mentions: [strings]
          - review_tone: "positive|neutral|negative"
          - audience_sentiment: "positive|neutral|negative"
          - video_already_selling_product: "yes|no"

        Inputs:
        video_id: {video_id}
        transcript: {t}
        comments: {c}

        Return a compact JSON object.
        """
    return prompt

async def analyze_with_llm(video_id: str, transcript: str, comments: list):
    """
    Runs the LLM analysis with SQLite caching to avoid redundant API calls.
    Caches based on video_id + content hash to detect when transcript/comments change.
    """
    # Generate cache key based on video_id and content hash
    content = f"{transcript}{''.join(comments[:5])}"  # Use first 5 comments
    content_hash = generate_content_hash(content)
    cache_key = generate_cache_key(video_id, "llm_analysis", content_hash)
    
    # Try to get from cache first
    cached_analysis = get_cached(cache_key)
    if cached_analysis is not None:
        print(f"✅ Cache HIT: LLM analysis for {video_id}")
        return cached_analysis
    
    print(f"❌ Cache MISS: Running LLM analysis for {video_id}")
    
    # Not in cache, perform LLM analysis
    def _call():
        if not transcript and not comments:
            return {}
        prompt = PromptTemplate(
            input_variables=["video_id", "transcript", "comments"],
            template=(
                """
                  You are an expert content analyzer.
                  Extract information in **strict JSON** format only.
    
                  Return ONLY a valid JSON object with this exact structure:
    
                  {{
                    "product_mentions": [string],
                    "review_tone": "positive|neutral|negative",
                    "audience_sentiment": "positive|mixed|negative"(if comments are approx 70% positive then keep it positive else you decide),
                    "gear_focus": "cricket|badminton|football|wrestling|volleyball|kabaddi|pickleball",
                    "video_already_selling_product": "yes|no",
                    "affiliate_marketing": "yes|no",
                    "affiliate_marketing_url": "<url or empty string>",
                    "summary": "<concise textual summary>"
                  }}
    
    
                  Do not include any Markdown formatting, text before or after, or explanations.
                  Analyze this content:
                  Transcript: {transcript}
                  Comments: {comments}
                """
            ))
        llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, openai_api_key=OPENAI_API_KEY)
        chain = prompt | llm
        try:
            llm_result = chain.invoke({
                "video_id": video_id,
                "transcript": transcript[:3000] if transcript else "",
                "comments": " ".join(comments[:20])
            })
            print(f"llm_result for video: {video_id} is {llm_result}")
            clean_json_string = llm_result.content.replace("```json\n", "").replace("\n```", "")
            llm_content = json.loads(clean_json_string)
            return llm_content
        except Exception as e:
            print(f"LLM error: {e}")
            raise ValueError("Error in analyze_with_llm!")

    analysis_result = await run_in_threadpool(_call)
    
    # Cache the LLM analysis result (24-hour TTL)
    # clean_json_string = analysis_result.content.replace("```json\n", "").replace("\n```", "")
    # llm_content = json.loads(clean_json_string)
    if analysis_result and not isinstance(analysis_result, str):
        llm_analysis_cached = set_cached(
            key=cache_key,
            video_id=video_id,
            cache_type="llm_analysis",
            value=analysis_result,
            content_hash=content_hash,
            ttl_hours=24
        )
        if llm_analysis_cached:
            print(f"💾 Cached LLM analysis for {video_id}")
    
    return analysis_result
