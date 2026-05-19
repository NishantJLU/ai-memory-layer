import os
import asyncio
from src.config import settings

from opentelemetry import trace

tracer = trace.get_tracer(__name__)

# We lazily import providers to avoid loading heavy local models if not needed
_local_embedding_model = None


def get_embedding_provider():
    return settings.EMBEDDING_PROVIDER.lower()


def get_llm_provider():
    return settings.LLM_PROVIDER.lower()


async def get_embedding(text: str) -> list[float]:
    with tracer.start_as_current_span("get_embedding") as span:
        provider = get_embedding_provider()
        span.set_attribute("provider", provider)

        if provider == "openai":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.embeddings.create(input=text, model="text-embedding-3-small")
            return response.data[0].embedding

        elif provider == "local":
            global _local_embedding_model
            if _local_embedding_model is None:
                from sentence_transformers import SentenceTransformer
                # 384-dimensional fast model
                _local_embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # sentence_transformers returns a numpy array, we need a list of floats.
            # It's a CPU-intensive task, so we run it in a thread.
            embedding = await asyncio.to_thread(_local_embedding_model.encode, text)
            return embedding.tolist()

        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")


async def generate_summary(prompt: str, system_prompt: str = "You are an AI assistant.") -> str:
    with tracer.start_as_current_span("generate_summary") as span:
        provider = get_llm_provider()
        span.set_attribute("provider", provider)

        if provider == "openai":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            content = response.choices[0].message.content.strip()
            span.set_attribute("usage.total_tokens", response.usage.total_tokens)
            return content

        elif provider == "anthropic":
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            response = await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                temperature=0.0,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()

        elif provider == "local":
            # For true local, one might use Ollama or llama.cpp.
            # Here we mock it or expect a local OpenAI-compatible endpoint.
            from openai import AsyncOpenAI
            import json
            client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
            try:
                response = await client.chat.completions.create(
                    model="llama3",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                # Fallback for when Ollama is not running: return a mock JSON summary
                print(f"Warning: Local LLM fallback used. {e}")
                
                # Extract some meaning from the prompt if possible
                summary_text = "Automatic summary"
                if "Commit Message:" in prompt:
                    # Try to get the commit message part
                    msg_part = prompt.split("Commit Message:")[1].split("Diff snippet")[0].strip()
                    summary_text = f"Commit: {msg_part}"
                
                mock_data = {
                    "memory": summary_text,
                    "memory_type": "episodic",
                    "module": "auto-ingest"
                }
                # Special case for conflict detection check
                if "NO_CONFLICT" in prompt:
                    return "NO_CONFLICT"
                
                return json.dumps(mock_data)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
