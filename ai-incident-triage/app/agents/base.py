import os
from abc import ABC, abstractmethod
from typing import Any, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from app.utils.logger import get_logger

logger = get_logger(__name__)

class AgentExecutionError(Exception):
    """Exception raised when an agent fails to execute its task."""
    pass

class BaseAgent(ABC):
    """
    Abstract base class for all incident triage agents.
    Handles standard LLM invocation, prompt building, and error handling.
    """
    
    def __init__(self, llm: BaseChatModel, prompt_template_path: str):
        self.llm = llm
        self.prompt_template_path = prompt_template_path
        
    def _load_prompt_template(self) -> str:
        """Loads the specific prompt template for this agent."""
        if not os.path.exists(self.prompt_template_path):
            raise FileNotFoundError(f"Prompt template not found: {self.prompt_template_path}")
            
        with open(self.prompt_template_path, 'r', encoding='utf-8') as f:
            return f.read()
            
    def _load_shared_prompts(self) -> Dict[str, str]:
        """Loads the shared system prompt, output format, and guardrails."""
        base_dir = os.path.dirname(os.path.dirname(self.prompt_template_path))
        shared_dir = os.path.join(base_dir, "shared")
        
        prompts = {}
        for name in ["system_prompt.txt", "output_format.txt", "guardrails.txt"]:
            path = os.path.join(shared_dir, name)
            if not os.path.exists(path):
                # Fallback to absolute if needed, but assuming relative structure works
                # Let's try to resolve it relative to this file if it fails
                current_dir = os.path.dirname(os.path.abspath(__file__))
                path = os.path.join(os.path.dirname(current_dir), "prompts", "shared", name)
                
            with open(path, 'r', encoding='utf-8') as f:
                prompts[name] = f.read()
                
        return prompts
        
    def _build_messages(self, human_prompt: str) -> list:
        """
        Assembles the LangChain messages. 
        Combines shared components into the SystemMessage and uses human_prompt for HumanMessage.
        """
        shared = self._load_shared_prompts()
        
        system_content = f"{shared['system_prompt.txt']}\n\n{shared['output_format.txt']}\n\n{shared['guardrails.txt']}"
        
        return [
            SystemMessage(content=system_content),
            HumanMessage(content=human_prompt)
        ]

    async def _invoke_llm(self, messages: list) -> str:
        """Invokes the LLM and returns the raw text response."""
        try:
            logger.info(f"Invoking LLM for agent: {self.__class__.__name__}")
            response = await self.llm.ainvoke(messages)
            
            # response.content can be str or list, handle both
            content = response.content
            if isinstance(content, list):
                content = " ".join([str(c) for c in content])
                
            return content
        except Exception as e:
            logger.error(f"LLM invocation failed in {self.__class__.__name__}: {str(e)}")
            raise AgentExecutionError(f"LLM invocation failed: {str(e)}") from e

    @abstractmethod
    async def run(self, input_data: Any) -> Any:
        """
        Execute the agent's main task. 
        Must be implemented by subclasses.
        """
        pass
