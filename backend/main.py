from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import uvicorn
import wikipedia
from wikipedia_processor import WikipediaProcessor
from vector_store import VectorStore
from llm_chat import LLMChat
import logging
from fetch_web_context import format_web_context
from web_search_manager import web_search_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Wikipedia Chat API", version="1.0.0")
session_histories: Dict[str, LLMChat] = {}

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:7001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
wikipedia_processor = WikipediaProcessor()
vector_store = VectorStore()
llm_chat = LLMChat()

# Pydantic models
class WikiRequest(BaseModel):
    title: str
    url: str
    summary: str
    content: str

class ChatRequest(BaseModel):
    message: str
    chat_mode: str = "rag"
    use_context: bool = True 
    session_id: Optional[str] = "default" 

class ChatResponse(BaseModel):
    response: str
    sources: List[dict] = []
    web_context: str = ""
    reasoning: str = ""
    mode_used: str = "rag"
    fallback_used: bool = False
    original_mode: str = "rag"
    success: bool = True
    error_message: str = ""

class WikiResponse(BaseModel):
    success: bool
    message: str
    title: Optional[str] = None
    chunks_count: Optional[int] = None

# API endpoints
@app.post("/process-data/", response_model=WikiResponse)
async def process_data(request: WikiRequest):
    """Process Wikipedia data and store in vector database"""
    try:
        request_dict = request.dict()
        success = vector_store.store_document(request_dict)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store document in vector database")
        stats = vector_store.get_collection_stats()
        return WikiResponse(
            success=True,
            message="Data processed successfully",
            title=request.title,
            chunks_count=stats.get("points_count", 0)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with LLM using different modes with fallback mechanisms"""
    try:
        session_id = request.session_id or "default"
        if session_id not in session_histories:
            session_histories[session_id] = LLMChat(history_window=5)  # keep last 5 turns
        llm_chat = session_histories[session_id]

        sources = []
        web_context = ""
        reasoning = ""
        fallback_used = False
        original_mode = request.chat_mode

        if request.chat_mode not in ["rag", "web", "deep"]:
            request.chat_mode = "rag"  # Default RAG
            logger.warning(f"Invalid chat mode '{request.chat_mode}', defaulting to RAG")
        
        response = ""
        mode_used = request.chat_mode
        
        try:
            # --------------------------
            # ✅ RAG mode
            # --------------------------
            if request.chat_mode == "rag":
                sources = vector_store.search_similar(request.message, limit=3)
                if sources and any(source.get('score', 0) > 0.3 for source in sources):
                    logger.info(f"RAG mode: Found {len(sources)} relevant sources")
                    response = llm_chat.generate_response(request.message, sources, "rag")
                else:
                    fallback_used = True
                    mode_used = "web"
                    logger.warning(f"RAG fallback: Insufficient results for '{request.message}', falling back to web search")

            # --------------------------
            # ✅ Web mode
            # --------------------------        
            if request.chat_mode == "web" or (fallback_used and mode_used == "web"):
                try:
                    web_results = await web_search_manager.combined_web_search(request.message)
                    if web_results:
                        logger.info(f"Web mode: Found {len(web_results)} combined results for '{request.message}'")
                        
                        # Format web context for LLM
                        web_context = format_web_context(web_results)
                        # Generate response using web results as context
                        response = llm_chat.generate_response(
                            request.message,
                            web_results,  # Pass results as context
                            "web"
                        )
                    else:
                        fallback_used = True
                        mode_used = "deep"
                        logger.warning(f"Web fallback: No web results for '{request.message}', falling back to deep research")
                
                except Exception as e:
                    fallback_used = True
                    mode_used = "deep"
                    logger.error(f"Web search error for '{request.message}': {e}, falling back to deep research")
            
            # --------------------------
            # ✅ Deep mode
            # --------------------------
            if request.chat_mode == "deep" or (fallback_used and mode_used == "deep"):
                reasoning = "Engaging in comprehensive analysis without external data sources...\n"
                logger.info(f"Deep mode: Processing '{request.message}' with chain of thought")
                reasoning_response = llm_chat.generate_response(request.message, None, "deep")
                # reasoning += reasoning_response
                response = reasoning_response.split("Final Response:")[-1] if "Final Response:" in reasoning_response else reasoning_response
                if fallback_used and original_mode != "deep":
                    response = f"🔍 Note: I couldn't find specific information in my knowledge base, so I'm providing a general analysis:\n\n{response}"
        except Exception as inner_e:
            response = f"I apologize, but I encountered an issue while processing your request. Please try again or rephrase your question. Error: {str(inner_e)}"
            mode_used = "error"
        result = ChatResponse(
            response=response, 
            sources=sources if mode_used == "rag" else [],
            web_context=web_context if mode_used == "web" else "",
            reasoning=reasoning if mode_used == "deep" else "",
            mode_used=mode_used,
            fallback_used=fallback_used,
            original_mode=original_mode
        )
        if fallback_used and original_mode != mode_used:
            fallback_message = f"\n\n⚠️ Note: I used {mode_used.upper()} mode instead of {original_mode.upper()} because "
            if original_mode == "rag":
                fallback_message += "I couldn't find relevant information in my knowledge base."
            elif original_mode == "web":
                fallback_message += "I couldn't find web results for your query."
            result.response = result.response + fallback_message
        logger.info(f"Chat completed: mode={mode_used}, fallback={fallback_used}, original={original_mode}")
        return result
    except Exception as e:
        logger.error(f"Chat API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/clear/{session_id}")
async def clear_chat_session(session_id: str = "default"):
    """Clear chat history for a specific session"""
    try:
        if session_id in session_histories:
            del session_histories[session_id]
            logger.info(f"Cleared session history for session_id: {session_id}")
            return {"success": True, "message": f"Session {session_id} cleared"}
        else:
            return {"success": False, "message": f"Session {session_id} not found"}
    except Exception as e:
        logger.error(f"Error clearing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/")
async def get_stats():
    """Get vector database statistics"""
    try:
        stats = vector_store.get_collection_stats()
        return {"stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "components": {
        "wikipedia_processor": "active",
        "vector_store": "active",
        "llm_chat": "active" if llm_chat.is_healthy() else "inactive"
    }}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7002)