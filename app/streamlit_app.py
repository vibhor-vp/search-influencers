import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="YouTube Influencer Finder",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state for pagination
if "all_rows" not in st.session_state:
    st.session_state.all_rows = []
if "next_page_token" not in st.session_state:
    st.session_state.next_page_token = None
if "current_keyword" not in st.session_state:
    st.session_state.current_keyword = None
if "search_params" not in st.session_state:
    st.session_state.search_params = {}
if "loading_more" not in st.session_state:
    st.session_state.loading_more = False

# Title and description
st.title("📺 YouTube Influencer Finder")
st.markdown("Search for YouTube influencers based on keywords and filters")

# Sidebar for filters
st.sidebar.header("🔍 Search Filters")

# API configuration
# API_BASE_URL = st.sidebar.text_input(
#     "API Base URL",
#     value="http://localhost:8000",
#     help="Enter the FastAPI backend URL"
# )
API_BASE_URL = "http://13.232.117.41:8000"

# Search parameters
keyword = st.sidebar.text_input(
    "📝 Keyword",
    placeholder="e.g., tech, gaming, cooking",
    help="Enter the keyword to search for influencers"
)

min_subscribers = st.sidebar.number_input(
    "📊 Minimum Subscribers",
    value=5000,
    min_value=0,
    step=1000,
    help="Filter channels by minimum subscriber count"
)

max_subscribers = st.sidebar.number_input(
    "📊 Maximum Subscribers",
    value=1000000,
    min_value=0,
    step=10000,
    help="Filter channels by maximum subscriber count"
)

country = st.sidebar.text_input(
    "🌍 Country Code",
    value="IN",
    max_chars=2,
    help="Enter 2-letter ISO country code (e.g., IN, US, UK)"
)

# Search button
search_button = st.sidebar.button("🔎 Search", use_container_width=True, type="primary")

# Helper function to make API calls
def make_search_request(keyword, min_subs, max_subs, country_code, page_token=None):
    try:
        params = {
            "keyword": keyword,
            "min_subscribers": int(min_subs),
            "max_subscribers": int(max_subs),
            "country": country_code.upper()
        }
        
        if page_token:
            params["page_token"] = page_token
        
        response = requests.get(
            f"{API_BASE_URL}/search",
            params=params,
            timeout=180
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"❌ API Error: {response.status_code}")
            st.error(response.text)
            return None
    
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Connection Error: Cannot reach API at {API_BASE_URL}")
        st.info("Make sure your FastAPI server is running and the URL is correct")
        return None
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return None

# Main content area
if search_button:
    if not keyword:
        st.error("❌ Please enter a keyword to search")
    else:
        # Reset pagination if new keyword
        if st.session_state.current_keyword != keyword:
            st.session_state.all_rows = []
            st.session_state.next_page_token = None
            st.session_state.loading_more = False
            st.session_state.current_keyword = keyword
            st.session_state.search_params = {
                "min_subscribers": min_subscribers,
                "max_subscribers": max_subscribers,
                "country": country
            }
        
        st.info(f"🔄 Searching for '{keyword}' influencers...")
        
        # Make API call
        data = make_search_request(keyword, min_subscribers, max_subscribers, country)
        print("data:", data)
        if data:
            rows = data.get("rows", [])
            next_page_token = data.get("nextPageToken")
            
            # Add new rows to accumulated rows
            st.session_state.all_rows.extend(rows)
            st.session_state.next_page_token = next_page_token

# Display results if we have any data in session state
if st.session_state.all_rows and st.session_state.current_keyword:
    keyword = st.session_state.current_keyword
    df = pd.DataFrame(st.session_state.all_rows)
    
    # Display summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📌 Keyword", keyword)
    with col2:
        st.metric("📺 Total Found", len(st.session_state.all_rows))
    with col3:
        st.metric("📊 Results Loaded", len(st.session_state.all_rows))
    with col4:
        st.metric("🔍 Time", f"{datetime.now().strftime('%H:%M:%S')}")
    
    # Display full table
    st.subheader("📊 Results Table")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "channel_id": st.column_config.TextColumn("Channel ID", width="medium"),
            "channel_title": st.column_config.TextColumn("Channel", width="large"),
            "subscribers": st.column_config.NumberColumn("Subscribers", format="%d"),
            "video_count": st.column_config.NumberColumn("Videos", format="%d"),
            "country": st.column_config.TextColumn("Country", width="small"),
            "video_title": st.column_config.TextColumn("Video Title", width="large"),
            "video_publishedAt": st.column_config.TextColumn("Published", width="medium"),
            "comments_count": st.column_config.NumberColumn("Comments", format="%d"),
            "transcript_snippet": st.column_config.TextColumn("Transcript", width="large"),
            "llm_product_mentions": st.column_config.TextColumn("Products", width="medium"),
            "llm_review_tone": st.column_config.TextColumn("Tone", width="small"),
            "llm_audience_sentiment": st.column_config.TextColumn("Sentiment", width="small"),
            "llm_video_selling_product": st.column_config.TextColumn("Selling", width="small"),
            "llm_affiliate_marketing": st.column_config.TextColumn("Affiliate", width="small"),
        }
    )
    
    # Display detailed insights
    st.subheader("💡 Key Insights")
    
    insight_col1, insight_col2, insight_col3, insight_col4 = st.columns(4)
    
    with insight_col1:
        avg_subscribers = df['subscribers'].mean()
        st.metric("Average Subscribers", f"{int(avg_subscribers):,}")
    
    with insight_col2:
        avg_comments = df['comments_count'].mean()
        st.metric("Avg Comments/Video", f"{int(avg_comments):,.0f}")
    
    with insight_col3:
        total_videos_analyzed = len(df)
        st.metric("Videos Analyzed", total_videos_analyzed)
    
    with insight_col4:
        selling_count = df['llm_video_selling_product'].astype(str).str.lower().eq('true').sum()
        st.metric("Selling Products", selling_count)
    
    # Expandable sections for each result
    st.subheader("🔎 Detailed Results")
    
    for idx, row in df.iterrows():
        with st.expander(
            f"📺 {row['channel_title']} - {row['video_title'][:50]}...",
            expanded=False
        ):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Channel Info**")
                st.write(f"- **ID**: {row['channel_id']}")
                st.write(f"- **Subscribers**: {row['subscribers']:,}")
                st.write(f"- **Total Videos**: {row['video_count']}")
                st.write(f"- **Country**: {row['country']}")
            
            with col2:
                st.write("**Video Info**")
                st.write(f"- **Video ID**: {row['video_id']}")
                st.write(f"- **Published**: {row['video_publishedAt']}")
                st.write(f"- **Comments**: {row['comments_count']}")
            
            st.write("---")
            st.write("**Transcript Snippet**")
            st.text(row['transcript_snippet'] or "No transcript available")
            
            st.write("---")
            st.write("**LLM Analysis**")
            llm_col1, llm_col2 = st.columns(2)
            
            with llm_col1:
                st.write(f"🎯 **Product Mentions**: {row['llm_product_mentions']}")
                st.write(f"😊 **Tone**: {row['llm_review_tone']}")
            
            with llm_col2:
                st.write(f"📈 **Audience Sentiment**: {row['llm_audience_sentiment']}")
                st.write(f"💰 **Selling Product**: {row['llm_video_selling_product']}")
            
            st.write(f"🤝 **Affiliate Marketing**: {row['llm_affiliate_marketing']}")
    
    # Pagination section - OUTSIDE the search_button block
    st.divider()
    st.subheader("📄 Load More Results")
    
    if st.session_state.next_page_token:
        col_btn, col_msg = st.columns([1, 3])
        
        with col_btn:
            if st.session_state.loading_more:
                st.info("🔄 Loading...")
            else:
                if st.button("🔎 Search More Channels", use_container_width=True, type="secondary", key="load_more_btn"):
                    st.session_state.loading_more = True
                    st.rerun()
        
        # Make API call if loading_more is True
        if st.session_state.loading_more:
            with col_msg:
                with st.spinner("Fetching more results..."):
                    more_data = make_search_request(
                        st.session_state.current_keyword,
                        st.session_state.search_params["min_subscribers"],
                        st.session_state.search_params["max_subscribers"],
                        st.session_state.search_params["country"],
                        page_token=st.session_state.next_page_token
                    )
            
            if more_data:
                more_rows = more_data.get("rows", [])
                st.session_state.all_rows.extend(more_rows)
                st.session_state.next_page_token = more_data.get("nextPageToken")
                st.session_state.loading_more = False
                
                st.success(f"✅ Added {len(more_rows)} more results!")
                st.rerun()
            else:
                st.session_state.loading_more = False
                st.error("❌ Failed to load more results")
    else:
        st.info("ℹ️ No more results available")


# Download options (if we have results)
if st.session_state.all_rows and st.session_state.current_keyword:
    df = pd.DataFrame(st.session_state.all_rows)
    
    st.subheader("📥 Export Results")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv = df.to_csv(index=False)
        st.download_button(
            label="📊 Download as CSV",
            data=csv,
            file_name=f"influencers_{st.session_state.current_keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        json_str = json.dumps(st.session_state.all_rows, indent=2)
        st.download_button(
            label="📄 Download as JSON",
            data=json_str,
            file_name=f"influencers_{st.session_state.current_keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col3:
        st.info("💡 Excel export requires openpyxl library")

# Footer
st.divider()
st.markdown(
    """
    <div style='text-align: center; color: gray; padding: 20px;'>
    <p>YouTube Influencer Finder | Powered by FastAPI & Streamlit</p>
    </div>
    """,
    unsafe_allow_html=True
)
