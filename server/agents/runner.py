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
    from .runner_utils import map_model_id
except ImportError:
    from infrastructure.utils import log_line, get_text_from_completion, strip_code_fences, trim_history, extract_code_and_text
    from infrastructure.safety import violates_whitelist, ensure_clear_on_change
    from domain.protein.uniprot import search_uniprot
    from agents.runner_utils import map_model_id


_openrouter_api_key: Optional[str] = None


def _get_openrouter_api_key(api_key: Optional[str] = None) -> Optional[str]:    
    """Get OpenRouter API key from OPENROUTER_API_KEY env var."""
    global _openrouter_api_key
    
    # If a specific key is provided (e.g. from client request), use it (strip whitespace)
    if api_key:
        return (api_key or "").strip() or None

    # Return cached key if available
    if _openrouter_api_key:
        return _openrouter_api_key

    openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
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
        raise RuntimeError(
            "OpenRouter API key is missing. Please set OPENROUTER_API_KEY in server/.env (see https://openrouter.ai)"
        )
    
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
    tools: Optional[List[Dict[str, Any]]] = None,
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
        tools: Optional list of OpenRouter tool definitions (function-calling format).
    """
    key = _get_openrouter_api_key(api_key)
    if not key:
        raise RuntimeError(
            "OpenRouter API key is missing. Please set OPENROUTER_API_KEY in server/.env (see https://openrouter.ai)"
        )
    
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
    if tools:
        payload["tools"] = tools
    
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
            
            resp = CompletionResponse(data, thinking_data)
            resp._raw_data = data  # So caller can read tool_calls from choices[0].message
            return resp
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
                    user_message = (
                        "OpenRouter API key is invalid or missing. "
                        "Set OPENROUTER_API_KEY in server/.env with a valid key from https://openrouter.ai"
                    )
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
                        # OpenRouter error format: {"error": {"message": "...", "type": "...", ...}} or {"error": "User not found."}
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
                                # OpenRouter returns "User not found." for invalid/missing key; keep 401 user_message
                                if status_code == 401 and "user not found" in (error_detail or "").lower():
                                    pass  # user_message already set above for 401
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


def _invoke_llm_agent(
    agent: Dict[str, Any],
    messages: List[Dict[str, Any]],
    model_override: Optional[str] = None,
    *,
    current_code: Optional[str] = None,
    temperature: float = 0.5,
    max_tokens: int = 1000,
) -> Dict[str, Any]:
    """Single LLM path: convert messages, invoke compiled agent, return app result.
    Used by text and code agents after message building.
    """
    model = model_override or os.getenv(agent.get("modelEnv", "")) or agent.get("defaultModel")
    api_key = _get_openrouter_api_key()
    try:
        from .llm.messages import openrouter_to_langchain
        from .langchain_agent import get_agent, agent_output_to_app_result
        lc_messages = openrouter_to_langchain(messages)
        compiled = get_agent(agent["id"], model, api_key=api_key, temperature=temperature, max_tokens=max_tokens)
        final_state = compiled.invoke({"messages": lc_messages}, config={"recursion_limit": 25})
        return agent_output_to_app_result(final_state, agent["kind"], current_code=current_code)
    except Exception as e:
        if "Rate limit exceeded" in str(e) and not model_override:
            default_model = os.getenv(agent.get("modelEnv", "")) or agent.get("defaultModel")
            if default_model != model:
                log_line("runner:model:fallback", {"from": model, "to": default_model, "reason": "rate_limit", "agentId": agent.get("id")})
                try:
                    from .llm.messages import openrouter_to_langchain
                    from .langchain_agent import get_agent, agent_output_to_app_result
                    lc_messages = openrouter_to_langchain(messages)
                    compiled = get_agent(agent["id"], default_model, api_key=api_key, temperature=temperature, max_tokens=max_tokens)
                    final_state = compiled.invoke({"messages": lc_messages}, config={"recursion_limit": 25})
                    return agent_output_to_app_result(final_state, agent["kind"], current_code=current_code)
                except Exception as fallback_error:
                    raise RuntimeError(
                        f"Rate limit exceeded for model '{model}'. Fallback to '{default_model}' also failed: {str(fallback_error)}"
                    ) from fallback_error
        raise


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


async def _run_code_agent(
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
    pdb_content: Optional[str] = None,
) -> Dict[str, Any]:
    """Reusable code-generation agent path (code-builder, mvs-builder)."""
    if model_override:
        model = model_override
    else:
        model = os.getenv(agent.get("modelEnv", "")) or agent.get("defaultModel")
    base_log = {"model": model, "agentId": agent.get("id"), "model_override": bool(model_override)}
    import re
    code_pdb_id = None
    if current_code and str(current_code).strip():
        pdb_match = re.search(r"loadStructure\s*\(\s*['\"]([0-9A-Za-z]{4})['\"]", str(current_code))
        if pdb_match:
            code_pdb_id = pdb_match.group(1).upper()
            structure_metadata = f"\n\nStructure Context: The current code loads PDB ID {code_pdb_id}. "
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
        f"Existing code:\n\n```js\n{str(current_code)}\n```\n\nRequest: {user_text}{uploaded_file_info}{structure_metadata or ''}"
        if current_code and str(current_code).strip()
        else f"Generate Molstar builder code for: {user_text}{uploaded_file_info}{structure_metadata or ''}"
    )
    conversation_history = []
    if history:
        for msg in history[-6:]:
            msg_type = msg.get("type", "")
            msg_content = msg.get("content", "")
            if msg_type == "user":
                conversation_history.append({"role": "user", "content": msg_content})
            elif msg_type == "ai":
                conversation_history.append({"role": "assistant", "content": msg_content})
    system_prompt = agent.get("system")
    if agent.get("id") == "mvs-builder":
        try:
            from ..memory.rag.mvs_rag import enhance_mvs_prompt_with_rag
            system_prompt = await enhance_mvs_prompt_with_rag(user_text, system_prompt)
            log_line("agent:mvs:rag", {"enhanced": True, "userText": user_text})
        except Exception as e:
            log_line("agent:mvs:rag_error", {"error": str(e)})
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": context_prefix})
    log_line("agent:code:req", {**base_log, "hasCurrentCode": bool(current_code and str(current_code).strip()), "userText": user_text})
    result = _invoke_llm_agent(
        agent, messages, model_override,
        current_code=current_code,
        temperature=0.2,
        max_tokens=1200,
    )
    log_line("agent:code:res", {"length": len(result.get("code", "")), "has_text": bool(result.get("text"))})
    return result


async def _run_llm_text_agent(
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
    pdb_content: Optional[str] = None,
) -> Dict[str, Any]:
    """Reusable LLM text agent path (bio-chat, pipeline-agent). Handles SMILES tools via LangGraph when applicable."""
    if model_override:
        model = model_override
    else:
        model = os.getenv(agent.get("modelEnv", "")) or agent.get("defaultModel")
    base_log = {"model": model, "agentId": agent.get("id"), "model_override": bool(model_override)}
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
    code_pdb_id = None
    structure_origin_context = None
    if current_code and str(current_code).strip():
        import re
        blob_match = re.search(r"loadStructure\s*\(\s*['\"](blob:[^'\"]+)['\"]", str(current_code))
        if blob_match:
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
                if history:
                    for msg in reversed(history):
                        if msg.get("type") == "ai" and msg.get("alphafoldResult"):
                            res = msg["alphafoldResult"]
                            job_type = res.get("jobType", "unknown")
                            params = res.get("parameters", {})
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
        pdb_match = re.search(r"loadStructure\s*\(\s*['\"]([0-9A-Za-z]{4})['\"]", str(current_code))
        if pdb_match:
            code_pdb_id = pdb_match.group(1).upper()
            if not structure_origin_context:
                structure_origin_context = f"Current Structure: PDB ID {code_pdb_id} (from Protein Data Bank)."
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
    structure_label = None
    summarized_structure_context = ""
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
    active_selections = selections if selections and len(selections) > 0 else ([selection] if selection else [])
    selection_lines = []
    if active_selections:
        selection_lines.append(f"SelectedResiduesContext ({len(active_selections)} residue{'s' if len(active_selections) != 1 else ''}):")
        for i, sel in enumerate(active_selections):
            chain = sel.get("labelAsymId") or sel.get("authAsymId") or "?"
            seq_id = sel.get("labelSeqId") if sel.get("labelSeqId") is not None else sel.get("authSeqId")
            comp_id = sel.get("compId") or "?"
            pdb_id = sel.get("pdbId") or code_pdb_id or "unknown"
            selection_lines.append(f"  {i+1}. {comp_id}{seq_id} (Chain {chain}) in PDB {pdb_id}")
            selection_lines.append(f"     - Residue Type: {comp_id}")
            selection_lines.append(f"     - Position: {seq_id}")
            selection_lines.append(f"     - Chain: {chain}")
            selection_lines.append(f"     - PDB Structure: {pdb_id}")
            if sel.get("insCode"):
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
    if structure_origin_context:
        code_context = structure_origin_context + ("\n\n" + code_context if code_context else "")
    history_context_lines = []
    if history:
        for msg in history[-3:]:
            if msg.get("type") == "ai" and msg.get("alphafoldResult"):
                res = msg["alphafoldResult"]
                job_type = res.get("jobType", "unknown")
                if job_type == "rfdiffusion":
                    params = res.get("parameters", {})
                    history_context_lines.append(
                        f"Recent RFdiffusion result: {res.get('filename', 'unknown')} "
                        f"(design mode: {params.get('design_mode', 'unknown')})"
                    )
                elif job_type == "alphafold":
                    history_context_lines.append(f"Recent AlphaFold2 prediction: {res.get('filename', 'unknown')}")
    user_text_lower = user_text.lower().strip()
    greeting_patterns = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "thanks", "thank you", "ok", "okay"]
    is_greeting = any(p in user_text_lower for p in greeting_patterns) and len(user_text.strip()) < 30
    pipeline_context_info = ""
    if pipeline_id and pipeline_data:
        try:
            from ..domain.pipeline.context import get_pipeline_summary
            summary = await get_pipeline_summary(pipeline_id, pipeline_data)
            pipeline_context_lines = [
                f"Pipeline Context: {summary.get('name', 'Unnamed Pipeline')} (ID: {summary.get('pipeline_id')})"
            ]
            if summary.get("status"):
                pipeline_context_lines.append(f"Status: {summary['status']}")
            if summary.get("node_count"):
                pipeline_context_lines.append(f"Total nodes: {summary['node_count']}")
            if summary.get("node_details"):
                node_list = []
                for node in summary["node_details"]:
                    parts = [f"{node.get('label', node.get('id'))} (type: {node.get('type')}, status: {node.get('status', 'idle')})"]
                    cfg = node.get("config")
                    if cfg:
                        parts.append("config: {" + ", ".join(f"{k}={v}" for k, v in cfg.items()) + "}")
                    if node.get("error"):
                        parts.append(f"error: {node['error']}")
                    node_list.append(" | ".join(parts))
                if node_list:
                    pipeline_context_lines.append("Nodes: " + "; ".join(node_list))
            if summary.get("execution_flow") and isinstance(summary["execution_flow"], list) and summary["execution_flow"]:
                pipeline_context_lines.append(f"Execution flow: {' → '.join(summary['execution_flow'])}")
            if summary.get("nodes_by_type"):
                type_summary = [f"{len(nodes)} {t}" for t, nodes in summary["nodes_by_type"].items()]
                if type_summary:
                    pipeline_context_lines.append(f"Node types: {', '.join(type_summary)}")
            output_files = []
            for node in pipeline_data.get("nodes", []):
                result_metadata = node.get("result_metadata") or {}
                if result_metadata.get("output_file"):
                    output_files.append(f"{node.get('label', node.get('id'))}: {result_metadata['output_file'].get('filename', 'output file')}")
                if result_metadata.get("sequence"):
                    output_files.append(f"{node.get('label', node.get('id'))}: sequence output")
            if output_files:
                pipeline_context_lines.append(f"Output files: {', '.join(output_files)}")
            if summary.get("recent_executions"):
                exec_lines = [f"{ex.get('status','?')} ({ex.get('trigger_type','?')}) at {ex.get('started_at','?')}" for ex in summary["recent_executions"]]
                pipeline_context_lines.append("Recent executions: " + "; ".join(exec_lines))
            if summary.get("latest_node_executions"):
                ne_lines = [f"[{ne.get('execution_order','-')}] {ne.get('node_label',ne.get('node_id'))} ({ne.get('node_type')}): {ne.get('status','?')}" for ne in summary["latest_node_executions"]]
                pipeline_context_lines.append("Latest run node log: " + "; ".join(ne_lines))
            if summary.get("node_files"):
                file_lines = [f"{nf.get('filename','?')} ({nf.get('role','?')}/{nf.get('file_type','?')}) on node {nf.get('node_id','?')}" for nf in summary["node_files"]]
                pipeline_context_lines.append("Pipeline files: " + "; ".join(file_lines))
            pipeline_context_info = "Pipeline Context:\n" + "\n".join(pipeline_context_lines)
        except Exception as e:
            log_line("agent:text:pipeline_context_error", {"error": str(e), "pipeline_id": pipeline_id, "has_pipeline_data": bool(pipeline_data)})
    elif pipeline_id:
        pipeline_context_info = f"Pipeline Context: Pipeline ID {pipeline_id} is attached to this message. Full pipeline details could not be loaded."
    conversation_history = []
    if history:
        for msg in history[-6:]:
            msg_type = msg.get("type", "")
            msg_content = msg.get("content", "")
            if msg_type == "user":
                conversation_history.append({"role": "user", "content": msg_content})
            elif msg_type == "ai":
                conversation_history.append({"role": "assistant", "content": msg_content})
    messages = []
    context_parts = []
    if uploaded_file_info:
        context_parts.append(uploaded_file_info)
    if pipeline_context_info:
        context_parts.append(pipeline_context_info)
    if history_context_lines:
        context_parts.append("Recent Structure Generation History:\n" + "\n".join(history_context_lines))
    if selection_context:
        context_parts.append(selection_context)
    if summarized_structure_context and not is_greeting:
        context_parts.append(summarized_structure_context)
    if code_context and not is_greeting:
        context_parts.append(code_context)
    if context_parts:
        messages.append({"role": "user", "content": "\n\n".join(context_parts)})
    messages.append({"role": "user", "content": user_text})
    log_line("agent:text:req", {**base_log, "hasSelection": bool(selection), "userText": user_text})
    openrouter_messages = []
    system_prompt = agent.get("system")
    if system_prompt:
        openrouter_messages.append({"role": "system", "content": system_prompt})
    openrouter_messages.extend(conversation_history)
    openrouter_messages.extend(messages)
    result = _invoke_llm_agent(agent, openrouter_messages, model_override, temperature=0.5, max_tokens=1000)
    log_line("agent:text:res", {"length": len(result.get("text", "")), "tool_count": len(result.get("toolResults") or [])})
    return result


def _build_react_messages(
    *,
    user_text: str,
    current_code: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    selection: Optional[Dict[str, Any]] = None,
    selections: Optional[List[Dict[str, Any]]] = None,
    uploaded_file_context: Optional[Dict[str, Any]] = None,
    structure_metadata: Optional[Dict[str, Any]] = None,
    pipeline_id: Optional[str] = None,
    pipeline_data: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Build OpenRouter-style message list for the ReAct agent (system + context + history + user)."""
    context_parts = []
    if uploaded_file_context:
        fn = uploaded_file_context.get("filename", "uploaded file")
        chains = uploaded_file_context.get("chains", [])
        context_parts.append(f"UploadedFileContext: User has uploaded '{fn}' (chains: {', '.join(chains) or 'N/A'}).")
    if pipeline_id and pipeline_data:
        context_parts.append(f"Pipeline Context: Pipeline '{pipeline_data.get('name', pipeline_id)}' is attached.")
    if selection or (selections and len(selections) > 0):
        sel_list = selections if selections and len(selections) > 0 else ([selection] if selection else [])
        for s in sel_list:
            chain = (s or {}).get("labelAsymId") or (s or {}).get("authAsymId") or "?"
            seq_id = (s or {}).get("labelSeqId") if (s or {}).get("labelSeqId") is not None else (s or {}).get("authSeqId")
            comp = (s or {}).get("compId") or "?"
            context_parts.append(f"SelectedResiduesContext: {comp}{seq_id} (Chain {chain}).")
    if structure_metadata:
        summary = _build_summarized_structure_context(structure_metadata=structure_metadata)
        if summary:
            context_parts.append(summary)
    if current_code and str(current_code).strip():
        context_parts.append(f"CodeContext (current viewer code):\n{str(current_code)[:2000]}")
    openrouter_messages = [{"role": "system", "content": ""}]
    try:
        from .prompts.bio_chat import REACT_SYSTEM_PROMPT
        openrouter_messages[0]["content"] = REACT_SYSTEM_PROMPT
    except Exception:
        pass
    if history:
        for msg in history[-6:]:
            if msg.get("type") == "user":
                openrouter_messages.append({"role": "user", "content": msg.get("content", "")})
            elif msg.get("type") == "ai":
                openrouter_messages.append({"role": "assistant", "content": msg.get("content", "")})
    if context_parts:
        openrouter_messages.append({"role": "user", "content": "Context:\n" + "\n".join(context_parts)})
    openrouter_messages.append({"role": "user", "content": user_text})
    return openrouter_messages


@traceable(name="RunReactAgent", run_type="chain")
async def run_react_agent(
    *,
    user_text: str,
    current_code: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    selection: Optional[Dict[str, Any]] = None,
    selections: Optional[List[Dict[str, Any]]] = None,
    current_structure_origin: Optional[Dict[str, Any]] = None,
    uploaded_file_context: Optional[Dict[str, Any]] = None,
    structure_metadata: Optional[Dict[str, Any]] = None,
    pipeline_id: Optional[str] = None,
    pipeline_data: Optional[Dict[str, Any]] = None,
    model_override: Optional[str] = None,
    temperature: float = 0.5,
    max_tokens: int = 1000,
) -> Dict[str, Any]:
    """Run the ReAct agent (LLM + tool calling). No keyword routing; LLM decides tools from descriptions."""
    from .llm.messages import openrouter_to_langchain
    from .langchain_agent import get_react_agent
    from .langchain_agent.result import react_state_to_app_result

    model = model_override or os.getenv("CLAUDE_CHAT_MODEL", "claude-3-5-sonnet-20241022")
    api_key = _get_openrouter_api_key()
    openrouter_messages = _build_react_messages(
        user_text=user_text,
        current_code=current_code,
        history=history,
        selection=selection,
        selections=selections,
        uploaded_file_context=uploaded_file_context,
        structure_metadata=structure_metadata,
        pipeline_id=pipeline_id,
        pipeline_data=pipeline_data,
    )
    lc_messages = openrouter_to_langchain(openrouter_messages)
    graph = get_react_agent(model, api_key=api_key, temperature=temperature, max_tokens=max_tokens)
    if hasattr(graph, "ainvoke"):
        final_state = await graph.ainvoke(
            {"messages": lc_messages},
            config={"recursion_limit": 25},
        )
    else:
        final_state = graph.invoke({"messages": lc_messages}, config={"recursion_limit": 25})
    return react_state_to_app_result(final_state)


@traceable(name="RunReactAgentStream", run_type="chain")
async def run_react_agent_stream(
    *,
    user_text: str,
    current_code: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    selection: Optional[Dict[str, Any]] = None,
    selections: Optional[List[Dict[str, Any]]] = None,
    uploaded_file_context: Optional[Dict[str, Any]] = None,
    structure_metadata: Optional[Dict[str, Any]] = None,
    pipeline_id: Optional[str] = None,
    pipeline_data: Optional[Dict[str, Any]] = None,
    model_override: Optional[str] = None,
    temperature: float = 0.5,
    max_tokens: int = 1000,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream ReAct agent: yield content chunks (text-by-text) then complete with full result.
    Uses LangGraph astream(stream_mode="messages") when available for token-level streaming."""
    from .llm.messages import openrouter_to_langchain
    from .langchain_agent import get_react_agent
    from .langchain_agent.result import react_state_to_app_result

    model = model_override or os.getenv("CLAUDE_CHAT_MODEL", "claude-3-5-sonnet-20241022")
    api_key = _get_openrouter_api_key()
    openrouter_messages = _build_react_messages(
        user_text=user_text,
        current_code=current_code,
        history=history,
        selection=selection,
        selections=selections,
        uploaded_file_context=uploaded_file_context,
        structure_metadata=structure_metadata,
        pipeline_id=pipeline_id,
        pipeline_data=pipeline_data,
    )
    lc_messages = openrouter_to_langchain(openrouter_messages)
    graph = get_react_agent(model, api_key=api_key, temperature=temperature, max_tokens=max_tokens)
    config = {"recursion_limit": 25}
    inputs = {"messages": lc_messages}
    last_state: Optional[Dict[str, Any]] = None
    streamed_content: list = []

    def _content_from_event(event: Any) -> Optional[str]:
        """Extract text content from a LangGraph stream event (AI messages only).
        stream_mode='messages' yields (chunk, metadata) tuples where chunk is an
        AIMessageChunk, ToolMessageChunk, etc. We only want AI message content."""
        # Tuple/list: e.g. (chunk, metadata) from messages mode
        if isinstance(event, (list, tuple)) and len(event) >= 1:
            chunk = event[0]
            # Only extract content from AI messages (not tool/human messages)
            chunk_type = getattr(chunk, "type", None) or ""
            if chunk_type not in ("ai", "AIMessageChunk"):
                return None
            if hasattr(chunk, "content"):
                c = chunk.content
                return c if isinstance(c, str) and c else None
            return None
        # Direct message object (AIMessageChunk / BaseMessage) with .content
        if hasattr(event, "content"):
            event_type = getattr(event, "type", None) or ""
            if event_type not in ("ai", "AIMessageChunk"):
                return None
            c = event.content
            return c if isinstance(c, str) and c else None
        # Dict shape
        if isinstance(event, dict):
            if event.get("type") not in ("ai", "AIMessageChunk", None):
                return None
            return event.get("content") or (event.get("chunk") or {}).get("content")
        return None

    try:
        if hasattr(graph, "astream"):
            try:
                print(f"[runner] Starting astream with stream_mode='messages', {len(lc_messages)} input messages")
                event_idx = 0
                # Use stream_mode="messages" for token-level AIMessageChunk events
                async for event in graph.astream(inputs, config=config, stream_mode="messages"):
                    event_idx += 1
                    event_type_str = type(event).__name__
                    if event_idx <= 3:
                        print(f"[runner] astream event #{event_idx}: {event_type_str}, repr={repr(event)[:200]}")
                    content = _content_from_event(event)
                    if isinstance(content, str) and content:
                        streamed_content.append(content)
                        yield {"type": "content", "data": {"text": content}}
                print(f"[runner] astream finished, {event_idx} events, {len(streamed_content)} content chunks, total chars: {sum(len(c) for c in streamed_content)}")
            except (TypeError, ValueError) as e:
                print(f"[runner] astream fallback due to: {e}")
                log_line("agent:react_stream:astream_fallback", {"error": str(e)})
                # Fall through to ainvoke below

        # If astream yielded content, we already ran the graph — DON'T re-run.
        # Build a minimal state from the streamed content for result extraction.
        if streamed_content:
            from langchain_core.messages import AIMessage as _AIMessage
            full_text = "".join(streamed_content)
            last_state = {"messages": lc_messages + [_AIMessage(content=full_text)]}
            print(f"[runner] Built state from streamed content, full_text len={len(full_text)}")
        else:
            # Only run ainvoke if streaming produced nothing (fallback)
            print("[runner] No streamed content, falling back to ainvoke")
            if hasattr(graph, "ainvoke"):
                last_state = await graph.ainvoke(inputs, config=config)
            else:
                last_state = graph.invoke(inputs, config=config)
            print(f"[runner] ainvoke done, state has {len(last_state.get('messages', []))} messages")
    except Exception as e:
        print(f"[runner] EXCEPTION: {e}")
        log_line("agent:react_stream:error", {"error": str(e)})
        yield {"type": "error", "data": {"error": str(e)}}
        return

    if last_state is None:
        print("[runner] ERROR: last_state is None")
        yield {"type": "error", "data": {"error": "No response from agent"}}
        return

    result = react_state_to_app_result(last_state)
    print(f"[runner] Result type={result.get('type')}, text len={len(result.get('text', ''))}, code len={len(result.get('code', ''))}")
    yield {"type": "complete", "data": {"agentId": "react", **result, "reason": "tool_calling"}}


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
    pdb_content: Optional[str] = None,
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

    # Special handling for DiffDock agent - open dialog (protein-ligand docking)
    if agent.get("id") == "diffdock-agent":
        import json
        result = {"action": "open_diffdock_dialog"}
        log_line("agent:diffdock:open_dialog", {"userText": user_text[:100]})
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

    # Special handling for Validation agent - use handler
    if agent.get("id") == "validation-agent":
        try:
            from .handlers.validation import validation_handler
            result = await validation_handler.process_validation_request(
                user_text,
                context={
                    "current_pdb_content": pdb_content,
                    "uploaded_file_context": uploaded_file_context,
                    "file_id": uploaded_file_context.get("file_id") if uploaded_file_context else None,
                    "session_id": None,
                    "user_id": None,
                },
            )
            if result.get("action") == "error":
                log_line("agent:validation:error", {"error": result.get("error"), "userText": user_text})
                return {"type": "text", "text": json.dumps(result)}
            return {"type": "text", "text": json.dumps(result)}
        except Exception as e:
            log_line("agent:validation:failed", {"error": str(e), "userText": user_text})
            return {"type": "text", "text": f"Validation failed: {str(e)}"}

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
        return await _run_code_agent(
            agent=agent,
            user_text=user_text,
            current_code=current_code,
            history=history,
            selection=selection,
            selections=selections,
            current_structure_origin=current_structure_origin,
            uploaded_file_context=uploaded_file_context,
            structure_metadata=structure_metadata,
            pipeline_id=pipeline_id,
            pipeline_data=pipeline_data,
            model_override=model_override,
            user_id=user_id,
            pdb_content=pdb_content,
        )

    # Text agent: delegate to reusable LLM text agent
    return await _run_llm_text_agent(
        agent=agent,
        user_text=user_text,
        current_code=current_code,
        history=history,
        selection=selection,
        selections=selections,
        current_structure_origin=current_structure_origin,
        uploaded_file_context=uploaded_file_context,
        structure_metadata=structure_metadata,
        pipeline_id=pipeline_id,
        pipeline_data=pipeline_data,
        model_override=model_override,
        user_id=user_id,
        pdb_content=pdb_content,
    )



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
            openrouter_model = map_model_id(model)
            
            # Build messages with conversation history
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            # Add conversation history for context awareness
            messages.extend(conversation_history)
            # Add current request with context
            messages.append({"role": "user", "content": context_prefix})
            
            log_line("agent:stream:code:start", {**base_log, "userText": user_text})
            stream_gen = _call_openrouter_api_stream(
                model=openrouter_model,
                messages=messages,
                max_tokens=1200,
                temperature=0.2,
            )
            from .langchain_agent.streaming import process_openrouter_stream
            for event in process_openrouter_stream(
                stream_gen, _parse_incremental_thinking_step, "code", current_code=current_code
            ):
                yield event
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
        
        # Build conversation history so the model can understand "previous chat" / "earlier in this conversation"
        conversation_history_stream: List[Dict[str, Any]] = []
        if history:
            for msg in history[-6:]:
                msg_type = msg.get("type", "")
                msg_content = msg.get("content", "")
                if msg_type == "user":
                    conversation_history_stream.append({"role": "user", "content": msg_content})
                elif msg_type == "ai":
                    conversation_history_stream.append({"role": "assistant", "content": msg_content})
        
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
        
        # Prepare messages: system, then conversation history, then current context + request
        openrouter_messages: List[Dict[str, Any]] = []
        system_prompt = agent.get("system")
        if system_prompt:
            openrouter_messages.append({"role": "system", "content": system_prompt})
        openrouter_messages.extend(conversation_history_stream)
        openrouter_messages.extend(messages)
        
        openrouter_model = map_model_id(model)
        log_line("agent:stream:start", {**base_log, "userText": user_text})
        stream_gen = _call_openrouter_api_stream(
            model=openrouter_model,
            messages=openrouter_messages,
            max_tokens=1000,
            temperature=0.5,
        )
        from .langchain_agent.streaming import process_openrouter_stream
        for event in process_openrouter_stream(stream_gen, _parse_incremental_thinking_step, "text"):
            yield event
        
    except Exception as e:
        log_line("agent:stream:error", {**base_log, "error": str(e), "trace": traceback.format_exc()})
        yield {"type": "error", "data": {"error": str(e)}}


# ---------------------------------------------------------------------------
# Supervisor-pattern streaming: route → build sub-agent → stream
# ---------------------------------------------------------------------------

@traceable(name="RunSupervisorStream", run_type="chain")
async def run_supervisor_stream(
    *,
    user_text: str,
    current_code: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    selection: Optional[Dict[str, Any]] = None,
    selections: Optional[List[Dict[str, Any]]] = None,
    uploaded_file_context: Optional[Dict[str, Any]] = None,
    structure_metadata: Optional[Dict[str, Any]] = None,
    pipeline_id: Optional[str] = None,
    pipeline_data: Optional[Dict[str, Any]] = None,
    model_override: Optional[str] = None,
    manual_agent_id: Optional[str] = None,
    temperature: float = 0.5,
    max_tokens: int = 1000,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Supervisor streaming: route to a sub-agent, then stream its ReAct loop.

    Yields events:
        routing   – which agent was chosen (frontend shows agent pill)
        tool_call – when a tool is invoked (frontend shows tool pill)
        content   – token-level text chunks
        complete  – final result with agentId + toolsInvoked
        error     – on failure
    """
    from .llm.model import get_chat_model
    from .llm.messages import openrouter_to_langchain
    from .supervisor.routing import route_to_agent
    from .langchain_agent.result import react_state_to_app_result

    model = model_override or os.getenv("CLAUDE_CHAT_MODEL", "claude-3-5-sonnet-20241022")
    api_key = _get_openrouter_api_key()

    # ── Step 1: Route ──
    if manual_agent_id:
        agent_id = manual_agent_id
        routing_reason = "manual_override"
    else:
        try:
            routing_llm = get_chat_model(model, api_key, temperature=0, max_tokens=50)
            agent_id, routing_reason = await route_to_agent(routing_llm, user_text, history=history)
        except Exception as e:
            print(f"[supervisor] routing failed, defaulting to bio_chat: {e}")
            agent_id = "bio_chat"
            routing_reason = f"routing_error_fallback:{e}"

    print(f"[supervisor] routed to: {agent_id} ({routing_reason})")
    yield {"type": "routing", "data": {"agentId": agent_id, "reason": routing_reason}}

    # ── Direct actions: dialog triggers bypass sub-agent entirely ──
    _DIRECT_ACTION_MAP = {
        "alphafold": {"action": "open_alphafold_dialog"},
        "openfold": {"action": "open_openfold2_dialog"},
        "rfdiffusion": {"action": "open_rfdiffusion_dialog"},
        "proteinmpnn": {"action": "open_proteinmpnn_dialog"},
        "diffdock": {"action": "open_diffdock_dialog"},
    }
    if agent_id in _DIRECT_ACTION_MAP:
        action_json = json.dumps(_DIRECT_ACTION_MAP[agent_id])
        print(f"[supervisor] direct action: {agent_id} → {action_json}")
        yield {"type": "complete", "data": {
            "type": "text",
            "text": action_json,
            "agentId": agent_id,
            "toolsInvoked": [],
        }}
        return

    # ── Step 2: Build sub-agent graph ──
    try:
        graph = await _build_supervisor_sub_agent(agent_id, model, api_key,
                                                   user_query=user_text,
                                                   temperature=temperature,
                                                   max_tokens=max_tokens)
    except Exception as e:
        print(f"[supervisor] failed to build sub-agent {agent_id}: {e}")
        yield {"type": "error", "data": {"error": f"Failed to build agent: {e}"}}
        return

    # ── Step 3: Build messages (reuse existing helper) ──
    openrouter_messages = _build_react_messages(
        user_text=user_text,
        current_code=current_code,
        history=history,
        selection=selection,
        selections=selections,
        uploaded_file_context=uploaded_file_context,
        structure_metadata=structure_metadata,
        pipeline_id=pipeline_id,
        pipeline_data=pipeline_data,
    )
    lc_messages = openrouter_to_langchain(openrouter_messages)
    # Strip the hardcoded bio_chat system message — each sub-agent graph
    # now prepends its own specialised system prompt via build_agent_graph.
    from langchain_core.messages import SystemMessage as _SM
    lc_messages = [m for m in lc_messages if not isinstance(m, _SM)]
    config = {"recursion_limit": 25}
    inputs = {"messages": lc_messages}

    # ── Step 4: Stream sub-agent ──
    streamed_content: list = []
    tools_invoked: list = []
    tool_calls_captured: list = []
    tool_call_chunk_buffers: Dict[int, Dict[str, Any]] = {}
    last_state: Optional[Dict[str, Any]] = None

    try:
        if hasattr(graph, "astream"):
            print(f"[supervisor] Starting astream for {agent_id}, {len(lc_messages)} input messages")
            event_idx = 0
            async for event in graph.astream(inputs, config=config, stream_mode="messages"):
                event_idx += 1
                # Extract text content (AI messages only)
                content = _supervisor_content_from_event(event)
                if isinstance(content, str) and content:
                    streamed_content.append(content)
                    yield {"type": "content", "data": {"text": content}}
                # Detect tool calls for tool pills
                tool_call = _supervisor_tool_call_from_event(event)
                if tool_call:
                    tool_calls_captured.append(tool_call)
                chunk_entries = _supervisor_tool_call_chunks_from_event(event)
                if chunk_entries:
                    for chunk_entry in chunk_entries:
                        idx = int(chunk_entry.get("index", 0) or 0)
                        buf = tool_call_chunk_buffers.get(idx) or {"id": None, "name": None, "args_text": ""}
                        if chunk_entry.get("id"):
                            buf["id"] = chunk_entry.get("id")
                        if chunk_entry.get("name"):
                            buf["name"] = chunk_entry.get("name")
                        args_fragment = chunk_entry.get("args")
                        if isinstance(args_fragment, str):
                            buf["args_text"] += args_fragment
                        tool_call_chunk_buffers[idx] = buf
                tool_name = tool_call.get("name") if isinstance(tool_call, dict) else _supervisor_tool_from_event(event)
                if tool_name and tool_name not in tools_invoked:
                    tools_invoked.append(tool_name)
                    yield {"type": "tool_call", "data": {"name": tool_name}}
            print(f"[supervisor] astream done: {event_idx} events, {len(streamed_content)} content chunks")

        if streamed_content and not tools_invoked:
            from langchain_core.messages import AIMessage as _AIMessage
            full_text = "".join(streamed_content)
            last_state = {"messages": lc_messages + [_AIMessage(content=full_text)]}
        else:
            if streamed_content and tools_invoked:
                print(
                    f"[supervisor] tools invoked during stream ({tools_invoked}); "
                    "running ainvoke once to preserve tool results in final state"
                )
            else:
                print(f"[supervisor] No streamed content, falling back to ainvoke for {agent_id}")
            if hasattr(graph, "ainvoke"):
                last_state = await graph.ainvoke(inputs, config=config)
            else:
                last_state = graph.invoke(inputs, config=config)
    except Exception as e:
        print(f"[supervisor] EXCEPTION during {agent_id} execution: {e}")
        log_line("supervisor:stream:error", {"agentId": agent_id, "error": str(e)})
        yield {"type": "error", "data": {"error": str(e)}}
        return

    if last_state is None:
        yield {"type": "error", "data": {"error": "No response from agent"}}
        return

    # ── Step 5: Build result with agent + tools metadata ──
    result = react_state_to_app_result(last_state)
    if tool_calls_captured or tool_call_chunk_buffers:
        try:
            try:
                from .smiles_tool import process_tool_calls
            except ImportError:
                from agents.smiles_tool import process_tool_calls
            normalized_calls = []
            chunk_calls = []
            for _, chunk_buf in sorted(tool_call_chunk_buffers.items(), key=lambda kv: kv[0]):
                args_text = (chunk_buf.get("args_text") or "").strip()
                if not args_text:
                    continue
                try:
                    parsed_args = json.loads(args_text)
                except json.JSONDecodeError:
                    continue
                chunk_calls.append({
                    "id": chunk_buf.get("id", ""),
                    "name": chunk_buf.get("name"),
                    "args": parsed_args,
                })
            source_calls = chunk_calls if chunk_calls else tool_calls_captured
            for tc in source_calls:
                name = tc.get("name")
                args = tc.get("args")
                if not name or args is None:
                    continue
                if isinstance(args, dict) and not args.get("smiles") and name == "show_smiles_in_viewer":
                    continue
                normalized_calls.append({
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": args if isinstance(args, str) else json.dumps(args),
                    },
                })
            stream_tool_results = process_tool_calls(normalized_calls) if normalized_calls else []
            if stream_tool_results:
                existing = result.get("toolResults") or []
                merged = []
                seen_names = set()
                for tr in stream_tool_results:
                    tname = tr.get("name")
                    if tname:
                        seen_names.add(tname)
                    merged.append(tr)
                for tr in existing:
                    tname = tr.get("name")
                    if tname and tname in seen_names:
                        continue
                    merged.append(tr)
                result["toolResults"] = merged
        except Exception as e:
            print(f"[supervisor] failed to enrich stream tool results: {e}")
    result["agentId"] = agent_id
    result["toolsInvoked"] = tools_invoked
    print(f"[supervisor] complete: agent={agent_id}, tools={tools_invoked}, type={result.get('type')}")
    yield {"type": "complete", "data": result}


def _supervisor_content_from_event(event: Any) -> Optional[str]:
    """Extract text from a LangGraph stream event (AI messages only)."""
    if isinstance(event, (list, tuple)) and len(event) >= 1:
        chunk = event[0]
        chunk_type = getattr(chunk, "type", None) or ""
        if chunk_type not in ("ai", "AIMessageChunk"):
            return None
        if hasattr(chunk, "content"):
            c = chunk.content
            return c if isinstance(c, str) and c else None
        return None
    if hasattr(event, "content"):
        event_type = getattr(event, "type", None) or ""
        if event_type not in ("ai", "AIMessageChunk"):
            return None
        c = event.content
        return c if isinstance(c, str) and c else None
    if isinstance(event, dict):
        if event.get("type") not in ("ai", "AIMessageChunk", None):
            return None
        return event.get("content") or (event.get("chunk") or {}).get("content")
    return None


def _supervisor_tool_from_event(event: Any) -> Optional[str]:
    """Extract tool name from a stream event (ToolMessage/ToolMessageChunk)."""
    chunk = event
    if isinstance(event, (list, tuple)) and len(event) >= 1:
        chunk = event[0]
    chunk_type = getattr(chunk, "type", None) or ""
    if chunk_type in ("tool", "ToolMessage", "ToolMessageChunk"):
        return getattr(chunk, "name", None)
    # AIMessageChunk with tool_calls
    if chunk_type in ("ai", "AIMessageChunk"):
        tool_calls = getattr(chunk, "tool_calls", None)
        if tool_calls and len(tool_calls) > 0:
            return tool_calls[0].get("name")
    return None


def _supervisor_tool_call_from_event(event: Any) -> Optional[Dict[str, Any]]:
    """Extract tool call (name+args) from a stream event when available."""
    chunk = event
    if isinstance(event, (list, tuple)) and len(event) >= 1:
        chunk = event[0]
    chunk_type = getattr(chunk, "type", None) or ""
    if chunk_type in ("ai", "AIMessageChunk"):
        tool_calls = getattr(chunk, "tool_calls", None)
        if tool_calls and len(tool_calls) > 0 and isinstance(tool_calls[0], dict):
            tc = tool_calls[0]
            return {
                "id": tc.get("id", ""),
                "name": tc.get("name"),
                "args": tc.get("args"),
            }
    return None


def _supervisor_tool_call_chunks_from_event(event: Any) -> List[Dict[str, Any]]:
    """Extract raw tool_call_chunks from stream events for incremental args reconstruction."""
    chunk = event
    if isinstance(event, (list, tuple)) and len(event) >= 1:
        chunk = event[0]
    chunk_type = getattr(chunk, "type", None) or ""
    if chunk_type in ("ai", "AIMessageChunk"):
        tool_call_chunks = getattr(chunk, "tool_call_chunks", None) or []
        return [tc for tc in tool_call_chunks if isinstance(tc, dict)]
    return []


async def _build_supervisor_sub_agent(
    agent_id: str,
    model: str,
    api_key: Optional[str],
    *,
    user_query: str = "",
    temperature: float = 0.5,
    max_tokens: int = 1000,
) -> Any:
    """Build and return the compiled sub-agent graph for the given agent_id."""
    if agent_id == "code_builder":
        from .sub_agents.code_builder import build_code_builder_agent
        return await build_code_builder_agent(
            model, api_key, user_query=user_query,
            temperature=temperature, max_tokens=max_tokens,
        )
    elif agent_id == "pipeline":
        from .sub_agents.pipeline import build_pipeline_agent
        return build_pipeline_agent(model, api_key, temperature=temperature, max_tokens=max_tokens)
    else:
        # Default: bio_chat
        from .sub_agents.bio_chat import build_bio_chat_agent
        return build_bio_chat_agent(model, api_key, temperature=temperature, max_tokens=max_tokens)
