import streamlit as st
import requests
from datetime import datetime
import json
from database_handler import db_handler
import wikipedia
import os
import tempfile
from pathlib import Path
import PyPDF2
import docx
import pandas as pd
from PIL import Image
import io
import docprocessor
import mimetypes

BACKEND_URL = "http://localhost:7002"

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
        border-radius: 10px;
        margin-bottom: 10px;
        line-height: 1.4;
        color: #262730 !important; /* Dark text color */
    }
    .user-message {
        background-color: #e6f7ff;
        border-left: 5px solid #1890ff;
    }
    .bot-message {
        background-color: #f9f9f9;
        border-left: 5px solid #52c41a;
    }
    .stContainer {
        padding-bottom: 20px;
    }
    .stTextInput input {
    color: #262730 !important;
    background-color: white !important;
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
app_mode = st.sidebar.radio("Select Platform", ["Chat Agent", "Data Storage", "Statistics", "Data Upload"])#, "Database Management"])

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
    st.sidebar.subheader("Chat Agent Modes")
    chat_mode = st.sidebar.radio(
        "Choose Mode",
        ["🧠 RAG Mode", "🌐 Web Search", "🤔 Think Deep"],
        index=0
    )
    # Map sidebar selection to session_state.chat_mode
    mode_mapping = {
        "🧠 RAG Mode": "rag",
        "🌐 Web Search": "web",
        "🤔 Think Deep": "deep"
    }
    st.session_state.chat_mode = mode_mapping[chat_mode]
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
    chat_container = st.container(height=400)
    with chat_container:
        # st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for message in st.session_state.messages:
            if message['role'] == 'user':
                st.markdown(f'<div class="message user-message"><strong>You:</strong> {message["content"]}</div>', 
                           unsafe_allow_html=True)
            else:
                content = message["content"]
                if message.get("mode") == "rag" and message.get("sources"):
                    source_list = message.get('sources', [])
                    if source_list and isinstance(source_list[0], dict):
                        sources_formatted = []
                        for source in source_list:
                            topic = source.get("metadata", "Unknown").get("Header 2", "Unknown")
                            confidence = source.get("score", "Unknown")
                            source_name = source.get("url", "Unknown")
                            sources_formatted.append(f"- Topic: {topic} | Confidence: {confidence} | Source: {source_name}")

                        content += "\n\n**Sources:**\n" + "\n".join(sources_formatted)
                    else:
                        content += f"\n\n**Sources:** {', '.join(str(s) for s in source_list)}"
                
                # Add web context for Web Search mode
                if message.get("mode") == "web" and message.get("web_context"):
                    content += f"\n\n*Web Context: {message.get('web_context')}*"
                
                # Add reasoning for Think Deep mode
                if message.get("mode") == "deep" and message.get("reasoning"):
                    content += f"\n\n*Reasoning: {message.get('reasoning')}*"
                
                st.markdown(f'<div class="message bot-message"><strong>Bot:</strong> {content}</div>', 
                           unsafe_allow_html=True)
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
        try:
            st.session_state.messages = []
            session_id = "default"
            response = requests.post(f"http://localhost:8000/chat/clear/{session_id}")
            if response.status_code == 200:
                st.success("Chat cleared successfully!")
            else:
                st.warning("Frontend chat cleared, but there was an issue with the backend.")
        except Exception as e:
            st.error(f"Error clearing chat: {e}")
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
########################################################################################################

#################################### Data Upload #######################################################
elif app_mode ==  "Data Upload":
    st.header("📁 Data Upload Platform")

    mimetypes.init() # Initializing mimetypes

    supported_file_types = {
        "Text Documents": {
            "extensions": ["docx", "doc", "pdf", "txt", "md", "rtf", "odt"],
            "description": "Word documents, PDFs, text files, Markdown, RTF, and OpenDocument Text",
            "mime_types": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                          "application/msword", 
                          "application/pdf", 
                          "text/plain", 
                          "text/markdown", 
                          "application/rtf", 
                          "application/vnd.oasis.opendocument.text"]
        },
        "Spreadsheets": {
            "extensions": ["xlsx", "xls", "csv", "ods"],
            "description": "Excel files, CSV, and OpenDocument Spreadsheets",
            "mime_types": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          "application/vnd.ms-excel",
                          "text/csv",
                          "application/vnd.oasis.opendocument.spreadsheet"]
        },
        "Presentations": {
            "extensions": ["pptx", "odp"],
            "description": "PowerPoint presentations and OpenDocument Presentations",
            "mime_types": ["application/vnd.openxmlformats-officedocument.presentationml.presentation",
                          "application/vnd.oasis.opendocument.presentation"]
        },
        "Images": {
            "extensions": ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"],
            "description": "Common image formats for visual content",
            "mime_types": ["image/jpeg", "image/png", "image/gif", "image/bmp", "image/tiff", "image/webp"]
        },
        "Structured Data": {
            "extensions": ["json", "xml", "yaml", "yml"],
            "description": "JSON, XML, and YAML files for structured data",
            "mime_types": ["application/json", "application/xml", "text/x-yaml", "application/x-yaml"]
        },
        "Code & Logs": {
            "extensions": ["py", "js", "java", "c", "cpp", "html", "css", "log", "txt"],
            "description": "Source code files and log files",
            "mime_types": ["text/x-python", "application/javascript", "text/x-java", "text/x-c", "text/x-c++", 
                          "text/html", "text/css", "text/plain"]
        },
        "Research Articles": {
            "extensions": ["pdf", "docx", "tex"],
            "description": "Academic papers and research documents",
            "mime_types": ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
                          "application/x-tex"]
        },
        "Large Files": {
            "extensions": ["zip", "tar", "gz", "7z", "rar"],
            "description": "Archived files for batch processing",
            "mime_types": ["application/zip", "application/x-tar", "application/gzip", "application/x-7z-compressed", 
                          "application/x-rar-compressed"]
        }
    }
    with st.expander("📋 Supported File Formats (Up to 1GB)", expanded=False):
        st.info("💡 Large files may take longer to process. Progress indicators will show processing status.")
        for category, info in supported_file_types.items():
            st.markdown(f"**{category}**")
            st.markdown(f"*{info['description']}*")
            st.markdown(f"Extensions: `{', '.join(info['extensions'])}`")
            st.markdown(f"MIME Types: `{', '.join(info['mime_types'])}`")
            st.markdown("---")
    
    st.markdown("---")
    uploaded_files = st.file_uploader(
        "Drop any file", 
        accept_multiple_files=True,
        help="Upload documents to process and store in the knowledge base"
    )
    
    if uploaded_files:
        st.subheader("📄 Uploaded Files")
        file_tabs = st.tabs([f"{i+1}. {file.name}" for i, file in enumerate(uploaded_files)])
        if 'processed_files' not in st.session_state:
            st.session_state.processed_files = {}
            st.session_state.preview_data = {}
            st.session_state.file_info = {}

        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.file_info:
                file_content = uploaded_file.getvalue()
                mime_type, extension = docprocessor.detect_file_type(file_content, uploaded_file.name)
                category = docprocessor.categorize_file(mime_type, extension, supported_file_types)
                
                st.session_state.file_info[uploaded_file.name] = {
                    "mime_type": mime_type,
                    "extension": extension,
                    "category": category
                }
                uploaded_file.seek(0)   

        for i, (uploaded_file, tab) in enumerate(zip(uploaded_files, file_tabs)):
            with tab:
                file_info = st.session_state.file_info[uploaded_file.name]
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**File Name:** {uploaded_file.name}")
                    st.write(f"**Detected MIME Type:** {file_info['mime_type']}")
                    st.write(f"**File Extension:** {file_info['extension']}")
                    st.write(f"**File Size:** {uploaded_file.size / 1024:.2f} KB")
                    st.write(f"**Category:** {file_info['category']}")
                with col2:
                    process_key = f"process_{i}"
                    if st.button("⚙️ Process", key=process_key, use_container_width=True):
                        with st.spinner(f"Processing {uploaded_file.name}..."):
                            try:
                                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                                    tmp_file.write(uploaded_file.getvalue())
                                    tmp_path = tmp_file.name
                                processing_result, preview = docprocessor.process_uploaded_file(tmp_path, uploaded_file.name, file_info['extension'], file_info['mime_type'])
                                st.session_state.processed_files[uploaded_file.name] = processing_result
                                st.session_state.preview_data[uploaded_file.name] = preview
                                os.unlink(tmp_path)
                                st.success(f"✅ {uploaded_file.name} processed successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error processing {uploaded_file.name}: {str(e)}")
                if uploaded_file.name in st.session_state.processed_files:
                    file_data = st.session_state.processed_files[uploaded_file.name]
                    preview = st.session_state.preview_data[uploaded_file.name]
                    st.markdown("---")
                    st.markdown("### 📊 Processing Results")
                    # Display metadata
                    if file_data.get("metadata"):
                        with st.expander("📋 Metadata"):
                            st.json(file_data["metadata"])
                    if file_data["type"] in ["text", "document", "code", "log"] and file_data.get("content"):
                        preview_content = file_data["content"]
                        if len(preview_content) > 2000:
                            preview_content = preview_content[:2000] + "..."
                        
                        st.text_area("Extracted Content", 
                                    value=preview_content,
                                    height=250,
                                    key=f"content_{i}")
                    
                    elif file_data["type"] == "spreadsheet" and preview is not None:
                        st.write("**Data Preview:**")
                        st.dataframe(preview)
                        st.write(f"**Shape:** {file_data['metadata']['total_rows']} rows × {file_data['metadata']['total_columns']} columns")
                    
                    elif file_data["type"] == "image" and file_data.get("metadata"):
                        st.write(f"**Image Dimensions:** {file_data['metadata'].get('width', 'N/A')} × {file_data['metadata'].get('height', 'N/A')}")
                        st.write(f"**Format:** {file_data['metadata'].get('format', 'N/A')}")
                    
                    elif file_data["type"] == "structured_data" and file_data.get("content"):
                        try:
                            if isinstance(file_data["content"], (dict, list)):
                                st.json(file_data["content"])
                            else:
                                parsed_content = json.loads(file_data["content"])
                                st.json(parsed_content)
                        except:
                            st.text_area("Content", value=file_data["content"], height=250)
        st.markdown("---")
        st.subheader("🔄 Batch Operations")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⚙️ Process All Files", use_container_width=True):
                with st.spinner("Processing all files..."):
                    for i, uploaded_file in enumerate(uploaded_files):
                        try:
                            if uploaded_file.name not in st.session_state.processed_files:
                                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                                    tmp_file.write(uploaded_file.getvalue())
                                    tmp_path = tmp_file.name
                                
                                file_info = st.session_state.file_info[uploaded_file.name]
                                processing_result, preview = docprocessor.process_uploaded_file(
                                    tmp_path, 
                                    uploaded_file.name, 
                                    file_info['extension'],
                                    file_info['mime_type']
                                )
                                
                                st.session_state.processed_files[uploaded_file.name] = processing_result
                                st.session_state.preview_data[uploaded_file.name] = preview
                                os.unlink(tmp_path)
                        
                        except Exception as e:
                            st.error(f"Error processing {uploaded_file.name}: {str(e)}")
                    
                    st.success("All files processed!")
                    st.rerun()
        
        with col2:
            if st.button("🗑️ Clear All Processing", type="secondary", use_container_width=True):
                st.session_state.processed_files = {}
                st.session_state.preview_data = {}
                st.session_state.file_info = {}
                st.rerun()
    
    else:
        st.info("👆 Upload files using the file uploader above to get started")

# Footer
st.markdown("---")
st.markdown("### 📊 Stats")
# col1, col2, col3 = st.columns(3)
# with col1:
st.metric("Chat Messages", len([m for m in st.session_state.messages if m['role'] == 'user']))
# with col2:
#     st.metric("Submitted URLs", len(st.session_state.submitted_urls))
# with col3:
#     active_urls = len([u for u in st.session_state.submitted_urls if u['status'] == 'Active'])
#     st.metric("Active URLs", active_urls)
