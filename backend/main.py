from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import wikipedia
from wikipedia_processor import WikipediaProcessor
from vector_store import VectorStore
from llm_chat import LLMChat
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Initialize FastAPI app
app = FastAPI(title="Wikipedia Chat API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit frontend
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
            if request.chat_mode == "rag":
                sources = vector_store.search_similar(request.message, limit=3)
                if sources and any(source.get('score', 0) > 0.3 for source in sources):
                    logger.info(f"RAG mode: Found {len(sources)} relevant sources")
                    response = llm_chat.generate_response(request.message, sources, "rag")
                else:
                    fallback_used = True
                    mode_used = "web"
                    logger.warning(f"RAG fallback: Insufficient results for '{request.message}', falling back to web search")
                    
            if request.chat_mode == "web" or (fallback_used and mode_used == "web"):
                try:
                    search_results = wikipedia.search(request.message)
                    if search_results:
                        page_title = search_results[0]
                        logger.info(f"Web mode: Found Wikipedia page '{page_title}' for '{request.message}'")
                        page = wikipedia.page(page_title, auto_suggest=False)
                        summary = page.summary
                        web_context = f"Wikipedia page: {page_title}\n\n{summary[:500]}..."
                        
                        response = llm_chat.generate_response(
                            f"Based on this Wikipedia content: {summary[:1000]}...\n\nQuestion: {request.message}",
                            None, "web"
                        )
                    else:
                        fallback_used = True
                        mode_used = "deep"
                        logger.warning(f"Web fallback: No Wikipedia results for '{request.message}', falling back to deep research")
                
                except wikipedia.exceptions.DisambiguationError as e:
                    options = e.options[:3]
                    web_context = f"Disambiguation needed. Options: {', '.join(options)}"
                    response = f"I found multiple possible topics for '{request.message}'. Did you mean: {', '.join(options)}?"
                    logger.info(f"Web mode: Disambiguation needed for '{request.message}'")
                
                except wikipedia.exceptions.PageError:
                    fallback_used = True
                    mode_used = "deep"
                    logger.warning(f"Web fallback: Page not found for '{request.message}', falling back to deep research")
                
                except Exception as e:
                    fallback_used = True
                    mode_used = "deep"
                    logger.error(f"Web search error for '{request.message}': {e}, falling back to deep research")
            
            if request.chat_mode == "deep" or (fallback_used and mode_used == "deep"):
                reasoning = "Engaging in comprehensive analysis without external data sources...\n"
                logger.info(f"Deep mode: Processing '{request.message}' with chain of thought")
                cot_prompt = f"""Analyze the following query deeply and provide a well-reasoned response:

Query: {request.message}

Please follow this thought process:
1. Understand the core concept and context
2. Break down the query into key components
3. Apply logical reasoning and critical thinking
4. Consider multiple perspectives if applicable
5. Provide a comprehensive, insightful response

Reasoning:"""
                reasoning_response = llm_chat.generate_response(cot_prompt, None, "deep")
                reasoning += reasoning_response
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
        "llm_chat": "active" if llm_chat.model else "inactive"
    }}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)