from typing import List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
import os
from dotenv import load_dotenv

class LLMChat:
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.8, history_window: int = 5):
        """
        Initialize with OpenAI API. Requires `OPENAI_API_KEY` in env.
        """
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("❌ Missing OPENAI_API_KEY in environment.")

        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)

        self.history: List[Dict[str, str]] = []   # store conversation history
        self.history_window = history_window      # how many turns to keep

        # Pre-build prompt templates for different modes
        self.base_system = "You are a helpful, precise assistant. If unsure, say you don't know."

        self.prompt_rag = ChatPromptTemplate.from_messages([
            ("system", self.base_system + " Use the provided context to answer. "
             "If the answer isn't in the context, say you don't know.\n"
             "=== CONTEXT START ===\n{context}\n=== CONTEXT END ==="),
            ("user", "{question}"),
            MessagesPlaceholder("history")
        ])

        self.prompt_web = ChatPromptTemplate.from_messages([
            ("system", self.base_system + " Use the following web snippets to provide a clear, well-structured, and detailed answer. "
       "Summarize and synthesize the information so the user understands the topic thoroughly. "
       "Do not include citations or references to sources. "
       "Focus on clarity, completeness, and easy-to-follow explanations.\n"
             "=== WEB RESULTS ===\n{context}"),
            ("user", "{question}"),
            MessagesPlaceholder("history")
        ])

        self.prompt_deep = ChatPromptTemplate.from_messages([
            ("system", self.base_system +  " Provide a thoughtful, structured, and insightful response. "
             "Consider different perspectives and implications. "
             "Do NOT reveal your internal reasoning or step-by-step thinking. "
             "Only output the final polished response."),
            MessagesPlaceholder("history"),
            ("user", "{question}")
        ])

        self.prompt_general = ChatPromptTemplate.from_messages([
            ("system", self.base_system),
            ("user", "{question}"),
            MessagesPlaceholder("history")
        ])

        self.chain_rag = (
            RunnablePassthrough.assign(
                context=lambda x: self._format_context(x.get("context", []), "rag"),
                question=lambda x: x["question"],
                history=lambda x: x.get("history", [])
            )
            | self.prompt_rag | self.llm | StrOutputParser()
        )

        self.chain_web = (
            RunnablePassthrough.assign(
                context=lambda x: self._format_context(x.get("context", []), "web"),
                question=lambda x: x["question"],
                history=lambda x: x.get("history", [])
            )
            | self.prompt_web | self.llm | StrOutputParser()
        )

        self.chain_deep = (
            RunnablePassthrough.assign(
                question=lambda x: x["question"],
                history=lambda x: x.get("history", [])
            )| self.prompt_deep | self.llm | StrOutputParser()
        )

        self.chain_general = (
            RunnablePassthrough.assign(
                question=lambda x: x["question"],
                history=lambda x: x.get("history", [])
            )
            | self.prompt_general | self.llm | StrOutputParser()
        )

        print(f"✅ OpenAI model {self.model_name} initialized with LangChain (RunnableSequence).")
    
    def _update_history(self, role: str, content: str):
        """Keep rolling chat history of last N exchanges."""
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.history_window * 2:
            self.history = self.history[-self.history_window * 2:]

    def _format_context(self, context: Optional[List[Dict]], chat_mode: str) -> str:
        """Prepare context text for RAG/web modes."""
        if not context:
            return ""
        if not isinstance(context, list):
            return ""
        ctx_lines = []
        if chat_mode == "rag":
            ctx_lines = []
            for item in context[:6]:
                if isinstance(item, dict):
                    title = item.get("title", "Unknown")
                    content = item.get("content", "")
                    score = item.get("score", 0.0)
                    ctx_lines.append(f"[Source: {title} | Relevance: {score:.3f}]\n{content}")
                elif isinstance(item, str):
                    ctx_lines.append(f"[Source: Unknown]\n{item}")
        elif chat_mode == "web":
            for item in context[:8]:
                if isinstance(item, dict):
                    title = item.get("title", "Web result")
                    content = item.get("content", "")
                    ctx_lines.append(f"[{title}]\n{content}")
                elif isinstance(item, str):
                    ctx_lines.append(f"[Web result]\n{item}")
        return "\n\n".join(ctx_lines)

    def generate_response(self, message: str, context: Optional[List[Dict]] = None, 
                          chat_mode: str = "rag") -> str:
        """Generate response using OpenAI LLM with mode-specific guardrails."""
        try:
            if context is None:
                context = []
            elif isinstance(context, str):
                context = [{"content": context, "title": "Context", "score": 0.0}]
            elif not isinstance(context, list):
                context = []
            inputs = {"question": message,"context": context,"history": self.history}
            if chat_mode == "rag":
                output = self.chain_rag.invoke(inputs)
            elif chat_mode == "web":
                output = self.chain_web.invoke(inputs)
            elif chat_mode == "deep":
                inputs["history"] = self.history[-self.history_window*2:]
                output = self.chain_deep.invoke(inputs)
            else:
                output = self.chain_general.invoke(inputs)
            
            self._update_history("user", message)
            self._update_history("assistant", output)
            return output
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
            result = self.chain_general.invoke({
                "question": summary_prompt,
                "history": []
            })
            
            return result.strip()
        except Exception:
            return content[:200] + "..." if len(content) > 200 else content

    def cleanup(self):
        """No GPU cleanup needed for API mode."""
        print("✅ API-based LLM requires no cleanup.")

    def is_healthy(self) -> bool:
        """Check if the LLM component is healthy"""
        return self.llm is not None
