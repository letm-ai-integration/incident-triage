import json
import re
from typing import Dict, Any, Optional

def safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    """Try to directly parse text as JSON."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from LLM responses that may contain markdown code fences, 
    preamble text, or trailing commentary.
    """
    if not text:
        return None
        
    # 1. Try direct parse
    parsed = safe_json_parse(text)
    if parsed is not None:
        return parsed
        
    # 2. Try to find markdown json blocks
    markdown_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if markdown_match:
        parsed = safe_json_parse(markdown_match.group(1))
        if parsed is not None:
            return parsed
            
    # 3. Try generic markdown code blocks
    generic_match = re.search(r'```\s*([\s\S]*?)\s*```', text)
    if generic_match:
        parsed = safe_json_parse(generic_match.group(1))
        if parsed is not None:
            return parsed
            
    # 4. Try to find the first '{' and last '}'
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = text[start_idx:end_idx+1]
        parsed = safe_json_parse(json_str)
        if parsed is not None:
            return parsed
            
    return None
