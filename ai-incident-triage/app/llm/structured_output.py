from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError
from app.utils.json_utils import extract_json_from_text

T = TypeVar("T", bound=BaseModel)

class OutputParsingError(Exception):
    """Exception raised when LLM output cannot be parsed into the expected format."""
    def __init__(self, message: str, raw_text: str):
        super().__init__(message)
        self.raw_text = raw_text

class StructuredOutputParser:
    """
    Helper to parse raw LLM text responses into Pydantic models.
    """
    
    @staticmethod
    def parse(raw_text: str, model_class: Type[T]) -> T:
        """
        Extract JSON from raw text and validate it against the given Pydantic model.
        """
        parsed_dict = extract_json_from_text(raw_text)
        
        if parsed_dict is None:
            raise OutputParsingError(
                f"Could not extract valid JSON from LLM response.",
                raw_text=raw_text
            )
            
        try:
            return model_class.model_validate(parsed_dict)
        except ValidationError as e:
            raise OutputParsingError(
                f"Extracted JSON does not match expected schema {model_class.__name__}: {str(e)}",
                raw_text=raw_text
            )
