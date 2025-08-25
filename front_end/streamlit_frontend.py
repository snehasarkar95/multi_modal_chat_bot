import streamlit as st
import requests
from datetime import datetime
import json
from database_handler import db_handler
import wikipedia

BACKEND_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Multi-Platform App",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-container {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        height: 500px;
        overflow-y: auto;
    }
    .message {
        padding: 10px;
        margin: 5px 0;
        border-radius: 10px;
        max-width: 70%;
    }
    .user-message {
        background-color: #007bff;
        color: white;
        margin-left: auto;
        text-align: right;
    }
    .bot-message {
        background-color: #e9ecef;
        color: #333;
        margin-right: auto;
    }
    .url-form {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

if 'messages' not in st.session_state:
    st.session_state.messages = db_handler.get_all_messages()

if 'submitted_urls' not in st.session_state:
    st.session_state.submitted_urls = db_handler.get_all_urls()

if 'wikipedia_data' not in st.session_state:
    st.session_state.wikipedia_data = None

def process_wikipedia_data(data: dict):
    """Send URL to backend for processing"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/process-data/",
            json=data,
            timeout=30
        )
        return response.json()
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

def send_chat_message(message: str, chat_mode: str):
    """Send chat message and mode to backend for processing"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/chat/",
            json={
                "message": message, 
                "chat_mode": chat_mode,
            },
            timeout=30
        )
        result = response.json()
        if not result.get('success', True):
            return {
                "response": result.get('error_message', 'Backend error occurred'),
                "sources": [], "mode_used": "error", "success": False
            }
        return result
    except requests.exceptions.Timeout:
        return {
            "response": "Request timeout. Please try again.",
            "sources": [], "mode_used": "error", "success": False
        }
    except requests.exceptions.ConnectionError:
        return {
            "response": "Cannot connect to the server. Please check your connection.",
            "sources": [], "mode_used": "error", "success": False
        }
    except Exception as e:
        return {
            "response": f"Unexpected error: {str(e)}",
            "sources": [], "mode_used": "error", "success": False
        }

def get_stats():
    """Get backend statistics"""
    try:
        response = requests.get(f"{BACKEND_URL}/stats/", timeout=10)
        return response.json()
    except:
        return {"stats": {"vectors_count": 0, "points_count": 0}}

def fetch_wikipedia_data(topic: str, lang: str):
    """Fetch Wikipedia data for a given topic"""
    try:
        wikipedia.set_lang(lang)
        search_results = wikipedia.search(topic)
        if not search_results:
            return {"success": False, "message": "No Wikipedia page found for this topic"}
        page_title = search_results[0]
        page = wikipedia.page(page_title)
        content = page.content
        summary = page.summary
        url = page.url
        # images = page.images[:3]
        return {"success": True, "title": page_title,
                "url": url, "summary": summary,
                "content": content,"full_content": f"# {page_title}\n\n{content}",
                # "images": images,  
        }
        
    except wikipedia.exceptions.DisambiguationError as e:
        options = e.options[:5]  # Show first 5 options
        return {"success": False, "message": f"Disambiguation needed. Did you mean: {', '.join(options)}?"}
    
    except wikipedia.exceptions.PageError:
        return {"success": False, "message": "Wikipedia page not found"}
    
    except Exception as e:
        return {"success": False, "message": f"Error fetching data: {str(e)}"}

st.sidebar.title("🚀 Navigation")
app_mode = st.sidebar.radio("Select Platform", ["Chat Agent", "Data Storage", "Statistics", "Database Management"])

st.sidebar.markdown("---")
st.sidebar.subheader("Quick Actions")
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state.messages = db_handler.get_all_messages()
    st.session_state.submitted_urls = db_handler.get_all_urls()
    st.sidebar.success("Data refreshed from database!")

# Main header
st.markdown('<h1 class="main-header">Multi-Platform Application</h1>', unsafe_allow_html=True)

# Chat Platform Tab
if app_mode == "Chat Agent":
    st.header("💬 RAG Chat Agent")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        rag_mode = st.button("🧠 RAG Mode", 
                           help="Use stored Wikipedia knowledge (Retrieval Augmented Generation)",
                           use_container_width=True)
    
    with col2:
        web_mode = st.button("🌐 Web Search", 
                           help="Search the web for current information",
                           use_container_width=True)
    
    with col3:
        deep_mode = st.button("🤔 Think Deep", 
                            help="Use advanced reasoning without external context",
                            use_container_width=True)
    
    if "chat_mode" not in st.session_state:  # default mode to RAG
        st.session_state.chat_mode = "rag"

    if rag_mode:
        st.session_state.chat_mode = "rag"
    if web_mode:
        st.session_state.chat_mode = "web"
    if deep_mode:
        st.session_state.chat_mode = "deep"
    
    mode_colors = {
        "rag": "#4CAF50",    # Green
        "web": "#2196F3",    # Blue
        "deep": "#9C27B0"    # Purple
    }
    mode_labels = {
        "rag": "🧠 RAG Mode",
        "web": "🌐 Web Search",
        "deep": "🤔 Think Deep"
    }
    
    st.markdown(f"""
    <div style="background-color: {mode_colors[st.session_state.chat_mode]}; 
                color: white; 
                padding: 10px; 
                border-radius: 5px; 
                text-align: center;
                margin: 10px 0;
                font-weight: bold;">
        {mode_labels[st.session_state.chat_mode]} • Active
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("ℹ️ Mode Information", expanded=False):
        st.markdown("""
        **🧠 RAG Mode**: Uses your stored Wikipedia knowledge for context-aware responses.  
        **🌐 Web Search**: Searches the Wikipedia for current information with feature of only summary.  
        **🤔 Think Deep**: Uses advanced reasoning without external context for creative responses.
        """)
    chat_container = st.container()
    with chat_container:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for message in st.session_state.messages:
            if message['role'] == 'user':
                mode_indicator = ""
                if message.get('mode'):
                    mode_emoji = {"rag": "🧠", "web": "🌐", "deep": "🤔"}.get(message['mode'], "")
                    mode_indicator = f"<small style='color: #666;'>{mode_emoji} {message['mode'].upper()}</small><br>"
                
                st.markdown(f'''
                <div class="message user-message">
                    <strong>You:</strong><br>
                    {mode_indicator}
                    {message["content"]}
                </div>
                ''', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="message bot-message"><strong>AI:</strong> {message["content"]}</div>', 
                           unsafe_allow_html=True)
                if message.get('sources') and message.get('mode') == 'rag':
                    with st.expander("📚 Sources used (from your knowledge)"):
                        for i, source in enumerate(message['sources']):
                            st.markdown(f"""
                            <div class="source-item">
                                <strong>Source {i+1}:</strong> {source.get('title', 'Unknown')}<br>
                                <strong>Relevance score:</strong> {source.get('score', 0):.3f}<br>
                                <em>{source.get('content', '')[:150]}...</em>
                            </div>
                            """, unsafe_allow_html=True)
                if message.get('web_context') and message.get('mode') == 'web':
                    with st.expander("🌐 Web Search Results"):
                        st.markdown(f"""
                        <div class="source-item">
                            <strong>Web Context:</strong><br>
                            <em>{message['web_context'][:200]}...</em>
                        </div>
                        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([6, 1])
    with col1:
        user_input = st.text_input("Type your message...", key="chat_input", label_visibility="collapsed")
    with col2:
        send_button = st.button("Send", use_container_width=True)
    
    if send_button and user_input:
        st.session_state.messages.append({"role": "user", "content": user_input, "mode": st.session_state.chat_mode})
        with st.spinner("Thinking..."):
            response = send_chat_message(user_input, st.session_state.chat_mode)
            
            # Add AI response
            assistant_message = {
                "role": "assistant",
                "content": response.get('response', 'No response'),
                "mode": st.session_state.chat_mode
            }
            if st.session_state.chat_mode == "rag" and response.get('sources'):
                assistant_message["sources"] = response.get('sources', [])
            if st.session_state.chat_mode == "web" and response.get('web_context'):
                assistant_message["web_context"] = response.get('web_context')
            if st.session_state.chat_mode == "deep" and response.get('reasoning'):
                assistant_message["reasoning"] = response.get('reasoning')
            
            st.session_state.messages.append(assistant_message)
        
        st.rerun()
    
    # Clear chat button
    if st.button("Clear Chat", type="secondary"):
        st.session_state.messages = []
        st.rerun()

########################################### Data Storage ###############################################
elif app_mode == "Data Storage":
    st.header("🌐 Data Storage Platform")
    with st.form("topic_form"):
        st.subheader("Provide A Topic")
        topic = st.text_input("Topic:", placeholder="Data Science",key="topic_input")
        lang_options = {"English": "en", "Spanish": "es","French": "fr",
                        "German": "de","Italian": "it", "Hindi": "hi", "Japanese": "ja",
                        "Chinese (Simplified)": "zh", "Arabic": "ar"}
        lang_display = st.selectbox("Select Language:", list(lang_options.keys()), index=0)
        lang = lang_options.get(lang_display, "en") 
        submitted = st.form_submit_button("Fetch Data", use_container_width=True)
    if submitted and topic and lang:
        with st.spinner(f"Fetching Wikipedia data for '{topic}'..."):
            result = fetch_wikipedia_data(topic, lang)
            
            if result.get('success'):
                st.session_state.wikipedia_data = result
                st.success(f"✅ Successfully fetched data for: {result['title']}")
            else:
                st.error(f"❌ {result.get('message', 'Failed to fetch data')}")
    if st.session_state.wikipedia_data:
        data = st.session_state.wikipedia_data
        st.markdown(f"### 📖 {data['title']}")
        st.markdown(f"**URL:** [{data['url']}]({data['url']})")
        with st.expander("📋 Summary", expanded=True):
            st.markdown(f"<div class='wikipedia-content'>{data['summary']}</div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📄 Full Content")
        sections = data['content'].split('\n\n')
        visible_sections = min(10, len(sections))
        for i, section in enumerate(sections[:visible_sections]):
            if section.strip() and len(section.strip()) > 50:
                with st.expander(f"Section {i+1}", expanded=i < 3):
                    st.markdown(f"<div class='wikipedia-content'>{section}</div>", unsafe_allow_html=True)
        if len(sections) > visible_sections:
            st.info(f"📝 ... and {len(sections) - visible_sections} more sections. Visit the Wikipedia page for full content.")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("💾 Store in Vector DB", use_container_width=True):
                if st.session_state.wikipedia_data:
                    with st.spinner("Storing in vector database..."):
                        wiki_data = st.session_state.wikipedia_data.copy()
                        wiki_data.pop("success", None)
                        wiki_data.pop("full_content", None)
                        result = process_wikipedia_data(wiki_data)
                        if result.get('success'):
                            st.success("✅ Data stored in vector database!")
                        else:
                            st.error("❌ Failed to store data")
        with col2:
            if st.button("🔄 Fetch Another Topic", use_container_width=True):
                st.session_state.wikipedia_data = None
                st.rerun()
        with col3:
            if st.button("🗑️ Clear Data", use_container_width=True, type="secondary"):
                st.session_state.wikipedia_data = None
                st.rerun()
########################################################################################################

######################################## Vector DB Stats ###############################################
elif app_mode == "Statistics":
    st.header("📊 System Statistics")
    
    with st.spinner("Loading statistics..."):
        stats = get_stats()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Vectors", stats.get('stats', {}).get('vectors_count', 0))
    with col2:
        st.metric("Total Chunks", stats.get('stats', {}).get('points_count', 0))
    with col3:
        st.metric("Active Chats", len(st.session_state.messages))
    
    # Backend health check
    try:
        health_response = requests.get(f"{BACKEND_URL}/health/", timeout=5)
        health_data = health_response.json()
        
        st.subheader("🔧 System Health")
        for component, status in health_data.get('components', {}).items():
            status_color = "🟢" if status == "active" else "🔴"
            st.write(f"{status_color} {component}: {status}")
            
    except:
        st.error("❌ Backend server is not reachable")        
########################################################################################################

#################################### Front end Instance DB #############################################
elif app_mode == "Database Management":
    st.header("💾 Database Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Database Actions")
        
        if st.button("🗑️ Clear All Data", type="secondary"):
            if db_handler.clear_all_data():
                st.session_state.messages = []
                st.session_state.submitted_urls = []
                st.success("All data cleared from database!")
        
        if st.button("💾 Create Backup"):
            success, backup_path = db_handler.backup_database()
            if success:
                st.success(f"Backup created: {backup_path}")
            else:
                st.error("Backup failed!")
        
        # Custom backup name
        backup_name = st.text_input("Custom backup name (optional):", placeholder="my_backup.db")
        if st.button("💾 Create Custom Backup"):
            if backup_name:
                if not backup_name.endswith('.db'):
                    backup_name += '.db'
                success, backup_path = db_handler.backup_database(backup_name)
                if success:
                    st.success(f"Backup created: {backup_path}")
                else:
                    st.error("Backup failed!")
    
    with col2:
        st.subheader("Database Information")
        db_info = db_handler.get_database_info()
        
        st.write(f"**Database File:** `{db_info.get('database_file', 'N/A')}`")
        st.write(f"**Directory:** `{db_info.get('databases_directory', 'N/A')}`")
        st.write(f"**Size:** {db_info.get('database_size', 0):.2f} KB")
        st.write(f"**Total Messages:** {db_info.get('total_messages', 0)}")
        st.write(f"**Total URLs:** {db_info.get('total_urls', 0)}")
        st.write(f"**Active URLs:** {db_info.get('active_urls', 0)}")
    
    st.markdown("---")
    st.subheader("📦 Available Backups")
    
    backups = db_handler.list_backups()
    if backups:
        for backup in backups:
            with st.expander(f"📁 {backup['name']} ({backup['size']:.2f} KB)"):
                st.write(f"**Size:** {backup['size']:.2f} KB")
                st.write(f"**Modified:** {backup['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                if st.button(f"🔄 Restore {backup['name']}", key=f"restore_{backup['name']}"):
                    if db_handler.restore_backup(backup['name']):
                        st.session_state.messages = db_handler.get_all_messages()
                        st.session_state.submitted_urls = db_handler.get_all_urls()
                        st.success("Database restored successfully! Refresh to see updated data.")
                    else:
                        st.error("Restore failed!")
    else:
        st.info("No backups available yet. Create a backup using the options above.")

# Footer
st.markdown("---")
st.markdown("### 📊 Stats")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Chat Messages", len([m for m in st.session_state.messages if m['role'] == 'user']))
with col2:
    st.metric("Submitted URLs", len(st.session_state.submitted_urls))
with col3:
    active_urls = len([u for u in st.session_state.submitted_urls if u['status'] == 'Active'])
    st.metric("Active URLs", active_urls)
