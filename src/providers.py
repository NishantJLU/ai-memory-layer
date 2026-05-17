import os
from dotenv import load_dotenv

load_dotenv()

# We lazily import providers to avoid loading heavy local models if not needed
_local_embedding_model = None


def get_embedding_provider():
    return os.getenv("EMBEDDING_PROVIDER", "openai").lower()


def get_llm_provider():
    return os.getenv("LLM_PROVIDER", "openai").lower()


def get_embedding(text: str) -> list[float]:
    provider = get_embedding_provider()

    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.embeddings.create(input=text, model="text-embedding-3-small")
        return response.data[0].embedding

    elif provider == "local":
        global _local_embedding_model
        if _local_embedding_model is None:
            from sentence_transformers import SentenceTransformer
            # 384-dimensional fast model
            _local_embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        # sentence_transformers returns a numpy array, we need a list of floats
        return _local_embedding_model.encode(text).tolist()

    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")


def generate_summary(prompt: str, system_prompt: str = "You are an AI assistant.") -> str:
    provider = get_llm_provider()

    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()

    elif provider == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
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
        from openai import OpenAI
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        try:
            response = client.chat.completions.create(
                model="llama3",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error connecting to local LLM: {e}. Please ensure Ollama is running."
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
