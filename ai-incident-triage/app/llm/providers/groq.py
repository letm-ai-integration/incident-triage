from langchain_groq import ChatGroq
from app.config import Settings

def create_groq_llm(settings: Settings) -> ChatGroq:
    """
    Creates and configures a Groq LLM instance.
    """
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not set in the environment or config.")
        
    return ChatGroq(
        api_key=settings.groq_api_key,
        model_name=settings.groq_model_name,
        temperature=0,
        max_tokens=4096,
        max_retries=2,
    )
