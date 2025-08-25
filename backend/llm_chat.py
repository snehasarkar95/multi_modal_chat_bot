from typing import List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
import os
from dotenv import load_dotenv

class LLMChat:
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.3):
        """
        Initialize with OpenAI API. Requires `OPENAI_API_KEY` in env.
        """
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("❌ Missing OPENAI_API_KEY in environment.")

        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)

        # Pre-build prompt templates for different modes
        self.base_system = "You are a helpful, precise assistant. If unsure, say you don't know."

        self.prompt_rag = ChatPromptTemplate.from_messages([
            ("system", self.base_system + " Use ONLY the provided context to answer. "
             "If the answer isn't in the context, say you don't know.\n"
             "=== CONTEXT START ===\n{context}\n=== CONTEXT END ==="),
            ("user", "{question}"),
            MessagesPlaceholder("history")
        ])

        self.prompt_web = ChatPromptTemplate.from_messages([
            ("system", self.base_system + " Use the following web snippets to answer factually. "
             "Cite inline with (Source: <title>) when appropriate.\n"
             "=== WEB RESULTS ===\n{context}"),
            ("user", "{question}"),
            MessagesPlaceholder("history")
        ])

        self.prompt_deep = ChatPromptTemplate.from_messages([
            ("system", self.base_system + " Provide a deep, structured analysis. "
             "Cover assumptions, alternatives, and edge cases."),
            ("user", "{question}"),
            MessagesPlaceholder("history")
        ])

        self.prompt_general = ChatPromptTemplate.from_messages([
            ("system", self.base_system),
            ("user", "{question}"),
            MessagesPlaceholder("history")
        ])

        # LangChain chains
        self.chain_rag = LLMChain(llm=self.llm, prompt=self.prompt_rag)
        self.chain_web = LLMChain(llm=self.llm, prompt=self.prompt_web)
        self.chain_deep = LLMChain(llm=self.llm, prompt=self.prompt_deep)
        self.chain_general = LLMChain(llm=self.llm, prompt=self.prompt_general)

        print(f"✅ OpenAI model {self.model_name} initialized with LangChain.")

    def _format_context(self, context: Optional[List[Dict]], chat_mode: str) -> str:
        """Prepare context text for RAG/web modes."""
        if not context:
            return ""

        if chat_mode == "rag":
            ctx_lines = []
            for item in context[:6]:
                title = item.get("title", "Unknown")
                content = item.get("content", "")
                score = item.get("score", 0.0)
                ctx_lines.append(f"[Source: {title} | Relevance: {score:.3f}]\n{content}")
            return "\n\n".join(ctx_lines)

        if chat_mode == "web":
            web_lines = []
            for item in context[:8]:
                title = item.get("title", "Web result")
                content = item.get("content", "")
                web_lines.append(f"[{title}]\n{content}")
            return "\n\n".join(web_lines)

        return ""

    def generate_response(self, message: str, context: Optional[List[Dict]] = None, 
                          chat_mode: str = "rag", history: Optional[List[Dict]] = None) -> str:
        """Generate response using OpenAI LLM with mode-specific guardrails."""
        try:
            context_text = self._format_context(context, chat_mode)
            inputs = {
                "question": message,
                "context": context_text,
                "history": history or []
            }

            if chat_mode == "rag":
                return self.chain_rag.run(inputs).strip()
            elif chat_mode == "web":
                return self.chain_web.run(inputs).strip()
            elif chat_mode == "deep":
                return self.chain_deep.run(inputs).strip()
            else:
                return self.chain_general.run(inputs).strip()

        except Exception as e:
            return f"❌ Error generating response: {e}"

    def summarize_content(self, content: str, max_length: int = 150) -> str:
        """Lightweight summarization via GPT."""
        try:
            if len(content) > 4000:
                content = content[:4000] + "..."
            summary_prompt = (
                f"Summarize the following text in under {max_length} words:\n\n{content}"
            )
            return self.chain_general.run({"question": summary_prompt, "history": []}).strip()
        except Exception:
            return content[:200] + "..." if len(content) > 200 else content

    def cleanup(self):
        """No GPU cleanup needed for API mode."""
        print("✅ API-based LLM requires no cleanup.")
