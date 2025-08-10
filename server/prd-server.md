Goal
	•	Keep the same HTTP API so the frontend doesn’t change.
	•	Move to FastAPI + LangGraph (Python).
	•	Add: semantic router, builder whitelist, auto-clear on PDB change, typo/intent repair, better logs, and rate limiting.

Stack
	•	Framework: FastAPI
	•	Router: LangGraph (Python)
	•	LLMs: anthropic (for agents), openai (for embeddings + optional LLM fallback)
	•	CORS & rate limit: fastapi[all], slowapi
	•	Env: python-dotenv
	•	Run: uvicorn

Folder layout

server/
  app.py                  # FastAPI entry
  router_graph.py         # LangGraph router (rule → semantic → LLM)
  agents.py               # agent registry (code-builder, bio-chat, others)
  runner.py               # run_agent() logic (Anthropic calls)
  safety.py               # whitelist checks, PDB change guard
  utils.py                # logging, history utils, spell-fix
  requirements.txt

Endpoint parity (match your current API)
	•	GET  /api/agents → list agents
	•	POST /api/agents/invoke → run selected agent
	•	POST /api/agents/route → route then run
	•	POST /api/generate → code gen (compat)
	•	POST /api/chat → general chat (compat)
	•	GET  /api/health → health

Migration map (Node → Python)

Area	Node now	Python target
Web framework	Express	FastAPI
Router	pickAgentForPrompt()	router_graph.py (rule + semantic + LLM)
Agents registry	agents{...}	agents.py (same fields: id, name, description, kind, system, modelEnv, defaultModel)
LLM calls	Anthropic JS SDK	anthropic Python SDK
Embeddings	—	langchain_openai.OpenAIEmbeddings
Logs	logLine	structured logger + truncation in utils.py
CORS	cors()	fastapi.middleware.cors
Rate limit	—	slowapi
Env	dotenv	python-dotenv

Additional features to add
	1.	Semantic router (LangGraph):
	•	Rule: if selection + question → bio-chat.
	•	Semantic: embeddings vs. agent descriptions.
	•	LLM fallback: pick when scores are low/close.
	2.	Code safety:
	•	Whitelist builder methods.
	•	Reject unknown calls; auto-regenerate if violated.
	3.	Auto-clear on PDB change:
	•	If new code loads different PDB than currentCode, inject await builder.clearStructure().
	4.	Typo/intent repair:
	•	Normalize common intents: strucutre→structure, etc.
	•	If vague “generate 3d structure”, prefer last entity from history.
	5.	Response joiner:
	•	Join all text blocks from Anthropic.
	6.	Better logs:
	•	Log route stage (rule|semantic|llm), top-3 scores, chosen agent, truncated payloads.
	7.	Hard limits:
	•	Trim history to last N turns, cap char length.
	•	Increase code max_tokens a bit.
	8.	Configurable CORS + models via env.

Step-by-step

Step 1: Bootstrap FastAPI
	•	Create app.py with CORS, rate limit, health route.
	•	Load env (ANTHROPIC_API_KEY, OPENAI_API_KEY, APP_ORIGIN, model names).

Step 2: Port agent registry
	•	Copy your agents object to agents.py.
	•	Keep same fields so execution code is simple.
	•	Expose list_agents().

Step 3: Implement runner
	•	run_agent(agent, user_text, current_code, history, selection)
	•	If agent.kind == "code":
	•	Build prompt (include Existing code: block).
	•	Call Anthropic with code system prompt.
	•	Join text parts.
	•	Strip fences.
	•	Safety pass: whitelist + auto-clear PDB change. If violated, re-ask once.
	•	Else (bio-chat):
	•	Build context (SelectionContext + CodeContext).
	•	Call Anthropic with bio system prompt.
	•	Join text parts.

Step 4: LangGraph router
	•	router_graph.py with 3 nodes:
	•	rule_node → selection+question check.
	•	semantic_node → embedding similarity to agent descriptions; thresholds (THRESH=0.32, MARGIN=0.05).
	•	llm_fallback_node → small prompt, return agent id only.
	•	init_router(agents) builds the agent index on startup.

Step 5: Safety helpers
	•	safety.py:
	•	ALLOWED_CALLS = {...}
	•	violates_whitelist(code) -> bool
	•	infer_loaded_pdb(code) -> "1CBS"|None
	•	ensure_clear_on_change(currentCode, newCode) -> newCode

Step 6: Utils
	•	utils.py:
	•	log_line(section, obj) with truncation (8k char cap).
	•	get_text(completion) to join all message parts.
	•	spell_fix(input) small replacements.
	•	infer_last_entity(history) heuristic.

Step 7: Endpoints
	•	/api/agents → return list_agents().
	•	/api/agents/invoke:
	•	Validate agentId + input.
	•	Call run_agent.
	•	/api/agents/route:
	•	Build router state {input, selection, currentCode, history} (apply spell_fix).
	•	routed = await routerGraph.ainvoke(state).
	•	agentId = routed["routedAgentId"].
	•	Run agent and return { agentId, ...result, reason: routed["reason"] }.
	•	/api/generate and /api/chat:
	•	Keep for backward compatibility; reuse run_agent paths (code/text).

Step 8: Testing
	•	Unit:
	•	Router: prompts → agent choices; check thresholds.
	•	Safety: blocks unknown methods, inserts clear on PDB change.
	•	Runner: strips fences, joins parts.
	•	Integration:
	•	Curl the 5 main routes with your example payloads.
	•	Frontend smoke test:
	•	Load your app; try “generate 3d structure” after “search smiles for zearalenone”.

Step 9: Deployment
	•	uvicorn server.app:app --host 0.0.0.0 --port 8787
	•	Reverse proxy same as Node.
	•	Blue/green: run Python on a new port, switch proxy when healthy.

Minimal code stubs (just the signatures)

# app.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from router_graph import init_router, routerGraph
from agents import agents, list_agents
from runner import run_agent
from utils import log_line, spell_fix

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=(os.getenv("APP_ORIGIN","*").split(",")),
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_router(list(agents.values()))

@app.get("/api/health")
def health(): return {"ok": True}

@app.get("/api/agents")
def get_agents(): return {"agents": list_agents()}

@app.post("/api/agents/invoke")
@limiter.limit("30/minute")
async def invoke(req: Request):
    body = await req.json()
    agent_id = body.get("agentId")
    input_text = body.get("input")
    if not agent_id or agent_id not in agents or not isinstance(input_text, str):
        return {"error":"invalid_input"}
    res = await run_agent(
        agent=agents[agent_id],
        user_text=input_text,
        current_code=body.get("currentCode"),
        history=body.get("history"),
        selection=body.get("selection"),
    )
    return {"agentId": agent_id, **res}

@app.post("/api/agents/route")
@limiter.limit("60/minute")
async def route(req: Request):
    body = await req.json()
    input_text = body.get("input")
    if not isinstance(input_text, str): return {"error":"invalid_input"}
    input_text = spell_fix(input_text)

    routed = await routerGraph.ainvoke({
        "input": input_text,
        "selection": body.get("selection"),
        "currentCode": body.get("currentCode"),
        "history": body.get("history"),
    })
    agent_id = routed.get("routedAgentId")
    if not agent_id: return {"error":"router_no_decision", "reason": routed.get("reason")}
    log_line("router", {"agentId": agent_id, "reason": routed.get("reason")})
    res = await run_agent(
        agent=agents[agent_id],
        user_text=input_text,
        current_code=body.get("currentCode"),
        history=body.get("history"),
        selection=body.get("selection"),
    )
    return {"agentId": agent_id, **res, "reason": routed.get("reason")}

Rollout checklist
	•	Stand up FastAPI on a new port.
	•	Point staging frontend to it.
	•	Verify parity on all endpoints.
	•	Load test rate limits.
	•	Switch prod traffic.
	•	Monitor router reason logs and adjust THRESH/MARGIN.

If you want, I can fill in the Python files with working code next.