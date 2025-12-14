import os
import json
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .utils import log_line, get_text_from_completion, strip_code_fences, trim_history
    from .safety import violates_whitelist, ensure_clear_on_change
    from .uniprot import search_uniprot
except ImportError:
    from utils import log_line, get_text_from_completion, strip_code_fences, trim_history
    from safety import violates_whitelist, ensure_clear_on_change
    from uniprot import search_uniprot


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
    
    # Try to load from models_config.json
    config_path = Path(__file__).parent / "models_config.json"
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
    """Get OpenRouter API key. Supports OPENROUTER_API_KEY or ANTHROPIC_API_KEY env vars."""
    global _openrouter_api_key
    
    # If a specific key is provided (e.g. from client request), use it
    if api_key:
        return api_key

    # Return cached key if available
    if _openrouter_api_key:
        return _openrouter_api_key

    # Check for OpenRouter key first in env
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        _openrouter_api_key = openrouter_key
        return _openrouter_api_key

    # Fallback to ANTHROPIC_API_KEY (may be OpenRouter key)
    env_api_key = os.getenv("ANTHROPIC_API_KEY")
    if env_api_key:
        _openrouter_api_key = env_api_key
        return _openrouter_api_key
    
    return None


def _call_openrouter_api(
    model: str,
    messages: List[Dict[str, Any]],
    max_tokens: int,
    temperature: float,
    api_key: Optional[str] = None,
) -> Any:
    """Make a direct API call to OpenRouter using requests.
    
    Returns a response object compatible with get_text_from_completion().
    """
    key = _get_openrouter_api_key(api_key)
    if not key:
        raise RuntimeError("OpenRouter API key is missing. Please set OPENROUTER_API_KEY or ANTHROPIC_API_KEY in your .env file.")
    
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
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        # Parse response and create a compatible object
        data = response.json()
        
        # Create a simple object that mimics OpenAI/OpenRouter response format
        class CompletionResponse:
            def __init__(self, data):
                self.choices = [Choice(data.get("choices", [{}])[0] if data.get("choices") else {})]
        
        class Choice:
            def __init__(self, choice_data):
                self.message = Message(choice_data.get("message", {}))
        
        class Message:
            def __init__(self, message_data):
                self.content = message_data.get("content", "")
        
        return CompletionResponse(data)
    except requests.exceptions.HTTPError as e:
        # Extract the actual error message from OpenRouter's response
        error_detail = str(e)
        status_code = None
        
        if hasattr(e, 'response') and e.response is not None:
            status_code = e.response.status_code
            try:
                error_data = e.response.json()
                if isinstance(error_data, dict):
                    # OpenRouter error format: {"error": {"message": "...", "type": "...", ...}}
                    if 'error' in error_data:
                        error_obj = error_data['error']
                        if isinstance(error_obj, dict) and 'message' in error_obj:
                            error_detail = error_obj['message']
                        elif isinstance(error_obj, str):
                            error_detail = error_obj
                    # Sometimes the error is at the top level
                    elif 'message' in error_data:
                        error_detail = error_data['message']
            except (ValueError, KeyError, AttributeError):
                # If JSON parsing fails, try to get text response
                try:
                    error_text = e.response.text
                    if error_text:
                        error_detail = f"{error_detail} (Response: {error_text[:200]})"
                except:
                    pass
        
        log_line("runner:openrouter:error", {
            "error": error_detail,
            "status": status_code,
            "model": model
        })
        raise RuntimeError(f"OpenRouter API call failed: {error_detail}")
    except requests.exceptions.RequestException as e:
        log_line("runner:openrouter:error", {
            "error": str(e),
            "status": getattr(e, 'response', {}).status_code if hasattr(e, 'response') and e.response is not None else None,
            "model": model
        })
        raise RuntimeError(f"OpenRouter API call failed: {str(e)}")


def _map_model_id(model_id: str) -> str:
    """Map legacy model ID to OpenRouter model ID using models_config.json"""
    model_map = _load_model_map()
    return model_map.get(model_id, model_id)


async def run_agent(
    *,
    agent: Dict[str, Any],
    user_text: str,
    current_code: Optional[str],
    history: Optional[List[Dict[str, Any]]],
    selection: Optional[Dict[str, Any]],
    selections: Optional[List[Dict[str, Any]]] = None,
    model_override: Optional[str] = None,
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
            from .alphafold_handler import alphafold_handler
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
        context_prefix = (
            f"You may MODIFY the existing Molstar builder code below to satisfy the new request. Prefer editing in-place if it does not change the loaded PDB. Always return the full updated code.\n\n"
            f"Existing code:\n\n```js\n{str(current_code)}\n```\n\nRequest: {user_text}"
            if current_code and str(current_code).strip()
            else f"Generate Molstar builder code for: {user_text}"
        )

        prior_dialogue = (
            "\n\nRecent context: "
            + " | ".join(f"{m.get('type')}: {m.get('content')}" for m in (history or [])[-4:])
            if history
            else ""
        )

        # Enhanced system prompt with RAG for MVS agent
        system_prompt = agent.get("system")
        if agent.get("id") == "mvs-builder":
            print(f"🧠 [RAG] MVS agent triggered, enhancing prompt with Pinecone examples...")
            try:
                from .mvs_rag import enhance_mvs_prompt_with_rag
                system_prompt = await enhance_mvs_prompt_with_rag(user_text, system_prompt)
                print(f"✅ [RAG] Successfully enhanced MVS prompt")
                log_line("agent:mvs:rag", {"enhanced": True, "userText": user_text})
            except Exception as e:
                print(f"❌ [RAG] Failed to enhance prompt: {e}")
                log_line("agent:mvs:rag_error", {"error": str(e)})
                # Fallback to base prompt if RAG fails
        
        # Map model ID to OpenRouter format
        openrouter_model = _map_model_id(model)
        
        # Prepare messages with system prompt
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": context_prefix + prior_dialogue})
        
        log_line("agent:code:req", {**base_log, "hasCurrentCode": bool(current_code and str(current_code).strip()), "userText": user_text})
        completion = _call_openrouter_api(
            model=openrouter_model,
            messages=messages,
            max_tokens=800,
            temperature=0.2,
        )
        content_text = get_text_from_completion(completion)
        code = strip_code_fences(content_text)

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
                max_tokens=800,
                temperature=0.2,
            )
            code = strip_code_fences(get_text_from_completion(completion2))

        code = ensure_clear_on_change(current_code, code)
        log_line("agent:code:res", {"length": len(code)})
        return {"type": "code", "code": code}

    # Text agent
    selection_lines = []
    
    # Extract PDB ID from current code if available
    code_pdb_id = None
    if current_code and str(current_code).strip():
        import re
        # Look for loadStructure calls with PDB ID
        pdb_match = re.search(r"loadStructure\s*\(\s*['\"]([0-9A-Za-z]{4})['\"]", str(current_code))
        if pdb_match:
            code_pdb_id = pdb_match.group(1).upper()
    
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

    messages: List[Dict[str, Any]] = []
    if selection_context or code_context:
        messages.append({"role": "user", "content": (selection_context + ("\n\n" if selection_context and code_context else "") + code_context)})
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
        
    completion = _call_openrouter_api(
        model=openrouter_model,
        messages=openrouter_messages,
        max_tokens=1000,
        temperature=0.5,
    )
    text = get_text_from_completion(completion)
    log_line("agent:text:res", {"length": len(text), "preview": text[:400]})
    return {"type": "text", "text": text}

