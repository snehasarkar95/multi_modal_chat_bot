from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    pipeline
)
from typing import List, Dict, Optional, Tuple
import torch
import math

class LLMChat:

    PREFERRED_LARGE_MODEL = "mistralai/Mistral-7B-Instruct-v0.2"
    MID_MODEL = "tiiuae/falcon-7b-instruct"
    SMALL_MODEL = "HuggingFaceH4/zephyr-7b-alpha"
    def __init__(self):
        self.model_name = None
        self.tokenizer = None
        self.model = None
        self.summarizer = None
        self.device_map = "auto"
        self.load_in_4bit = False
        self.torch_dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

        self._initialize_models()

    def _total_vram_gb(self) -> float:
        if not torch.cuda.is_available():
            return 0.0
        total = 0
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            total += props.total_memory / (1024 ** 3)
        return total
    
    def _pick_model_for_hardware(self) -> Tuple[str, bool]:
        """
        Decide which model to load and whether to use 4-bit based on available VRAM.
        Very rough heuristics:
        - >= 120 GB: 70B in bf16
        - >= 40 GB: 70B in 4-bit
        - >= 24 GB: Mixtral 8x7B in 4-bit
        - else: 8B in 4-bit or fp32 on CPU
        """
        vram = self._total_vram_gb()

        # Prefer the large model if we have enough VRAM
        if vram >= 120:
            return self.PREFERRED_LARGE_MODEL, False  # full precision (bf16)
        if vram >= 40:
            return self.PREFERRED_LARGE_MODEL, True   # 4-bit quantization

        # Next best: Mixtral 8x7B (MoE, very strong)
        if vram >= 24:
            return self.MID_MODEL, True               # 4-bit

        # Otherwise: 8B instruct
        return self.SMALL_MODEL, True if vram > 0 else False
    
    def _build_messages(self, message: str, context: Optional[List[Dict]], chat_mode: str):
        """Use chat template-friendly messages."""
        system_base = "You are a helpful, precise assistant. If unsure, say you don't know."

        if chat_mode == "rag" and context:
            ctx_lines = []
            for item in context:
                title = item.get("title", "Unknown")
                content = item.get("content", "")
                score = item.get("score", 0.0)
                ctx_lines.append(f"[Source: {title} | Relevance: {score:.3f}]\n{content}")
            system = (
                system_base
                + " Use ONLY the following context to answer. "
                  "If the answer isn't in the context, say you don't know.\n\n"
                  "=== CONTEXT START ===\n"
                  + "\n\n".join(ctx_lines[:6])
                  + "\n=== CONTEXT END ==="
            )
        elif chat_mode == "web" and context:
            web_lines = []
            for item in context:
                title = item.get("title", "Web result")
                content = item.get("content", "")
                web_lines.append(f"[{title}]\n{content}")
            system = (
                system_base
                + " Use the following web snippets to answer factually. "
                  "Cite inline with (Source: <title>) when appropriate.\n\n"
                  "=== WEB RESULTS ===\n"
                  + "\n\n".join(web_lines[:8])
            )
        elif chat_mode == "deep":
            system = (
                system_base
                + " Provide a deep, structured analysis. Cover assumptions, alternatives, and edge cases."
            )
        else:
            system = system_base

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": message}
        ]

    def _initialize_models(self):
        """Initialize chat model + summarizer with sensible defaults."""
        try:
            chosen_model, use_4bit = self._pick_model_for_hardware()
            self.model_name = chosen_model
            self.load_in_4bit = use_4bit

            quant_args = {}
            if self.load_in_4bit:
                # Requires bitsandbytes
                quant_args = dict(
                    load_in_4bit=True,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=self.torch_dtype,
                    bnb_4bit_quant_type="nf4",
                )

            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, use_fast=True)
            # ensure pad token
            if self.tokenizer.pad_token_id is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                # device_map=self.device_map,
                torch_dtype=self.torch_dtype,
                low_cpu_mem_usage=True,
                attn_implementation="flash_attention_2" if torch.cuda.is_available() else "eager",
                timeout=None,
                **quant_args
            )

            # Summarizer can stay as BART; it's fast and stable
            self.summarizer = pipeline(
                "summarization",
                model="facebook/bart-large-cnn",
                tokenizer="facebook/bart-large-cnn",
                device=0 if torch.cuda.is_available() else -1
            )

            print(f"✅ Loaded {self.model_name} (4-bit: {self.load_in_4bit})")

        except Exception as e:
            print(f"❌ Error initializing models: {e}")
            raise

    def generate_response(self, message: str, context: Optional[List[Dict]] = None, chat_mode: str = "rag") -> str:
        """
        Generate response using an instruction-tuned chat model with chat templates.
        """
        try:
            messages = self._build_messages(message, context, chat_mode)

            # Use the model's built-in chat template if available
            if hasattr(self.tokenizer, "apply_chat_template"):
                prompt = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
                inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
            else:
                # Fallback: naive concat
                joined = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages]) + "\nASSISTANT:"
                inputs = self.tokenizer(joined, return_tensors="pt").to(self.model.device)

            gen_kwargs = {
                "max_new_tokens": 512 if chat_mode != "deep" else 1024,
                "temperature": 0.7 if chat_mode != "deep" else 0.6,
                "top_p": 0.9,
                "repetition_penalty": 1.05,
                "do_sample": True,
                "pad_token_id": self.tokenizer.eos_token_id
            }

            with torch.no_grad():
                outputs = self.model.generate(**inputs, **gen_kwargs)

            # Slice only the generated tail, not the prompt
            generated = outputs[0][inputs["input_ids"].shape[-1]:]
            response = self.tokenizer.decode(generated, skip_special_tokens=True).strip()

            # Optional: light cleanup (no line chopping)
            response = response.replace("\u200b", "").strip()

            # Add basic attribution for RAG
            if chat_mode == "rag" and context:
                titles = [c.get("title", "Source") for c in context[:3]]
                response += f"\n\nSources: " + "; ".join(dict.fromkeys(titles))

            return response or "I don't have enough information to answer that question."

        except Exception as e:
            print(f"Error generating response in {chat_mode} mode: {e}")
            return self._get_fallback_response(chat_mode, message)

    # Keep your existing helper methods, with safer cleaning
    def _get_fallback_response(self, chat_mode: str, message: str) -> str:
        fallbacks = {
            "rag": f"I’m having trouble accessing my knowledge base for '{message}'.",
            "web": f"I’m having trouble using the web snippets for '{message}'.",
            "deep": f"I’m having trouble performing deep analysis on '{message}'."
        }
        return fallbacks.get(chat_mode, "I’m having technical difficulties. Please try again.")

    def summarize_content(self, content: str, max_length: int = 150) -> str:
        try:
            if len(content) > 4000:
                content = content[:4000] + "..."
            summary = self.summarizer(content, max_length=max_length, min_length=30, do_sample=False)
            return summary[0]["summary_text"]
        except Exception:
            return content[:200] + "..." if len(content) > 200 else content

    def cleanup(self):
        try:
            if hasattr(self, 'model'):
                del self.model
            if hasattr(self, 'tokenizer'):
                del self.tokenizer
            if hasattr(self, 'summarizer'):
                del self.summarizer
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("✅ LLM resources cleaned up")
        except Exception as e:
            print(f"Error during cleanup: {e}")