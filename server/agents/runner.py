import os
import json
import requests
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, AsyncGenerator

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def noop(f):
            return f
        return noop

try:
    from ..infrastructure.utils import log_line, get_text_from_completion, strip_code_fences, trim_history, extract_code_and_text
    from ..infrastructure.safety import violates_whitelist, ensure_clear_on_change
    from ..domain.protein.uniprot import search_uniprot
except ImportError:
    from infrastructure.utils import log_line, get_text_from_completion, strip_code_fences, trim_history, extract_code_and_text
    from infrastructure.safety import violates_whitelist, ensure_clear_on_change
    from domain.protein.uniprot import search_uniprot


_openrouter_api_key: Optional[str] = None
_model_map: Optional[Dict[str, str]] = None


def _load_model_map() -> Dict[str, str]:
    """Load model ID mappings from models_config.json.
    Maps legacy Anthropic model IDs to OpenRouter model IDs.
    """
    global _model_map
    if _model_map is not None:
        return _model_map
    
    _model_map = {}
    
    # Try to load from models_config.json (in server/ root)
    config_path = Path(__file__).parent.parent / "models_config.json"
    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                models = config.get("models", [])
                
                # Create mapping from legacy IDs to OpenRouter IDs
                # Map common legacy Anthropic model IDs to their OpenRouter equivalents
                legacy_to_openrouter = {
                    "claude-3-5-sonnet-20241022": "anthropic/claude-3.5-sonnet",
                    "claude-3-5-sonnet-20240620": "anthropic/claude-3.5-sonnet",
                    "claude-3-opus-20240229": "anthropic/claude-3-opus",
                    "claude-3-sonnet-20240229": "anthropic/claude-3-sonnet",
                    "claude-3-haiku-20240307": "anthropic/claude-3-haiku",
                }
                
                # Add mappings from config file models (if they have legacy IDs)
                for model in models:
                    model_id = model.get("id", "")
                    # If model ID is already in OpenRouter format, use it as-is
                    if "/" in model_id:
                        _model_map[model_id] = model_id
                
                # Add legacy mappings
                _model_map.update(legacy_to_openrouter)
                
                log_line("runner:model_map", {"loaded": True, "count": len(_model_map)})
        else:
            log_line("runner:model_map", {"error": "models_config.json not found"})
    except Exception as e:
        log_line("runner:model_map", {"error": str(e)})
        # Fallback to basic mappings
        _model_map = {
            "claude-3-5-sonnet-20241022": "anthropic/claude-3.5-sonnet",
            "claude-3-5-sonnet-20240620": "anthropic/claude-3.5-sonnet",
            "claude-3-opus-20240229": "anthropic/claude-3-opus",
            "claude-3-sonnet-20240229": "anthropic/claude-3-sonnet",
            "claude-3-haiku-20240307": "anthropic/claude-3-haiku",
        }
    
    return _model_map


def _get_openrouter_api_key(api_key: Optional[str] = None) -> Optional[str]:    
    """Get OpenRouter API key from OPENROUTER_API_KEY env var."""
    global _openrouter_api_key
    
    # If a specific key is provided (e.g. from client request), use it
    if api_key:
        return api_key

    # Return cached key if available
    if _openrouter_api_key:
        return _openrouter_api_key

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        _openrouter_api_key = openrouter_key
        return _openrouter_api_key



def _is_thinking_model(model: str) -> bool:
    """Check if a model is a thinking/reasoning model."""
    if not model:
        return False
    model_lower = model.lower()
    return 'thinking' in model_lower


def _parse_incremental_thinking_step(accumulated_reasoning: str, current_step: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Parse thinking step incrementally from accumulated reasoning text.
    
    Returns:
        (completed_step, current_step) - completed_step is emitted when a step boundary is detected
    """
    if not accumulated_reasoning:
        return None, current_step
    
    lines = accumulated_reasoning.split('\n')
    completed_step = None
    new_current = current_step
    
    # Look for step boundaries (numbered lists, headers, etc.)
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Check for step markers
        step_match = None
        step_id = None
        
        # Numbered list: "1. Step Title" or "1) Step Title"
        if line and (line[0].isdigit() and (line.startswith(('.', ')')) or (len(line) > 1 and line[1] in ('.', ')')))):
            if line[0].isdigit():
                # Extract number
                num_end = 1
                while num_end < len(line) and line[num_end].isdigit():
                    num_end += 1
                if num_end < len(line) and line[num_end] in ('.', ')'):
                    step_match = line[num_end + 1:].strip()
                    step_id = f"step_{line[:num_end]}"
        
        # Bullet points: "- Step Title" or "* Step Title" or "• Step Title"
        elif line.startswith(('-', '*', '•')):
            step_match = line[1:].strip()
            step_id = f"step_{len([l for l in lines[:i] if l.strip() and (l.strip()[0].isdigit() or l.strip().startswith(('-', '*', '•')))]) + 1}"
        
        # Header-like format: "Step Name:" or "STEP NAME:"
        elif ':' in line and len(line) > 0 and (line[0].isupper() or line.split(':')[0].strip().isupper()):
            parts = line.split(':', 1)
            if len(parts) == 2:
                step_match = parts[0].strip()
                step_id = f"step_{step_match.lower().replace(' ', '_')}"
        
        if step_match:
            # If we have a current step, complete it
            if new_current:
                new_current["content"] = new_current.get("content", "").strip()
                completed_step = new_current
                new_current = None
            
            # Start new step
            new_current = {
                "id": step_id or f"step_{int(time.time() * 1000)}",
                "title": step_match,
                "content": parts[1].strip() if ':' in line and len(parts) == 2 else "",
                "status": "processing"
            }
        elif new_current:
            # Append to current step content
            if new_current.get("content"):
                new_current["content"] += "\n" + line
            else:
                new_current["content"] = line
    
    return completed_step, new_current


def _call_openrouter_api_stream(
    model: str,
    messages: List[Dict[str, Any]],
    max_tokens: int,
    temperature: float,
    api_key: Optional[str] = None,
) -> Any:
    """Make a streaming API call to OpenRouter.
    
    Yields chunks as they arrive from OpenRouter.
    Each chunk contains either reasoning tokens or content tokens.
    
    Args:
        model: Model ID to use
        messages: List of message dicts
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
        api_key: Optional API key override
    
    Yields:
        Dict with 'type' ('reasoning' or 'content') and 'data' (the chunk text)
    """
    key = _get_openrouter_api_key(api_key)
    if not key:
        raise RuntimeError("OpenRouter API key is missing. Please set OPENROUTER_API_KEY in your .env file.")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": os.getenv("APP_ORIGIN", "http://localhost:3000"),
        "X-Title": "NovoProtein AI",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    
    # Request reasoning tokens for thinking models
    is_thinking = _is_thinking_model(model)
    if is_thinking:
        payload["extra_body"] = {
            "reasoning": {
                "effort": "high"
            }
        }
    
    try:
        response = requests.post(url, headers=headers, json=payload, stream=True)
        response.raise_for_status()
        
        log_line("runner:stream:started", {"model": model, "status": response.status_code})
        chunk_count = 0
        
        # Parse Server-Sent Events (SSE) format
        for line in response.iter_lines():
            if not line:
                continue
            
            # SSE format: "data: {...}"
            if line.startswith(b'data: '):
                data_str = line[6:].decode('utf-8')
                if data_str.strip() == '[DONE]':
                    log_line("runner:stream:done", {"chunk_count": chunk_count})
                    break
                
                try:
                    chunk_data = json.loads(data_str)
                    choices = chunk_data.get("choices", [])
                    if choices:
                        choice = choices[0]
                        delta = choice.get("delta", {})
                        
                        # Check for reasoning tokens
                        if "reasoning" in delta:
                            reasoning_text = delta["reasoning"]
                            if reasoning_text:
                                chunk_count += 1
                                log_line("runner:stream:reasoning", {"chunk": chunk_count, "length": len(reasoning_text)})
                                yield {"type": "reasoning", "data": reasoning_text}
                        
                        # Check for content tokens
                        if "content" in delta:
                            content_text = delta["content"]
                            if content_text:
                                chunk_count += 1
                                log_line("runner:stream:content", {"chunk": chunk_count, "length": len(content_text)})
                                yield {"type": "content", "data": content_text}
                except json.JSONDecodeError as e:
                    log_line("runner:stream:parse_error", {"line": data_str[:100], "error": str(e)})
                    continue
        
        log_line("runner:stream:finished", {"model": model, "total_chunks": chunk_count})
    except requests.exceptions.RequestException as e:
        log_line("runner:stream:error", {"error": str(e)})
        raise RuntimeError(f"OpenRouter streaming API call failed: {str(e)}")


def _call_openrouter_api(
    model: str,
    messages: List[Dict[str, Any]],
    max_tokens: int,
    temperature: float,
    api_key: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> Any:
    """Make a direct API call to OpenRouter using requests with retry logic.
    
    Returns a response object compatible with get_text_from_completion().
    
    Args:
        model: Model ID to use
        messages: List of message dicts
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
        api_key: Optional API key override
        max_retries: Maximum number of retries for rate limit errors (default: 3)
        retry_delay: Initial delay between retries in seconds (default: 1.0)
    """
    key = _get_openrouter_api_key(api_key)
    if not key:
        raise RuntimeError("OpenRouter API key is missing. Please set OPENROUTER_API_KEY in your .env file.")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": os.getenv("APP_ORIGIN", "http://localhost:3000"),
        "X-Title": "NovoProtein AI",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    
    # Request reasoning tokens for thinking models
    is_thinking = _is_thinking_model(model)
    log_line("runner:thinking:check", {"model": model, "is_thinking": is_thinking})
    if is_thinking:
        # Different thinking models may need different parameters
        if "moonshot" in model.lower() or "kimi" in model.lower():
            # Moonshot models may need streaming for reasoning
            # But let's try non-streaming first and check response
            payload["extra_body"] = {
                "reasoning": {
                    "effort": "high"
                }
            }
        else:
            # Anthropic and other thinking models
            payload["extra_body"] = {
                "reasoning": {
                    "effort": "high"
                }
            }
        log_line("runner:thinking:requested", {"model": model, "payload_has_extra_body": "extra_body" in payload})
    
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            # Parse response and create a compatible object
            data = response.json()
            
            # Check for reasoning tokens in usage (some models like Moonshot report this)
            if "usage" in data and isinstance(data["usage"], dict):
                reasoning_tokens = data["usage"].get("reasoning_tokens") or data["usage"].get("reasoningTokens")
                if reasoning_tokens:
                    log_line("runner:thinking:usage", {
                        "reasoning_tokens": reasoning_tokens,
                        "model": model
                    })
            
            # Extract thinking/reasoning data from response if available
            # OpenRouter returns reasoning in message.reasoning when extra_body.reasoning is requested
            thinking_data = None
            if data.get("choices") and len(data["choices"]) > 0:
                choice = data["choices"][0]
                message_data = choice.get("message", {})
                
                # Primary location: message.reasoning (OpenRouter standard for reasoning tokens)
                if "reasoning" in message_data:
                    thinking_data = message_data["reasoning"]
                    log_line("runner:thinking:extracted", {
                        "location": "message.reasoning",
                        "type": type(thinking_data).__name__,
                        "is_str": isinstance(thinking_data, str),
                        "is_list": isinstance(thinking_data, list),
                        "is_dict": isinstance(thinking_data, dict),
                        "preview": str(thinking_data)[:200] if isinstance(thinking_data, str) else None
                    })
                
                # Fallback locations for other formats
                elif "thinking" in message_data:
                    thinking_data = message_data["thinking"]
                    log_line("runner:thinking:extracted", {"location": "message.thinking"})
                elif "chain_of_thought" in message_data:
                    thinking_data = message_data["chain_of_thought"]
                    log_line("runner:thinking:extracted", {"location": "message.chain_of_thought"})
                
                # Check choice level
                elif "reasoning" in choice:
                    thinking_data = choice["reasoning"]
                    log_line("runner:thinking:extracted", {"location": "choice.reasoning"})
                elif "thinking" in choice:
                    thinking_data = choice["thinking"]
                    log_line("runner:thinking:extracted", {"location": "choice.thinking"})
                
                # Check response root level
                elif "reasoning" in data:
                    thinking_data = data["reasoning"]
                    log_line("runner:thinking:extracted", {"location": "data.reasoning"})
                elif "thinking" in data:
                    thinking_data = data["thinking"]
                    log_line("runner:thinking:extracted", {"location": "data.thinking"})
                
                # Debug logging if not found - also check delta for streaming responses
                if not thinking_data:
                    # Check if reasoning might be in delta (for streaming responses)
                    delta = choice.get("delta", {})
                    if "reasoning" in delta:
                        thinking_data = delta["reasoning"]
                        log_line("runner:thinking:extracted", {"location": "choice.delta.reasoning"})
                    elif "thinking" in delta:
                        thinking_data = delta["thinking"]
                        log_line("runner:thinking:extracted", {"location": "choice.delta.thinking"})
                    
                    if not thinking_data:
                        log_line("runner:thinking:debug", {
                            "has_choices": "choices" in data,
                            "choice_keys": list(choice.keys()) if isinstance(choice, dict) else None,
                            "message_keys": list(message_data.keys()) if isinstance(message_data, dict) else None,
                            "delta_keys": list(delta.keys()) if isinstance(delta, dict) else None,
                            "data_keys": list(data.keys()) if isinstance(data, dict) else None,
                            "has_usage": "usage" in data,
                            "usage_keys": list(data["usage"].keys()) if isinstance(data.get("usage"), dict) else None,
                            "is_thinking_model": _is_thinking_model(model),
                            "model": model
                        })
                elif _is_thinking_model(model):
                    # Log when we have a thinking model but didn't find reasoning
                    log_line("runner:thinking:warning", {
                        "model": model,
                        "message_has_reasoning": "reasoning" in message_data if isinstance(message_data, dict) else False,
                        "message_has_thinking": "thinking" in message_data if isinstance(message_data, dict) else False
                    })
            
            # Create a simple object that mimics OpenAI/OpenRouter response format
            class CompletionResponse:
                def __init__(self, data, thinking=None):
                    self.choices = [Choice(data.get("choices", [{}])[0] if data.get("choices") else {}, thinking)]
                    self.thinking = thinking  # Store thinking data at response level for easy access
            
            class Choice:
                def __init__(self, choice_data, thinking=None):
                    self.message = Message(choice_data.get("message", {}), thinking)
                    self.thinking = thinking  # Also store at choice level
            
            class Message:
                def __init__(self, message_data, thinking=None):
                    self.content = message_data.get("content", "")
                    # Store thinking/reasoning data - prioritize passed thinking, then check message_data
                    self.thinking = thinking if thinking is not None else message_data.get("reasoning")
                    self.reasoning = message_data.get("reasoning") if thinking is None else thinking
            
            return CompletionResponse(data, thinking_data)
        except requests.exceptions.HTTPError as e:
            # Extract the actual error message from OpenRouter's response
            error_detail = str(e)
            status_code = None
            user_message = None
            retry_after = None
            
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                
                # Handle specific HTTP status codes with user-friendly messages
                if status_code == 429:
                    user_message = "Rate limit exceeded. Please wait a moment and try again, or use a different model."
                elif status_code == 401:
                    user_message = "API key is invalid or missing. Please check your OpenRouter API key."
                elif status_code == 403:
                    user_message = "Access forbidden. The API key may not have permission for this model."
                elif status_code == 404:
                    user_message = f"Model '{model}' not found. Please check the model ID."
                elif status_code == 500:
                    user_message = "OpenRouter service error. Please try again later."
                elif status_code == 503:
                    user_message = "Service temporarily unavailable. Please try again later."
                
                # Try to extract detailed error message from response
                try:
                    error_data = e.response.json()
                    if isinstance(error_data, dict):
                        # OpenRouter error format: {"error": {"message": "...", "type": "...", ...}}
                        if 'error' in error_data:
                            error_obj = error_data['error']
                            if isinstance(error_obj, dict):
                                # Extract message, type, and other details
                                if 'message' in error_obj:
                                    error_detail = error_obj['message']
                                if 'type' in error_obj:
                                    error_detail = f"{error_obj.get('type', 'Error')}: {error_detail}"
                                # Check for rate limit details
                                if status_code == 429 and 'retry_after' in error_obj:
                                    retry_after = error_obj['retry_after']
                                    user_message = f"Rate limit exceeded. Please wait {retry_after} seconds before trying again."
                            elif isinstance(error_obj, str):
                                error_detail = error_obj
                        # Sometimes the error is at the top level
                        elif 'message' in error_data:
                            error_detail = error_data['message']
                        # Check for additional error context
                        if 'detail' in error_data:
                            error_detail = f"{error_detail} ({error_data['detail']})"
                except (ValueError, KeyError, AttributeError, json.JSONDecodeError):
                    # If JSON parsing fails, try to get text response
                    try:
                        error_text = e.response.text
                        if error_text:
                            # Try to extract useful info from text response
                            if len(error_text) < 500:
                                error_detail = f"{error_detail} (Response: {error_text})"
                            else:
                                error_detail = f"{error_detail} (Response: {error_text[:200]}...)"
                    except:
                        pass
            
            # Retry logic for rate limit errors (429)
            if status_code == 429 and attempt < max_retries:
                # Use retry_after from response if available, otherwise use exponential backoff
                wait_time = retry_after if retry_after else (retry_delay * (2 ** attempt))
                log_line("runner:openrouter:retry", {
                    "model": model,
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                    "wait_time": wait_time,
                    "retry_after": retry_after
                })
                time.sleep(wait_time)
                last_exception = e
                continue  # Retry the request
            
            # For non-retryable errors or after max retries, raise the exception
            # Use user-friendly message if available, otherwise use technical error detail
            final_error = user_message if user_message else error_detail
            
            log_line("runner:openrouter:error", {
                "error": error_detail,
                "status": status_code,
                "model": model,
                "user_message": user_message,
                "attempt": attempt + 1,
                "max_retries": max_retries
            })
            
            # For rate limits after all retries, provide more helpful error message
            if status_code == 429:
                raise RuntimeError(f"Rate limit exceeded for model '{model}' after {max_retries + 1} attempts. {user_message or 'Please wait a moment and try again, or use a different model.'}")
            else:
                raise RuntimeError(f"OpenRouter API call failed: {final_error}")
        except requests.exceptions.RequestException as e:
            # For network errors, retry with exponential backoff
            if attempt < max_retries:
                wait_time = retry_delay * (2 ** attempt)
                log_line("runner:openrouter:retry", {
                    "model": model,
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                    "wait_time": wait_time,
                    "error": str(e)
                })
                time.sleep(wait_time)
                last_exception = e
                continue  # Retry the request
            
            log_line("runner:openrouter:error", {
                "error": str(e),
                "status": getattr(e, 'response', {}).status_code if hasattr(e, 'response') and e.response is not None else None,
                "model": model,
                "attempt": attempt + 1,
                "max_retries": max_retries
            })
            raise RuntimeError(f"OpenRouter API call failed after {max_retries + 1} attempts: {str(e)}")
    
    # If we've exhausted all retries, raise the last exception
    if last_exception:
        raise last_exception
    raise RuntimeError(f"OpenRouter API call failed for model '{model}'")


def _map_model_id(model_id: str) -> str:
    """Map legacy model ID to OpenRouter model ID using models_config.json"""
    model_map = _load_model_map()
    return model_map.get(model_id, model_id)


def _parse_thinking_data(completion: Any) -> Optional[Dict[str, Any]]:
    """Extract and parse thinking data from API completion response.
    
    Returns a structured thinking process object with steps, or None if no thinking data.
    """
    try:
        # Get thinking data from completion object
        thinking_raw = None
        
        # Try to get thinking from response level first
        if hasattr(completion, 'thinking') and completion.thinking:
            thinking_raw = completion.thinking
            log_line("runner:thinking:found", {"location": "response.thinking"})
        
        # Try to get thinking/reasoning from message level (primary location for OpenRouter)
        if not thinking_raw and hasattr(completion, 'choices'):
            try:
                if len(completion.choices) > 0:
                    message = completion.choices[0].message
                    # Check reasoning first (OpenRouter standard for thinking models)
                    if hasattr(message, 'reasoning') and message.reasoning:
                        thinking_raw = message.reasoning
                        log_line("runner:thinking:found", {"location": "message.reasoning"})
                    # Fallback to thinking attribute
                    elif hasattr(message, 'thinking') and message.thinking:
                        thinking_raw = message.thinking
                        log_line("runner:thinking:found", {"location": "message.thinking"})
            except (AttributeError, IndexError, TypeError) as e:
                log_line("runner:thinking:access_error", {"error": str(e), "type": type(e).__name__})
        
        # If still not found, try to access the raw data structure
        if not thinking_raw and hasattr(completion, 'choices'):
            try:
                if len(completion.choices) > 0:
                    choice = completion.choices[0]
                    # Check if choice has reasoning/thinking directly
                    if hasattr(choice, 'reasoning') and choice.reasoning:
                        thinking_raw = choice.reasoning
                        log_line("runner:thinking:found", {"location": "choice.reasoning"})
                    elif hasattr(choice, 'thinking') and choice.thinking:
                        thinking_raw = choice.thinking
                        log_line("runner:thinking:found", {"location": "choice.thinking"})
            except (AttributeError, IndexError, TypeError) as e:
                log_line("runner:thinking:access_error", {"error": str(e), "type": type(e).__name__})
        
        if not thinking_raw:
            log_line("runner:thinking:not_found", {"has_completion": completion is not None})
            return None
        
        log_line("runner:thinking:raw", {"type": type(thinking_raw).__name__, "is_str": isinstance(thinking_raw, str), "is_list": isinstance(thinking_raw, list), "is_dict": isinstance(thinking_raw, dict)})
        
        # Parse thinking data - structure depends on API response format
        # OpenRouter/Anthropic may return thinking as:
        # - A string (raw thinking text)
        # - A list of steps
        # - A dict with steps
        # - Embedded in content with special markers
        
        thinking_steps = []
        current_step = None  # Initialize outside if block to avoid NameError
        
        if isinstance(thinking_raw, str):
            # If it's a string, try to parse it into steps
            # Look for common patterns like numbered steps, headers, etc.
            lines = thinking_raw.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check for step markers (numbered, bulleted, or header-like)
                step_match = None
                if line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                    step_match = line[2:].strip()
                elif line.startswith(('-', '*', '•')):
                    step_match = line[1:].strip()
                elif len(line) > 0 and line[0].isupper() and ':' in line:
                    # Header-like format: "Step Name: description"
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        step_match = parts[0].strip()
                        line = parts[1].strip()
                
                if step_match:
                    # Save previous step if exists
                    if current_step:
                        thinking_steps.append(current_step)
                    # Start new step
                    current_step = {
                        "id": f"step_{len(thinking_steps) + 1}",
                        "title": step_match,
                        "content": line if line else "",
                        "status": "completed"
                    }
                elif current_step:
                    # Append to current step content
                    current_step["content"] += "\n" + line if current_step["content"] else line
        
        elif isinstance(thinking_raw, list):
            # If it's already a list of steps
            for i, step in enumerate(thinking_raw):
                if isinstance(step, dict):
                    thinking_steps.append({
                        "id": step.get("id", f"step_{i+1}"),
                        "title": step.get("title", step.get("name", f"Step {i+1}")),
                        "content": step.get("content", step.get("description", "")),
                        "status": step.get("status", "completed")
                    })
                elif isinstance(step, str):
                    thinking_steps.append({
                        "id": f"step_{i+1}",
                        "title": f"Step {i+1}",
                        "content": step,
                        "status": "completed"
                    })
        
        elif isinstance(thinking_raw, dict):
            # If it's a dict with steps
            if "steps" in thinking_raw:
                steps = thinking_raw["steps"]
                if isinstance(steps, list):
                    for i, step in enumerate(steps):
                        if isinstance(step, dict):
                            thinking_steps.append({
                                "id": step.get("id", f"step_{i+1}"),
                                "title": step.get("title", step.get("name", f"Step {i+1}")),
                                "content": step.get("content", step.get("description", "")),
                                "status": step.get("status", "completed")
                            })
            else:
                # Single thinking entry
                thinking_steps.append({
                    "id": "step_1",
                    "title": thinking_raw.get("title", "Thinking"),
                    "content": thinking_raw.get("content", str(thinking_raw)),
                    "status": "completed"
                })
        
        # Save last step if exists
        if current_step:
            thinking_steps.append(current_step)
        
        if thinking_steps:
            return {
                "steps": thinking_steps,
                "isComplete": True,
                "totalSteps": len(thinking_steps)
            }
        
        return None
    except Exception as e:
        log_line("runner:thinking:parse_error", {"error": str(e)})
        return None


def _build_summarized_structure_context(
    *,
    structure_metadata: Optional[Dict[str, Any]] = None,
    uploaded_file_context: Optional[Dict[str, Any]] = None,
    pdb_id: Optional[str] = None,
    structure_label: Optional[str] = None,
    max_chars: int = 800,
) -> str:
    """Build a truncated StructureContext for the LLM, applying tiered truncation for large structures."""
    lines: List[str] = []
    chain_residue_counts: Dict[str, int] = {}
    residue_composition: Optional[Dict[str, int]] = None
    total_residues = 0

    # Gather metadata from structure_metadata (from frontend MolStar)
    if structure_metadata:
        if structure_metadata.get("sequences"):
            for seq in structure_metadata["sequences"]:
                chain = seq.get("chain", "?")
                length = seq.get("length", 0)
                chain_residue_counts[chain] = length
        total_residues = structure_metadata.get("residueCount") or sum(chain_residue_counts.values())
        residue_composition = structure_metadata.get("residueComposition")

    # Or from uploaded_file_context
    if not chain_residue_counts and uploaded_file_context:
        chain_residue_counts = dict(uploaded_file_context.get("chain_residue_counts") or {})
        total_residues = uploaded_file_context.get("total_residues") or sum(chain_residue_counts.values())
        if not chain_residue_counts and uploaded_file_context.get("chains"):
            chains = uploaded_file_context.get("chains", [])
            if chains:
                chain_residue_counts = {c: 0 for c in chains}

    # Build chain summary with tiered detail
    if chain_residue_counts:
        sorted_chains = sorted(chain_residue_counts.items(), key=lambda x: x[0])
        chain_count = len(sorted_chains)

        if total_residues > 5000 or chain_count > 10:
            total = total_residues or sum(c for _, c in sorted_chains)
            lines.append(f"Chains: {chain_count} chains, {total} total residues.")
        elif total_residues > 1000:
            chain_parts = [f"{c}({n})" for c, n in sorted_chains[:15]]
            if len(sorted_chains) > 15:
                chain_parts.append(f"...+{len(sorted_chains) - 15} more")
            lines.append(f"Chains: {', '.join(chain_parts)}.")
        else:
            chain_parts = [f"{c}({n} residues)" for c, n in sorted_chains]
            lines.append(f"Chains: {', '.join(chain_parts)}.")

    # Add composition (tiered: top 5 for <300, top 3 for 300-1000, skip for >1000)
    if residue_composition and total_residues <= 1000:
        cap = 5 if total_residues < 300 else 3
        sorted_comp = sorted(
            residue_composition.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:cap]
        total_count = sum(residue_composition.values()) or 1
        comp_parts = [f"{r} {int(100 * c / total_count)}%" for r, c in sorted_comp]
        if comp_parts:
            lines.append(f"Residue composition (top {len(comp_parts)}): {', '.join(comp_parts)}.")

    label = structure_label or (f"PDB {pdb_id}" if pdb_id else "structure")
    header = f"StructureContext: {label}."
    body = " ".join(lines)
    if body:
        full = f"{header} {body}"
    else:
        full = header

    if len(full) > max_chars:
        full = full[: max_chars - 3] + "..."
    return full


@traceable(name="RunAgent", run_type="chain")
async def run_agent(
    *,
    agent: Dict[str, Any],
    user_text: str,
    current_code: Optional[str],
    history: Optional[List[Dict[str, Any]]],
    selection: Optional[Dict[str, Any]],
    selections: Optional[List[Dict[str, Any]]] = None,
    current_structure_origin: Optional[Dict[str, Any]] = None,
    uploaded_file_context: Optional[Dict[str, Any]] = None,
    structure_metadata: Optional[Dict[str, Any]] = None,
    pipeline_id: Optional[str] = None,
    pipeline_data: Optional[Dict[str, Any]] = None,
    model_override: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    # Use model_override if provided, otherwise fall back to agent's default
    if model_override:
        model = model_override
    else:
        model = os.getenv(agent.get("modelEnv", "")) or agent.get("defaultModel")
    base_log = {"model": model, "agentId": agent.get("id"), "model_override": bool(model_override)}

    # Special handling for AlphaFold agent - use handler instead of LLM
    if agent.get("id") == "alphafold-agent":
        try:
            from .handlers.alphafold import alphafold_handler
            result = await alphafold_handler.process_folding_request(
                user_text, 
                context={
                    "current_code": current_code,
                    "history": history,
                    "selection": selection
                }
            )
            
            if result.get("action") == "error":
                log_line("agent:alphafold:error", {"error": result.get("error"), "userText": user_text})
                return {"type": "text", "text": f"Error: {result.get('error')}"}
            else:
                # Convert handler result to JSON text for frontend processing
                import json
                log_line("agent:alphafold:success", {"userText": user_text, "hasSequence": bool(result.get("sequence"))})
                return {"type": "text", "text": json.dumps(result)}
                
        except Exception as e:
            log_line("agent:alphafold:failed", {"error": str(e), "userText": user_text})
            return {"type": "text", "text": f"AlphaFold processing failed: {str(e)}"}

    # Special handling for OpenFold2 agent - open dialog (manual-only, no auto-route)
    if agent.get("id") == "openfold2-agent":
        import json
        result = {"action": "open_openfold2_dialog"}
        log_line("agent:openfold2:open_dialog", {"userText": user_text[:100]})
        return {"type": "text", "text": json.dumps(result)}

    # Special handling for RFdiffusion agent - use handler instead of LLM
    if agent.get("id") == "rfdiffusion-agent":
        try:
            from .handlers.rfdiffusion import rfdiffusion_handler
            result = await rfdiffusion_handler.process_design_request(
                user_text,
                context={
                    "current_code": current_code,
                    "history": history,
                    "selection": selection
                }
            )
            
            if result.get("action") == "error":
                log_line("agent:rfdiffusion:error", {"error": result.get("error"), "userText": user_text})
                return {"type": "text", "text": f"Error: {result.get('error')}"}
            else:
                # Convert handler result to JSON text for frontend processing
                import json
                log_line("agent:rfdiffusion:success", {"userText": user_text, "hasDesignMode": bool(result.get("parameters", {}).get("design_mode"))})
                return {"type": "text", "text": json.dumps(result)}
                
        except Exception as e:
            log_line("agent:rfdiffusion:failed", {"error": str(e), "userText": user_text})
            return {"type": "text", "text": f"RFdiffusion processing failed: {str(e)}"}

    # Special handling for ProteinMPNN agent - use handler instead of LLM
    if agent.get("id") == "proteinmpnn-agent":
        try:
            from .handlers.proteinmpnn import proteinmpnn_handler
            result = await proteinmpnn_handler.process_design_request(
                user_text,
                context={
                    "current_code": current_code,
                    "history": history,
                    "selection": selection
                }
            )
            
            if result.get("action") == "error":
                log_line("agent:proteinmpnn:error", {"error": result.get("error"), "userText": user_text})
                return {"type": "text", "text": f"Error: {result.get('error')}"}
            else:
                # Convert handler result to JSON text for frontend processing
                import json
                log_line("agent:proteinmpnn:success", {"userText": user_text, "hasPdbSource": bool(result.get("pdbSource"))})
                return {"type": "text", "text": json.dumps(result)}
                
        except Exception as e:
            log_line("agent:proteinmpnn:failed", {"error": str(e), "userText": user_text})
            return {"type": "text", "text": f"ProteinMPNN processing failed: {str(e)}"}

    # Gather pipeline context for pipeline-agent and bio-chat (when pipeline_id is provided)
    # This allows agents to answer questions about attached pipelines
    if pipeline_id or agent.get("id") == "pipeline-agent":
        try:
            from ..domain.pipeline.context import get_pipeline_context
            
            # Gather pipeline context
            pipeline_state = {
                "input": user_text,
                "uploadedFileId": uploaded_file_context.get("file_id") if uploaded_file_context else None,
                "currentStructureOrigin": current_structure_origin,
                "history": history or [],
                "selection": selection,
                "selections": selections,
                "pipeline_id": pipeline_id,  # Pass pipeline_id to context gathering
                "pipeline_data": pipeline_data,  # Pass fetched pipeline data to context gathering
            }
            
            context = await get_pipeline_context(pipeline_state)
            
            # Enhance user text with context information
            context_summary = []
            if context.get("uploaded_files"):
                files_info = ", ".join([f.get("filename", "file") for f in context["uploaded_files"]])
                context_summary.append(f"Available uploaded files: {files_info}")
            if context.get("canvas_structure"):
                canvas = context["canvas_structure"]
                if canvas.get("pdb_id"):
                    context_summary.append(f"Current structure in 3D viewer: PDB {canvas['pdb_id']}")
                elif canvas.get("file_id"):
                    context_summary.append(f"Current structure in 3D viewer: {canvas.get('filename', 'uploaded file')}")
            
            # Add detailed pipeline context if available
            if context.get("pipeline"):
                pipeline_info = context["pipeline"]
                # Build comprehensive pipeline context for bio-chat
                pipeline_context_parts = [
                    f"Pipeline Context: {pipeline_info.get('name', 'Unnamed Pipeline')} (ID: {pipeline_info.get('id')})"
                ]
                
                if pipeline_info.get("status"):
                    pipeline_context_parts.append(f"Status: {pipeline_info['status']}")
                
                if pipeline_info.get("node_count"):
                    pipeline_context_parts.append(f"Nodes: {pipeline_info['node_count']}")
                
                # Add node details with actual config params
                if pipeline_info.get("node_details"):
                    node_details = pipeline_info["node_details"]
                    node_list = []
                    for node in node_details:
                        parts = [f"{node.get('label', node.get('id'))} ({node.get('type')}, status: {node.get('status', 'idle')})"]
                        cfg = node.get("config")
                        if cfg:
                            cfg_str = ", ".join(f"{k}={v}" for k, v in cfg.items())
                            parts.append(f"config: {{{cfg_str}}}")
                        if node.get("error"):
                            parts.append(f"error: {node['error']}")
                        node_list.append(" | ".join(parts))
                    if node_list:
                        pipeline_context_parts.append("Node details: " + "; ".join(node_list))

                # Add execution flow if available
                if pipeline_info.get("execution_flow"):
                    flow = pipeline_info["execution_flow"]
                    if isinstance(flow, list) and flow:
                        pipeline_context_parts.append(f"Execution flow: {'; '.join(flow)}")

                # Add nodes by type if available
                if pipeline_info.get("nodes_by_type"):
                    nodes_by_type = pipeline_info["nodes_by_type"]
                    type_summary = []
                    for node_type, nodes_of_type in nodes_by_type.items():
                        type_summary.append(f"{len(nodes_of_type)} {node_type}")
                    if type_summary:
                        pipeline_context_parts.append(f"Node types: {', '.join(type_summary)}")

                # Add output files if available
                if pipeline_info.get("output_files"):
                    output_files = pipeline_info["output_files"]
                    file_list = [f.get("node_label", f.get("node_id")) for f in output_files]
                    if file_list:
                        pipeline_context_parts.append(f"Output files from: {', '.join(file_list)}")

                # --- Enriched execution context ---
                # Recent execution history
                if pipeline_info.get("recent_executions"):
                    exec_lines = []
                    for ex in pipeline_info["recent_executions"]:
                        dur = f", duration: {ex['total_duration_ms']}ms" if ex.get("total_duration_ms") else ""
                        err = f", error: {ex['error_summary']}" if ex.get("error_summary") else ""
                        exec_lines.append(
                            f"{ex.get('status','?')} ({ex.get('trigger_type','?')}) at {ex.get('started_at','?')}{dur}{err}"
                        )
                    pipeline_context_parts.append("Recent executions: " + "; ".join(exec_lines))

                # Latest execution per-node log
                if pipeline_info.get("latest_node_executions"):
                    ne_lines = []
                    for ne in pipeline_info["latest_node_executions"]:
                        dur = f", {ne['duration_ms']}ms" if ne.get("duration_ms") else ""
                        err = f", error: {ne['error']}" if ne.get("error") else ""
                        out = f", output: {ne['output_summary']}" if ne.get("output_summary") else ""
                        ne_lines.append(
                            f"[{ne.get('execution_order','-')}] {ne.get('node_label',ne.get('node_id'))} ({ne.get('node_type')}): {ne.get('status','?')}{dur}{err}{out}"
                        )
                    pipeline_context_parts.append("Latest run node log: " + "; ".join(ne_lines))

                # Pipeline files
                if pipeline_info.get("node_files"):
                    file_lines = []
                    for nf in pipeline_info["node_files"]:
                        file_lines.append(
                            f"{nf.get('filename','?')} ({nf.get('role','?')}/{nf.get('file_type','?')}) on node {nf.get('node_id','?')}"
                        )
                    pipeline_context_parts.append("Pipeline files: " + "; ".join(file_lines))

                context_summary.append("; ".join(pipeline_context_parts))
            
            enhanced_user_text = user_text
            if context_summary:
                enhanced_user_text = f"{user_text}\n\nContext: {'; '.join(context_summary)}"
            
            # Include context in the system message or as additional context
            # The agent will use this to generate appropriate blueprints or answer questions
            p_info = context.get("pipeline") or {}
            log_line("agent:pipeline:context", {
                "has_files": len(context.get("uploaded_files", [])) > 0,
                "has_canvas": context.get("canvas_structure") is not None,
                "has_pipeline": bool(p_info),
                "has_executions": bool(p_info.get("recent_executions")),
                "has_node_executions": bool(p_info.get("latest_node_executions")),
                "has_node_files": bool(p_info.get("node_files")),
                "pipeline_id": pipeline_id,
                "userText": user_text
            })
            
            # Continue with normal LLM flow but with enhanced text
            # We'll modify the user_text for this agent
            user_text = enhanced_user_text
            
        except Exception as e:
            log_line("agent:pipeline:context_error", {"error": str(e), "userText": user_text, "pipeline_id": pipeline_id})
            # Continue without context enhancement if gathering fails

    # Deterministic UniProt search agent (no LLM call)
    if agent.get("id") == "uniprot-search":
        import re, json
        # extract term between 'search ... in uniprot' or fallback to entire text
        m_term = re.search(r"(?:search|find)\s+(.+?)\s+in\s+uniprot", user_text, flags=re.I)
        term = (m_term.group(1) if m_term else user_text).strip()
        # number of results
        m_size = re.search(r"(?:show|top|first)\s+(\d+)\s+(?:results|hits)?", user_text, flags=re.I)
        size = int(m_size.group(1)) if m_size else 3
        # format preference
        m_format = re.search(r"(?:as|in)\s+(json|table|csv)\b", user_text, flags=re.I)
        fmt = (m_format.group(1).lower() if m_format else "table")

        items = await search_uniprot(term, size=size)

        if fmt == "json":
            text = json.dumps(items, indent=2)
        elif fmt == "csv":
            header = "accession,id,protein,organism,length,reviewed"
            lines = [header]
            for i in items:
                protein = (i.get("protein") or "").replace(",", " ")
                organism = (i.get("organism") or "").replace(",", " ")
                lines.append(f"{i.get('accession')},{i.get('id')},{protein},{organism},{i.get('length') or ''},{'Yes' if i.get('reviewed') else 'No'}")
            text = "\n".join(lines)
        else:
            # markdown-like table (renders as text in current chat UI)
            lines = [
                "Accession | ID | Protein | Organism | Length | Reviewed",
                "---|---|---|---|---|---",
            ]
            for i in items:
                lines.append(
                    f"{i.get('accession')} | {i.get('id')} | {i.get('protein') or '-'} | {i.get('organism') or '-'} | {i.get('length') or '-'} | {'Yes' if i.get('reviewed') else 'No'}"
                )
            text = "\n".join(lines) if items else "No UniProt matches found."
        log_line("agent:uniprot:res", {"count": len(items), "fmt": fmt, "term": term})
        return {"type": "text", "text": text}

    if agent.get("kind") == "code":
        # Extract PDB ID and structure metadata from current code for better context
        import re
        code_pdb_id = None
        structure_metadata = ""
        
        if current_code and str(current_code).strip():
            # Extract PDB ID from loadStructure calls
            pdb_match = re.search(r"loadStructure\s*\(\s*['\"]([0-9A-Za-z]{4})['\"]", str(current_code))
            if pdb_match:
                code_pdb_id = pdb_match.group(1).upper()
                structure_metadata = f"\n\nStructure Context: The current code loads PDB ID {code_pdb_id}. "
                # Extract representation types and colors for context
                representations = []
                if re.search(r"addCartoonRepresentation", str(current_code)):
                    color_match = re.search(r"color:\s*['\"]([^'\"]+)['\"]", str(current_code))
                    color = color_match.group(1) if color_match else "default"
                    representations.append(f"cartoon ({color})")
                if re.search(r"addBallAndStickRepresentation", str(current_code)):
                    representations.append("ball-and-stick")
                if re.search(r"addSurfaceRepresentation", str(current_code)):
                    representations.append("surface")
                if re.search(r"highlightLigands", str(current_code)):
                    representations.append("ligands highlighted")
                if representations:
                    structure_metadata += f"Current representations: {', '.join(representations)}. "
                structure_metadata += "When generating your response, confirm what structure is being loaded and explain what visual elements will be shown."
        
        # Include uploaded file context if available
        uploaded_file_info = ""
        if uploaded_file_context:
            file_url = uploaded_file_context.get("file_url", "")
            filename = uploaded_file_context.get("filename", "uploaded file")
            atoms = uploaded_file_context.get("atoms", 0)
            chains = uploaded_file_context.get("chains", [])
            uploaded_file_info = f"\n\nIMPORTANT: User has uploaded a PDB file ({filename}, {atoms} atoms, chains: {', '.join(chains) if chains else 'N/A'}). "
            uploaded_file_info += f"To load this file, use: await builder.loadStructure('{file_url}');\n"
            uploaded_file_info += "The file is available at the API endpoint shown above. Use this URL instead of a PDB ID.\n"
            if not structure_metadata:
                structure_metadata = f"\n\nStructure Context: User has uploaded a PDB file '{filename}' ({atoms} atoms, {len(chains)} chain{'s' if len(chains) != 1 else ''}). "
                structure_metadata += "When generating your response, confirm what structure is being loaded and explain what visual elements will be shown."
        
        context_prefix = (
            f"You may MODIFY the existing Molstar builder code below to satisfy the new request. Prefer editing in-place if it does not change the loaded PDB. Always return the full updated code.\n\n"
            f"Existing code:\n\n```js\n{str(current_code)}\n```\n\nRequest: {user_text}{uploaded_file_info}{structure_metadata}"
            if current_code and str(current_code).strip()
            else f"Generate Molstar builder code for: {user_text}{uploaded_file_info}{structure_metadata}"
        )

        # Build proper conversation history for context awareness
        # Convert history to proper message format so AI understands previous conversation
        conversation_history = []
        if history:
            for msg in history[-6:]:  # Last 6 messages for better context
                msg_type = msg.get('type', '')
                msg_content = msg.get('content', '')
                if msg_type == 'user':
                    conversation_history.append({"role": "user", "content": msg_content})
                elif msg_type == 'ai':
                    # Include full AI response content so AI understands what it previously suggested
                    conversation_history.append({"role": "assistant", "content": msg_content})
        
        # Enhanced system prompt with RAG for MVS agent
        system_prompt = agent.get("system")
        if agent.get("id") == "mvs-builder":
            print("[RAG] MVS agent triggered, enhancing prompt with Pinecone examples...")
            try:
                from ..memory.rag.mvs_rag import enhance_mvs_prompt_with_rag
                system_prompt = await enhance_mvs_prompt_with_rag(user_text, system_prompt)
                print("[RAG] Successfully enhanced MVS prompt")
                log_line("agent:mvs:rag", {"enhanced": True, "userText": user_text})
            except Exception as e:
                print(f"[RAG] Failed to enhance prompt: {e}")
                log_line("agent:mvs:rag_error", {"error": str(e)})
                # Fallback to base prompt if RAG fails
        
        # Map model ID to OpenRouter format
        openrouter_model = _map_model_id(model)
        
        # Prepare messages with system prompt, conversation history, and current request
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        # Add conversation history for context awareness
        messages.extend(conversation_history)
        # Add current request with context
        messages.append({"role": "user", "content": context_prefix})
        
        log_line("agent:code:req", {**base_log, "hasCurrentCode": bool(current_code and str(current_code).strip()), "userText": user_text})
        completion = _call_openrouter_api(
            model=openrouter_model,
            messages=messages,
            max_tokens=1200,
            temperature=0.2,
        )
        content_text = get_text_from_completion(completion)
        code, explanation_text = extract_code_and_text(content_text)
        final_completion = completion  # Track which completion to use for thinking data

        # Safety pass
        if violates_whitelist(code):
            log_line("safety:whitelist", {"blocked": True})
            # Ask once to regenerate within constraints
            safety_messages = []
            if agent.get("system"):
                safety_messages.append({"role": "system", "content": agent.get("system")})
            safety_messages.append({
                "role": "user",
                "content": context_prefix
                + "\n\nThe code you returned included calls that are not in the whitelist. Regenerate strictly using only the allowed builder methods.",
            })
            completion2 = _call_openrouter_api(
                model=openrouter_model,
                messages=safety_messages,
                max_tokens=1200,
                temperature=0.2,
            )
            content_text2 = get_text_from_completion(completion2)
            code, explanation_text = extract_code_and_text(content_text2)
            final_completion = completion2  # Use the safety pass completion for thinking data

        code = ensure_clear_on_change(current_code, code)
        log_line("agent:code:res", {"length": len(code), "has_text": bool(explanation_text)})
        
        # Extract thinking data if available (from final completion)
        thinking_process = _parse_thinking_data(final_completion)
        result = {"type": "code", "code": code}
        # Include text explanation if available
        if explanation_text:
            result["text"] = explanation_text
        if thinking_process:
            result["thinkingProcess"] = thinking_process
        return result

    # Text agent
    selection_lines = []
    code_pdb_id = None
    structure_origin_context = None
    
    # Enrich uploaded_file_context with full metadata from DB if we have file_id but missing chain_residue_counts
    if uploaded_file_context and user_id:
        file_id = uploaded_file_context.get("file_id")
        if file_id and not uploaded_file_context.get("chain_residue_counts"):
            try:
                from ..domain.storage.pdb_storage import get_uploaded_pdb
                db_meta = get_uploaded_pdb(file_id, user_id)
                if db_meta:
                    uploaded_file_context = dict(uploaded_file_context)
                    uploaded_file_context["chain_residue_counts"] = db_meta.get("chain_residue_counts", {})
                    uploaded_file_context["total_residues"] = db_meta.get("total_residues")
            except Exception as e:
                log_line("agent:text:upload_metadata_fetch_error", {"error": str(e), "file_id": file_id})

    # Add uploaded file context if available
    uploaded_file_info = ""
    if uploaded_file_context:
        filename = uploaded_file_context.get("filename", "uploaded file")
        atoms = uploaded_file_context.get("atoms", 0)
        chains = uploaded_file_context.get("chains", [])
        file_url = uploaded_file_context.get("file_url", "")
        uploaded_file_info = (
            f"UploadedFileContext: User has uploaded a PDB file named '{filename}' "
            f"({atoms} atoms, {len(chains)} chain{'s' if len(chains) != 1 else ''}: {', '.join(chains) if chains else 'N/A'}). "
            f"The file is available at: {file_url}. "
            f"When answering questions about this structure, refer to it as the uploaded file '{filename}'.\n\n"
        )
    
    if current_code and str(current_code).strip():
        import re
        # Check for blob URL (RF diffusion/AlphaFold result)
        blob_match = re.search(r"loadStructure\s*\(\s*['\"](blob:[^'\"]+)['\"]", str(current_code))
        if blob_match:
            # This is a generated structure, check current_structure_origin or history for origin
            if current_structure_origin:
                origin_type = current_structure_origin.get("type", "unknown")
                if origin_type == "rfdiffusion":
                    params = current_structure_origin.get("parameters", {})
                    structure_origin_context = (
                        f"Current Structure: This is a protein structure generated using RFdiffusion protein design. "
                        f"Design mode: {params.get('design_mode', 'unknown')}. "
                    )
                    if params.get("contigs"):
                        structure_origin_context += f"Contigs: {params.get('contigs')}. "
                    if params.get("diffusion_steps"):
                        structure_origin_context += f"Diffusion steps: {params.get('diffusion_steps')}. "
                    if current_structure_origin.get("filename"):
                        structure_origin_context += f"Filename: {current_structure_origin.get('filename')}. "
                    structure_origin_context += (
                        "This structure does not have a PDB ID because it was computationally generated, "
                        "not retrieved from the Protein Data Bank."
                    )
                elif origin_type == "alphafold":
                    structure_origin_context = (
                        f"Current Structure: This is a protein structure predicted using AlphaFold2. "
                    )
                    if current_structure_origin.get("filename"):
                        structure_origin_context += f"Filename: {current_structure_origin.get('filename')}. "
                    structure_origin_context += (
                        "This structure does not have a PDB ID because it was computationally predicted, "
                        "not retrieved from the Protein Data Bank."
                    )
                elif origin_type == "upload":
                    structure_origin_context = (
                        f"Current Structure: This is a protein structure loaded from an uploaded PDB file. "
                    )
                    if current_structure_origin.get("filename"):
                        structure_origin_context += f"Filename: {current_structure_origin.get('filename')}. "
            else:
                # Fallback: check history for structure metadata
                if history:
                    import json
                    for msg in reversed(history):  # Check most recent first
                        if msg.get("type") == "ai" and msg.get("alphafoldResult"):
                            result = msg["alphafoldResult"]
                            job_type = result.get("jobType", "unknown")
                            params = result.get("parameters", {})
                            
                            if job_type == "rfdiffusion":
                                structure_origin_context = (
                                    f"Current Structure: This structure was generated using RFdiffusion protein design. "
                                    f"Design mode: {params.get('design_mode', 'unknown')}. "
                                )
                                if params.get("contigs"):
                                    structure_origin_context += f"Contigs: {params.get('contigs')}. "
                                structure_origin_context += (
                                    "This structure does not have a PDB ID because it was computationally generated."
                                )
                                break
                            elif job_type == "alphafold":
                                structure_origin_context = (
                                    "Current Structure: This structure was predicted using AlphaFold2. "
                                    "This structure does not have a PDB ID because it was computationally predicted."
                                )
                                break
        
        # Check for PDB ID (traditional structure)
        pdb_match = re.search(r"loadStructure\s*\(\s*['\"]([0-9A-Za-z]{4})['\"]", str(current_code))
        if pdb_match:
            code_pdb_id = pdb_match.group(1).upper()
            if not structure_origin_context:
                structure_origin_context = f"Current Structure: PDB ID {code_pdb_id} (from Protein Data Bank)."

    # Fetch PDB metadata when we have PDB ID but no structure_metadata from frontend
    if code_pdb_id and not structure_metadata:
        try:
            from ..domain.protein.sequence import SequenceExtractor
            extractor = SequenceExtractor()
            sequences = extractor.extract_from_pdb_id(code_pdb_id)
            if sequences:
                structure_metadata = {
                    "sequences": [{"chain": c, "sequence": s, "length": len(s)} for c, s in sequences.items()],
                    "chains": list(sequences.keys()),
                    "residueCount": sum(len(s) for s in sequences.values()),
                }
        except Exception as e:
            log_line("agent:text:pdb_metadata_fetch_error", {"error": str(e), "pdb_id": code_pdb_id})

    # Build summarized StructureContext (chains, residue counts, composition) for residue-suggestion questions
    summarized_structure_context = ""
    structure_label = None
    if current_structure_origin:
        origin_type = current_structure_origin.get("type", "")
        if origin_type == "upload" and current_structure_origin.get("filename"):
            structure_label = f"uploaded file '{current_structure_origin['filename']}'"
        elif origin_type == "pdb" and current_structure_origin.get("pdbId"):
            code_pdb_id = code_pdb_id or current_structure_origin.get("pdbId")
    if code_pdb_id and not structure_label:
        structure_label = f"PDB {code_pdb_id}"
    if structure_metadata or (uploaded_file_context and (uploaded_file_context.get("chain_residue_counts") or uploaded_file_context.get("chains"))):
        summarized_structure_context = _build_summarized_structure_context(
            structure_metadata=structure_metadata,
            uploaded_file_context=uploaded_file_context,
            pdb_id=code_pdb_id,
            structure_label=structure_label,
        )
    
    # Handle multiple selections if provided, otherwise fall back to single selection
    active_selections = selections if selections and len(selections) > 0 else ([selection] if selection else [])
    
    if active_selections:
        # Always treat as multiple selections to provide comprehensive info
        # Use the new multiple selection format even for single selections
        selection_lines.append(f"SelectedResiduesContext ({len(active_selections)} residue{'s' if len(active_selections) != 1 else ''}):")
        
        for i, sel in enumerate(active_selections):
            chain = sel.get('labelAsymId') or sel.get('authAsymId') or '?'
            seq_id = sel.get('labelSeqId') if sel.get('labelSeqId') is not None else sel.get('authSeqId')
            comp_id = sel.get('compId') or '?'
            # Use PDB ID from selection, or fall back to code context
            pdb_id = sel.get('pdbId') or code_pdb_id or 'unknown'
            
            # Provide detailed info for each residue
            selection_lines.append(f"  {i+1}. {comp_id}{seq_id} (Chain {chain}) in PDB {pdb_id}")
            selection_lines.append(f"     - Residue Type: {comp_id}")
            selection_lines.append(f"     - Position: {seq_id}")
            selection_lines.append(f"     - Chain: {chain}")
            selection_lines.append(f"     - PDB Structure: {pdb_id}")
            if sel.get('insCode'):
                selection_lines.append(f"     - Insertion Code: {sel.get('insCode')}")
        
        if len(active_selections) > 1:
            selection_lines.append(f"Note: User has selected {len(active_selections)} residues for analysis or comparison.")
        else:
            selection_lines.append("Note: User has selected this specific residue for analysis.")
    selection_context = "Context:\n" + "\n".join(selection_lines) if selection_lines else ""
    
    code_context = (
        f"CodeContext (Current PDB: {code_pdb_id or 'unknown'}):\n" + str(current_code)[:3000]
        if current_code and str(current_code).strip()
        else ""
    )
    
    # Add structure origin context to code_context
    if structure_origin_context:
        if code_context:
            code_context = structure_origin_context + "\n\n" + code_context
        else:
            code_context = structure_origin_context
    
    # Also add recent history context about generated structures
    history_context_lines = []
    if history:
        import json
        for msg in history[-3:]:  # Last 3 messages
            if msg.get("type") == "ai" and msg.get("alphafoldResult"):
                result = msg["alphafoldResult"]
                job_type = result.get("jobType", "unknown")
                if job_type == "rfdiffusion":
                    params = result.get("parameters", {})
                    history_context_lines.append(
                        f"Recent RFdiffusion result: {result.get('filename', 'unknown')} "
                        f"(design mode: {params.get('design_mode', 'unknown')})"
                    )
                elif job_type == "alphafold":
                    history_context_lines.append(
                        f"Recent AlphaFold2 prediction: {result.get('filename', 'unknown')}"
                    )

    # Detect if user input is a greeting or conversational (not asking about structure)
    user_text_lower = user_text.lower().strip()
    greeting_patterns = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "thanks", "thank you", "ok", "okay"]
    is_greeting = any(pattern in user_text_lower for pattern in greeting_patterns) and len(user_text.strip()) < 30
    
    # Add pipeline context for text agents (bio-chat) if pipeline_id is provided
    pipeline_context_info = ""
    if pipeline_id:
        # Try to use pipeline_data if available, otherwise create basic context
        if pipeline_data:
            try:
                from ..domain.pipeline.context import get_pipeline_context, get_pipeline_summary
                
                # Create pipeline summary
                summary = await get_pipeline_summary(pipeline_id, pipeline_data)
                
                # Build detailed pipeline context
                pipeline_context_lines = [
                    f"Pipeline Context: {summary.get('name', 'Unnamed Pipeline')} (ID: {summary.get('pipeline_id')})"
                ]
                
                if summary.get("status"):
                    pipeline_context_lines.append(f"Status: {summary['status']}")
                
                if summary.get("node_count"):
                    pipeline_context_lines.append(f"Total nodes: {summary['node_count']}")
                
                # Add node details with actual configs
                if summary.get("node_details"):
                    node_list = []
                    for node in summary["node_details"]:
                        parts = [f"{node.get('label', node.get('id'))} (type: {node.get('type')}, status: {node.get('status', 'idle')})"]
                        cfg = node.get("config")
                        if cfg:
                            cfg_str = ", ".join(f"{k}={v}" for k, v in cfg.items())
                            parts.append(f"config: {{{cfg_str}}}")
                        if node.get("error"):
                            parts.append(f"error: {node['error']}")
                        node_list.append(" | ".join(parts))
                    if node_list:
                        pipeline_context_lines.append("Nodes: " + "; ".join(node_list))

                # Add execution flow
                if summary.get("execution_flow"):
                    flow = summary["execution_flow"]
                    if isinstance(flow, list) and flow:
                        pipeline_context_lines.append(f"Execution flow: {' → '.join(flow)}")

                # Add nodes by type
                if summary.get("nodes_by_type"):
                    type_summary = []
                    for node_type, nodes_of_type in summary["nodes_by_type"].items():
                        type_summary.append(f"{len(nodes_of_type)} {node_type}")
                    if type_summary:
                        pipeline_context_lines.append(f"Node types: {', '.join(type_summary)}")

                # Extract and add output files from result_metadata
                output_files = []
                for node in pipeline_data.get("nodes", []):
                    result_metadata = node.get("result_metadata") or {}
                    if result_metadata.get("output_file"):
                        output_files.append(f"{node.get('label', node.get('id'))}: {result_metadata['output_file'].get('filename', 'output file')}")
                    if result_metadata.get("sequence"):
                        output_files.append(f"{node.get('label', node.get('id'))}: sequence output")
                if output_files:
                    pipeline_context_lines.append(f"Output files: {', '.join(output_files)}")

                # Recent execution history
                if summary.get("recent_executions"):
                    exec_lines = []
                    for ex in summary["recent_executions"]:
                        dur = f", duration: {ex['total_duration_ms']}ms" if ex.get("total_duration_ms") else ""
                        err = f", error: {ex['error_summary']}" if ex.get("error_summary") else ""
                        exec_lines.append(f"{ex.get('status','?')} ({ex.get('trigger_type','?')}) at {ex.get('started_at','?')}{dur}{err}")
                    pipeline_context_lines.append("Recent executions: " + "; ".join(exec_lines))

                # Latest execution per-node log
                if summary.get("latest_node_executions"):
                    ne_lines = []
                    for ne in summary["latest_node_executions"]:
                        dur = f", {ne['duration_ms']}ms" if ne.get("duration_ms") else ""
                        err = f", error: {ne['error']}" if ne.get("error") else ""
                        out = f", output: {ne['output_summary']}" if ne.get("output_summary") else ""
                        ne_lines.append(f"[{ne.get('execution_order','-')}] {ne.get('node_label',ne.get('node_id'))} ({ne.get('node_type')}): {ne.get('status','?')}{dur}{err}{out}")
                    pipeline_context_lines.append("Latest run node log: " + "; ".join(ne_lines))

                # Pipeline files
                if summary.get("node_files"):
                    file_lines = []
                    for nf in summary["node_files"]:
                        file_lines.append(f"{nf.get('filename','?')} ({nf.get('role','?')}/{nf.get('file_type','?')}) on node {nf.get('node_id','?')}")
                    pipeline_context_lines.append("Pipeline files: " + "; ".join(file_lines))

                pipeline_context_info = "Pipeline Context:\n" + "\n".join(pipeline_context_lines)
            except Exception as e:
                log_line("agent:text:pipeline_context_error", {
                    "error": str(e),
                    "pipeline_id": pipeline_id,
                    "has_pipeline_data": bool(pipeline_data),
                })
                # Continue without pipeline context if fetching fails
        else:
            # If no pipeline_data, still provide basic context with pipeline_id
            pipeline_context_info = f"Pipeline Context: Pipeline ID {pipeline_id} is attached to this message. The user is asking about this pipeline, but full pipeline details could not be loaded (user may not be authenticated or pipeline may not exist in database)."
            log_line("agent:text:pipeline_basic_context", {
                "pipeline_id": pipeline_id,
                "note": "Using basic context without full pipeline data",
            })
    
    messages: List[Dict[str, Any]] = []
    context_parts = []
    if uploaded_file_info:
        context_parts.append(uploaded_file_info)
    if pipeline_context_info:
        context_parts.append(pipeline_context_info)
    if history_context_lines:
        context_parts.append("Recent Structure Generation History:\n" + "\n".join(history_context_lines))
    if selection_context:
        context_parts.append(selection_context)
    # Add summarized StructureContext (chains, residue counts) for residue-suggestion questions
    if summarized_structure_context and not is_greeting:
        context_parts.append(summarized_structure_context)
    # Only include code/structure context if user is NOT just greeting
    # For greetings, skip structure context to avoid describing structures unnecessarily
    if code_context and not is_greeting:
        context_parts.append(code_context)
    
    if context_parts:
        messages.append({"role": "user", "content": "\n\n".join(context_parts)})
    messages.append({"role": "user", "content": user_text})

    log_line("agent:text:req", {**base_log, "hasSelection": bool(selection), "userText": user_text})
    
    # Map model ID to OpenRouter format
    openrouter_model = _map_model_id(model)
    
    # Prepare messages with system prompt
    openrouter_messages = []
    system_prompt = agent.get("system")
    if system_prompt:
        openrouter_messages.append({"role": "system", "content": system_prompt})
    openrouter_messages.extend(messages)
    
    # Try the requested model, with automatic fallback to default if rate limited
    try:
        completion = _call_openrouter_api(
            model=openrouter_model,
            messages=openrouter_messages,
            max_tokens=1000,
            temperature=0.5,
        )
    except RuntimeError as e:
        # If rate limited and using a model override, try falling back to default model
        if "Rate limit exceeded" in str(e) and model_override:
            default_model = os.getenv(agent.get("modelEnv", "")) or agent.get("defaultModel")
            default_openrouter_model = _map_model_id(default_model)
            
            # Only fallback if default model is different from the override
            if default_openrouter_model != openrouter_model:
                log_line("runner:model:fallback", {
                    "from": openrouter_model,
                    "to": default_openrouter_model,
                    "reason": "rate_limit",
                    "agentId": agent.get("id")
                })
                try:
                    completion = _call_openrouter_api(
                        model=default_openrouter_model,
                        messages=openrouter_messages,
                        max_tokens=1000,
                        temperature=0.5,
                    )
                    # Update base_log to reflect the fallback
                    base_log["model"] = default_model
                    base_log["fallback_used"] = True
                except RuntimeError as fallback_error:
                    # If fallback also fails, raise the original error with context
                    log_line("runner:model:fallback_failed", {
                        "original_model": openrouter_model,
                        "fallback_model": default_openrouter_model,
                        "error": str(fallback_error)
                    })
                    raise RuntimeError(f"Rate limit exceeded for model '{openrouter_model}'. Fallback to default model '{default_openrouter_model}' also failed: {str(fallback_error)}")
            else:
                # Same model, just re-raise the original error
                raise
        else:
            # Not a rate limit or no override, just re-raise
            raise
    
    text = get_text_from_completion(completion)
    log_line("agent:text:res", {"length": len(text), "preview": text[:400]})
    
    # Extract thinking data if available
    thinking_process = _parse_thinking_data(completion)
    result = {"type": "text", "text": text}
    if thinking_process:
        result["thinkingProcess"] = thinking_process
    return result


@traceable(name="RunAgentStream", run_type="chain")
async def run_agent_stream(
    *,
    agent: Dict[str, Any],
    user_text: str,
    current_code: Optional[str],
    history: Optional[List[Dict[str, Any]]],
    selection: Optional[Dict[str, Any]],
    selections: Optional[List[Dict[str, Any]]] = None,
    current_structure_origin: Optional[Dict[str, Any]] = None,
    uploaded_file_context: Optional[Dict[str, Any]] = None,
    model_override: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream agent execution with incremental thinking step updates.
    
    Yields incremental updates:
    - {"type": "thinking_step", "data": {...}} - New or updated thinking step
    - {"type": "content", "data": {"text": "..."}} - Content chunk
    - {"type": "complete", "data": {...}} - Final result
    - {"type": "error", "data": {"error": "..."}} - Error occurred
    """
    # Use model_override if provided, otherwise fall back to agent's default
    if model_override:
        model = model_override
    else:
        model = os.getenv(agent.get("modelEnv", "")) or agent.get("defaultModel")
    base_log = {"model": model, "agentId": agent.get("id"), "model_override": bool(model_override)}
    
    # Check if this is a thinking model
    is_thinking = _is_thinking_model(model)
    if not is_thinking:
        # For non-thinking models, fall back to regular execution
        try:
            result = await run_agent(
                agent=agent,
                user_text=user_text,
                current_code=current_code,
                history=history,
                selection=selection,
                selections=selections,
                model_override=model_override,
            )
            yield {"type": "complete", "data": result}
            return
        except Exception as e:
            yield {"type": "error", "data": {"error": str(e)}}
            return
    
    # Support streaming for both text and code agents with thinking models
    agent_kind = agent.get("kind")
    
    # Handle code agents
    if agent_kind == "code":
        try:
            # Extract PDB ID and structure metadata from current code for better context
            import re
            code_pdb_id = None
            structure_metadata = ""
            
            if current_code and str(current_code).strip():
                # Extract PDB ID from loadStructure calls
                pdb_match = re.search(r"loadStructure\s*\(\s*['\"]([0-9A-Za-z]{4})['\"]", str(current_code))
                if pdb_match:
                    code_pdb_id = pdb_match.group(1).upper()
                    structure_metadata = f"\n\nStructure Context: The current code loads PDB ID {code_pdb_id}. "
                    # Extract representation types and colors for context
                    representations = []
                    if re.search(r"addCartoonRepresentation", str(current_code)):
                        color_match = re.search(r"color:\s*['\"]([^'\"]+)['\"]", str(current_code))
                        color = color_match.group(1) if color_match else "default"
                        representations.append(f"cartoon ({color})")
                    if re.search(r"addBallAndStickRepresentation", str(current_code)):
                        representations.append("ball-and-stick")
                    if re.search(r"addSurfaceRepresentation", str(current_code)):
                        representations.append("surface")
                    if re.search(r"highlightLigands", str(current_code)):
                        representations.append("ligands highlighted")
                    if representations:
                        structure_metadata += f"Current representations: {', '.join(representations)}. "
                    structure_metadata += "When generating your response, confirm what structure is being loaded and explain what visual elements will be shown."
            
            # Include uploaded file context if available
            uploaded_file_info = ""
            if uploaded_file_context:
                file_url = uploaded_file_context.get("file_url", "")
                filename = uploaded_file_context.get("filename", "uploaded file")
                atoms = uploaded_file_context.get("atoms", 0)
                chains = uploaded_file_context.get("chains", [])
                uploaded_file_info = f"\n\nIMPORTANT: User has uploaded a PDB file ({filename}, {atoms} atoms, chains: {', '.join(chains) if chains else 'N/A'}). "
                uploaded_file_info += f"To load this file, use: await builder.loadStructure('{file_url}');\n"
                uploaded_file_info += "The file is available at the API endpoint shown above. Use this URL instead of a PDB ID.\n"
                if not structure_metadata:
                    structure_metadata = f"\n\nStructure Context: User has uploaded a PDB file '{filename}' ({atoms} atoms, {len(chains)} chain{'s' if len(chains) != 1 else ''}). "
                    structure_metadata += "When generating your response, confirm what structure is being loaded and explain what visual elements will be shown."
            
            # Build context similar to run_agent for code agents
            context_prefix = (
                f"You may MODIFY the existing Molstar builder code below to satisfy the new request. Prefer editing in-place if it does not change the loaded PDB. Always return the full updated code.\n\n"
                f"Existing code:\n\n```js\n{str(current_code)}\n```\n\nRequest: {user_text}{uploaded_file_info}{structure_metadata}"
                if current_code and str(current_code).strip()
                else f"Generate Molstar builder code for: {user_text}{uploaded_file_info}{structure_metadata}"
            )

            # Build proper conversation history for context awareness (streaming path)
            conversation_history = []
            if history:
                for msg in history[-6:]:  # Last 6 messages for better context
                    msg_type = msg.get('type', '')
                    msg_content = msg.get('content', '')
                    if msg_type == 'user':
                        conversation_history.append({"role": "user", "content": msg_content})
                    elif msg_type == 'ai':
                        # Include full AI response content so AI understands what it previously suggested
                        conversation_history.append({"role": "assistant", "content": msg_content})

            # Enhanced system prompt with RAG for MVS agent
            system_prompt = agent.get("system")
            if agent.get("id") == "mvs-builder":
                try:
                    from ..memory.rag.mvs_rag import enhance_mvs_prompt_with_rag
                    system_prompt = await enhance_mvs_prompt_with_rag(user_text, system_prompt)
                    log_line("agent:mvs:rag:stream", {"enhanced": True, "userText": user_text})
                except Exception as e:
                    log_line("agent:mvs:rag_error:stream", {"error": str(e)})
            
            # Map model ID to OpenRouter format
            openrouter_model = _map_model_id(model)
            
            # Build messages with conversation history
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            # Add conversation history for context awareness
            messages.extend(conversation_history)
            # Add current request with context
            messages.append({"role": "user", "content": context_prefix})
            
            # Stream from OpenRouter
            accumulated_reasoning = ""
            accumulated_content = ""
            thinking_steps: List[Dict[str, Any]] = []
            current_step: Optional[Dict[str, Any]] = None
            
            log_line("agent:stream:code:start", {**base_log, "userText": user_text})
            
            # Call streaming API (synchronous generator, but we're in async context)
            stream_gen = _call_openrouter_api_stream(
                model=openrouter_model,
                messages=messages,
                max_tokens=1200,
                temperature=0.2,
            )
            for chunk in stream_gen:
                if chunk["type"] == "reasoning":
                    accumulated_reasoning += chunk["data"]
                    completed_step, current_step = _parse_incremental_thinking_step(accumulated_reasoning, current_step)
                    
                    if completed_step:
                        completed_step["status"] = "completed"
                        existing_idx = next((i for i, s in enumerate(thinking_steps) if s["id"] == completed_step["id"]), None)
                        if existing_idx is not None:
                            thinking_steps[existing_idx] = completed_step
                        else:
                            thinking_steps.append(completed_step)
                        yield {"type": "thinking_step", "data": completed_step}
                    
                    if current_step:
                        existing_idx = next((i for i, s in enumerate(thinking_steps) if s["id"] == current_step["id"]), None)
                        if existing_idx is not None:
                            thinking_steps[existing_idx] = current_step
                        else:
                            thinking_steps.append(current_step)
                        yield {"type": "thinking_step", "data": current_step}
                
                elif chunk["type"] == "content":
                    accumulated_content += chunk["data"]
                    yield {"type": "content", "data": {"text": chunk["data"]}}
            
            # Finalize any remaining step
            if current_step:
                current_step["status"] = "completed"
                current_step["content"] = current_step.get("content", "").strip()
                existing_idx = next((i for i, s in enumerate(thinking_steps) if s["id"] == current_step["id"]), None)
                if existing_idx is not None:
                    thinking_steps[existing_idx] = current_step
                else:
                    thinking_steps.append(current_step)
                yield {"type": "thinking_step", "data": current_step}
            
            # Extract code from content
            log_line("agent:stream:code:extract", {
                **base_log,
                "accumulated_content_length": len(accumulated_content),
                "accumulated_content_preview": accumulated_content[:200] if accumulated_content else None
            })
            
            code, explanation_text = extract_code_and_text(accumulated_content)
            
            # If no code found, log warning but still return result with thinking process
            if not code or not code.strip():
                log_line("agent:stream:code:empty", {
                    **base_log,
                    "accumulated_content_length": len(accumulated_content),
                    "has_thinking_steps": len(thinking_steps) > 0,
                    "has_text": bool(explanation_text)
                })
            
            # Safety pass (simplified for streaming)
            if code and code.strip() and violates_whitelist(code):
                log_line("safety:whitelist:stream", {"blocked": True})
                # For streaming, we'll just log the violation
                code = ensure_clear_on_change(current_code, code)
            
            if code and code.strip():
                code = ensure_clear_on_change(current_code, code)
            else:
                # If code is empty, keep it empty (don't use current_code)
                code = ""
            
            # Build final result - always include thinking process if available
            final_result = {
                "type": "code",
                "code": code,
            }
            # Include text explanation if available
            if explanation_text:
                final_result["text"] = explanation_text
            
            # Add thinking process if we have steps (even if code is empty)
            if thinking_steps:
                final_result["thinkingProcess"] = {
                    "steps": thinking_steps,
                    "isComplete": True,
                    "totalSteps": len(thinking_steps)
                }
            
            log_line("agent:stream:code:complete", {
                **base_log,
                "code_length": len(code) if code else 0,
                "steps_count": len(thinking_steps),
                "has_thinking_process": "thinkingProcess" in final_result
            })
            yield {"type": "complete", "data": final_result}
            return
            
        except Exception as e:
            log_line("agent:stream:code:error", {**base_log, "error": str(e), "trace": traceback.format_exc()})
            yield {"type": "error", "data": {"error": str(e)}}
            return
    
    # Handle text agents (existing code)
    
    try:
        # Build messages (same logic as run_agent for text agents)
        selection_lines = []
        code_pdb_id = None
        structure_origin_context = None
        
        # Add uploaded file context if available
        uploaded_file_info = ""
        if uploaded_file_context:
            filename = uploaded_file_context.get("filename", "uploaded file")
            atoms = uploaded_file_context.get("atoms", 0)
            chains = uploaded_file_context.get("chains", [])
            file_url = uploaded_file_context.get("file_url", "")
            uploaded_file_info = (
                f"UploadedFileContext: User has uploaded a PDB file named '{filename}' "
                f"({atoms} atoms, {len(chains)} chain{'s' if len(chains) != 1 else ''}: {', '.join(chains) if chains else 'N/A'}). "
                f"The file is available at: {file_url}. "
                f"When answering questions about this structure, refer to it as the uploaded file '{filename}'.\n\n"
            )
        
        if current_code and str(current_code).strip():
            import re
            # Check for blob URL (RF diffusion/AlphaFold result)
            blob_match = re.search(r"loadStructure\s*\(\s*['\"](blob:[^'\"]+)['\"]", str(current_code))
            if blob_match:
                # This is a generated structure, check current_structure_origin or history for origin
                if current_structure_origin:
                    origin_type = current_structure_origin.get("type", "unknown")
                    if origin_type == "rfdiffusion":
                        params = current_structure_origin.get("parameters", {})
                        structure_origin_context = (
                            f"Current Structure: This is a protein structure generated using RFdiffusion protein design. "
                            f"Design mode: {params.get('design_mode', 'unknown')}. "
                        )
                        if params.get("contigs"):
                            structure_origin_context += f"Contigs: {params.get('contigs')}. "
                        if params.get("diffusion_steps"):
                            structure_origin_context += f"Diffusion steps: {params.get('diffusion_steps')}. "
                        if current_structure_origin.get("filename"):
                            structure_origin_context += f"Filename: {current_structure_origin.get('filename')}. "
                        structure_origin_context += (
                            "This structure does not have a PDB ID because it was computationally generated, "
                            "not retrieved from the Protein Data Bank."
                        )
                    elif origin_type == "alphafold":
                        structure_origin_context = (
                            f"Current Structure: This is a protein structure predicted using AlphaFold2. "
                        )
                        if current_structure_origin.get("filename"):
                            structure_origin_context += f"Filename: {current_structure_origin.get('filename')}. "
                        structure_origin_context += (
                            "This structure does not have a PDB ID because it was computationally predicted, "
                            "not retrieved from the Protein Data Bank."
                        )
                    elif origin_type == "upload":
                        structure_origin_context = (
                            f"Current Structure: This is a protein structure loaded from an uploaded PDB file. "
                        )
                        if current_structure_origin.get("filename"):
                            structure_origin_context += f"Filename: {current_structure_origin.get('filename')}. "
                else:
                    # Fallback: check history for structure metadata
                    if history:
                        import json
                        for msg in reversed(history):  # Check most recent first
                            if msg.get("type") == "ai" and msg.get("alphafoldResult"):
                                result = msg["alphafoldResult"]
                                job_type = result.get("jobType", "unknown")
                                params = result.get("parameters", {})
                                
                                if job_type == "rfdiffusion":
                                    structure_origin_context = (
                                        f"Current Structure: This structure was generated using RFdiffusion protein design. "
                                        f"Design mode: {params.get('design_mode', 'unknown')}. "
                                    )
                                    if params.get("contigs"):
                                        structure_origin_context += f"Contigs: {params.get('contigs')}. "
                                    structure_origin_context += (
                                        "This structure does not have a PDB ID because it was computationally generated."
                                    )
                                    break
                                elif job_type == "alphafold":
                                    structure_origin_context = (
                                        "Current Structure: This structure was predicted using AlphaFold2. "
                                        "This structure does not have a PDB ID because it was computationally predicted."
                                    )
                                    break
            
            # Check for PDB ID (traditional structure)
            pdb_match = re.search(r"loadStructure\s*\(\s*['\"]([0-9A-Za-z]{4})['\"]", str(current_code))
            if pdb_match:
                code_pdb_id = pdb_match.group(1).upper()
                if not structure_origin_context:
                    structure_origin_context = f"Current Structure: PDB ID {code_pdb_id} (from Protein Data Bank)."
        
        active_selections = selections if selections and len(selections) > 0 else ([selection] if selection else [])
        
        if active_selections:
            selection_lines.append(f"SelectedResiduesContext ({len(active_selections)} residue{'s' if len(active_selections) != 1 else ''}):")
            for i, sel in enumerate(active_selections):
                chain = sel.get('labelAsymId') or sel.get('authAsymId') or '?'
                seq_id = sel.get('labelSeqId') if sel.get('labelSeqId') is not None else sel.get('authSeqId')
                comp_id = sel.get('compId') or '?'
                pdb_id = sel.get('pdbId') or code_pdb_id or 'unknown'
                selection_lines.append(f"  {i+1}. {comp_id}{seq_id} (Chain {chain}) in PDB {pdb_id}")
                selection_lines.append(f"     - Residue Type: {comp_id}")
                selection_lines.append(f"     - Position: {seq_id}")
                selection_lines.append(f"     - Chain: {chain}")
                selection_lines.append(f"     - PDB Structure: {pdb_id}")
                if sel.get('insCode'):
                    selection_lines.append(f"     - Insertion Code: {sel.get('insCode')}")
            
            if len(active_selections) > 1:
                selection_lines.append(f"Note: User has selected {len(active_selections)} residues for analysis or comparison.")
            else:
                selection_lines.append("Note: User has selected this specific residue for analysis.")
        
        selection_context = "Context:\n" + "\n".join(selection_lines) if selection_lines else ""
        code_context = (
            f"CodeContext (Current PDB: {code_pdb_id or 'unknown'}):\n" + str(current_code)[:3000]
            if current_code and str(current_code).strip()
            else ""
        )
        
        # Add structure origin context to code_context
        if structure_origin_context:
            if code_context:
                code_context = structure_origin_context + "\n\n" + code_context
            else:
                code_context = structure_origin_context
        
        # Also add recent history context about generated structures
        history_context_lines = []
        if history:
            import json
            for msg in history[-3:]:  # Last 3 messages
                if msg.get("type") == "ai" and msg.get("alphafoldResult"):
                    result = msg["alphafoldResult"]
                    job_type = result.get("jobType", "unknown")
                    if job_type == "rfdiffusion":
                        params = result.get("parameters", {})
                        history_context_lines.append(
                            f"Recent RFdiffusion result: {result.get('filename', 'unknown')} "
                            f"(design mode: {params.get('design_mode', 'unknown')})"
                        )
                    elif job_type == "alphafold":
                        history_context_lines.append(
                            f"Recent AlphaFold2 prediction: {result.get('filename', 'unknown')}"
                        )
        
        # Detect if user input is a greeting or conversational (not asking about structure)
        user_text_lower = user_text.lower().strip()
        greeting_patterns = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "thanks", "thank you", "ok", "okay"]
        is_greeting = any(pattern in user_text_lower for pattern in greeting_patterns) and len(user_text.strip()) < 30
        
        messages: List[Dict[str, Any]] = []
        context_parts = []
        if uploaded_file_info:
            context_parts.append(uploaded_file_info)
        if history_context_lines:
            context_parts.append("Recent Structure Generation History:\n" + "\n".join(history_context_lines))
        if selection_context:
            context_parts.append(selection_context)
        # Only include code/structure context if user is NOT just greeting
        # For greetings, skip structure context to avoid describing structures unnecessarily
        if code_context and not is_greeting:
            context_parts.append(code_context)
        
        if context_parts:
            messages.append({"role": "user", "content": "\n\n".join(context_parts)})
        messages.append({"role": "user", "content": user_text})
        
        # Prepare messages with system prompt
        openrouter_messages = []
        system_prompt = agent.get("system")
        if system_prompt:
            openrouter_messages.append({"role": "system", "content": system_prompt})
        openrouter_messages.extend(messages)
        
        # Map model ID to OpenRouter format
        openrouter_model = _map_model_id(model)
        
        # Stream from OpenRouter
        accumulated_reasoning = ""
        accumulated_content = ""
        thinking_steps: List[Dict[str, Any]] = []
        current_step: Optional[Dict[str, Any]] = None
        step_counter = 0
        
        log_line("agent:stream:start", {**base_log, "userText": user_text})
        
        reasoning_chunks = 0
        content_chunks = 0
        
        for chunk in _call_openrouter_api_stream(
            model=openrouter_model,
            messages=openrouter_messages,
            max_tokens=1000,
            temperature=0.5,
        ):
            log_line("agent:stream:chunk", {"type": chunk.get("type"), "agentId": agent.get("id")})
            
            if chunk["type"] == "reasoning":
                reasoning_chunks += 1
                # Accumulate reasoning tokens
                accumulated_reasoning += chunk["data"]
                
                # Parse incremental thinking steps
                completed_step, current_step = _parse_incremental_thinking_step(accumulated_reasoning, current_step)
                
                # Emit completed step
                if completed_step:
                    completed_step["status"] = "completed"
                    # Check if step already exists
                    existing_idx = next((i for i, s in enumerate(thinking_steps) if s["id"] == completed_step["id"]), None)
                    if existing_idx is not None:
                        thinking_steps[existing_idx] = completed_step
                    else:
                        thinking_steps.append(completed_step)
                    yield {"type": "thinking_step", "data": completed_step}
                
                # Emit current step if it exists
                if current_step:
                    # Check if step already exists
                    existing_idx = next((i for i, s in enumerate(thinking_steps) if s["id"] == current_step["id"]), None)
                    if existing_idx is not None:
                        thinking_steps[existing_idx] = current_step
                    else:
                        thinking_steps.append(current_step)
                    yield {"type": "thinking_step", "data": current_step}
            
            elif chunk["type"] == "content":
                content_chunks += 1
                # Accumulate content tokens
                accumulated_content += chunk["data"]
                yield {"type": "content", "data": {"text": chunk["data"]}}
        
        log_line("agent:stream:chunks_received", {
            **base_log, 
            "reasoning_chunks": reasoning_chunks, 
            "content_chunks": content_chunks,
            "accumulated_reasoning_length": len(accumulated_reasoning),
            "accumulated_content_length": len(accumulated_content)
        })
        
        # Finalize any remaining step
        if current_step:
            current_step["status"] = "completed"
            current_step["content"] = current_step.get("content", "").strip()
            existing_idx = next((i for i, s in enumerate(thinking_steps) if s["id"] == current_step["id"]), None)
            if existing_idx is not None:
                thinking_steps[existing_idx] = current_step
            else:
                thinking_steps.append(current_step)
            yield {"type": "thinking_step", "data": current_step}
        
        # Build final result
        final_result = {
            "type": "text",
            "text": accumulated_content.strip(),
        }
        
        # Add thinking process if we have steps
        if thinking_steps:
            final_result["thinkingProcess"] = {
                "steps": thinking_steps,
                "isComplete": True,
                "totalSteps": len(thinking_steps)
            }
        
        log_line("agent:stream:complete", {**base_log, "text_length": len(accumulated_content), "steps_count": len(thinking_steps)})
        yield {"type": "complete", "data": final_result}
        
    except Exception as e:
        log_line("agent:stream:error", {**base_log, "error": str(e), "trace": traceback.format_exc()})
        yield {"type": "error", "data": {"error": str(e)}}

