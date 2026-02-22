Plan: Refactor to LangChain Supervisor Agent Architecture

Context
The current system has a single ReAct agent (run_react_agent_stream in server/agents/runner.py) that binds all tools and uses one system prompt. There's also a legacy main_graph.py router-dispatcher that's mostly dead code (router always returns bio-chat). The 12 agents in registry.py are only used for manual selection and system prompts — they don't have separate LangGraph graphs.

Problem: No clean separation of concerns. One agent handles everything — protein Q&A, code generation, pipeline design, and tool invocation all share the same context and prompt. This makes it hard to optimize prompts, add agent-specific tools, or scale.

Goal: Refactor into a LangGraph supervisor pattern with 3 specialized sub-agents, each with their own tools, while keeping the existing SSE streaming, dialog-based tool execution, and frontend patterns working.


Architecture
┌─────────────────────────────────────────────────┐
│                  Supervisor                      │
│  (LLM routes to sub-agent, or manual override)  │
└──────┬──────────────┬──────────────┬─────────────┘
       │              │              │
  ┌────▼────┐   ┌─────▼─────┐  ┌────▼─────┐
  │ BioChat │   │CodeBuilder│  │ Pipeline │
  │  Agent  │   │   Agent   │  │  Agent   │
  └────┬────┘   └─────┬─────┘  └──────────┘
       │              │
  Tools:          Tools:
  - AlphaFold     - SMILES
  - OpenFold      - MVS Builder
  - RFdiffusion     (RAG-enhanced)
  - ProteinMPNN
  - DiffDock
  - Validation
  - UniProt
  - MVS Builder


  Agent Responsibilities
AgentPurposeToolsBioChatProtein Q&A, info retrieval, triggers computational toolsAlphaFold, OpenFold, RFdiffusion, ProteinMPNN, DiffDock, Validation, UniProt, MVS BuilderCode BuilderMolStar/MolViewSpec visualization code generationSMILES, MVS Builder (RAG-enhanced prompt)PipelineWorkflow composition, blueprint JSON generationNone (generates JSON in text response)
Key Decisions

Supervisor auto-routes via LLM, user can manually override via AgentSelector
Dialog pattern kept: Tools return action JSON → frontend opens dialog → user confirms
MVS Builder shared: Available to both BioChat and Code Builder
Streaming: Route first, then stream sub-agent directly (avoids nested graph streaming issues)
Frontend pills: Agent pill shows active agent, tool pills show invoked tools per message


Implementation Phases
Phase 1: Tool Layer (non-breaking, additive)
Split server/agents/tools/actions.py into individual tool files. Keep old actions.py working until Phase 4.
Create files:
FileToolNotesserver/agents/tools/alphafold.pyopen_alphafold_dialogExtract from actions.pyserver/agents/tools/openfold.pyopen_openfold2_dialogExtract from actions.pyserver/agents/tools/rfdiffusion.pyopen_rfdiffusion_dialogExtract from actions.pyserver/agents/tools/proteinmpnn.pyopen_proteinmpnn_dialogNew — currently no dialog tool exists for ProteinMPNNserver/agents/tools/diffdock.pyopen_diffdock_dialogExtract from actions.pyserver/agents/tools/validation.pyvalidate_structureNew — triggers validation actionserver/agents/tools/uniprot.pysearch_uniprotMove from actions.py:get_uniprot_tool()server/agents/tools/mvs_builder.pymvs_builderNew — RAG-enhanced MVS code assistance
Each tool follows the existing pattern from actions.py:
python# Example: server/agents/tools/alphafold.py
from langchain_core.tools import tool
import json

def get_alphafold_tool():
    @tool
    def open_alphafold_dialog() -> str:
        """Open the AlphaFold structure prediction dialog..."""
        return json.dumps({"action": "open_alphafold_dialog"})
    return open_alphafold_dialog
Modify server/agents/tools/__init__.py — add get_tools_for_agent(agent_id):
pythonAGENT_TOOL_MAP = {
    "bio_chat": [get_alphafold_tool, get_openfold_tool, get_rfdiffusion_tool,
                 get_proteinmpnn_tool, get_diffdock_tool, get_validation_tool,
                 get_uniprot_tool, get_mvs_builder_tool],
    "code_builder": [get_smiles_tool, get_mvs_builder_tool],
    "pipeline": [],
}

def get_tools_for_agent(agent_id: str) -> list:
    return [f() for f in AGENT_TOOL_MAP.get(agent_id, [])]
Keep get_all_react_tools() working for backward compatibility.
Phase 2: Sub-Agent Builders (non-breaking, additive)
Create server/agents/sub_agents/:
FileAgentSystem Prompt SourceTools__init__.pyExports——bio_chat.pyBioChatprompts/bio_chat.py → BIO_CHAT_SYSTEM_PROMPT8 toolscode_builder.pyCode BuilderMerge prompts/code_builder.py + prompts/mvs_builder.py + RAG examples2 toolspipeline.pyPipelineprompts/pipeline.py → PIPELINE_AGENT_SYSTEM_PROMPT0 tools
Each builder reuses build_agent_graph() from server/agents/langchain_agent/graph.py:
python# server/agents/sub_agents/bio_chat.py
from ..langchain_agent.graph import build_agent_graph
from ..llm.model import get_chat_model
from ..tools import get_tools_for_agent
from ..prompts.bio_chat import BIO_CHAT_SYSTEM_PROMPT

def build_bio_chat_agent(model_id, api_key=None, temperature=0.5, max_tokens=1000):
    llm = get_chat_model(model_id, api_key, temperature=temperature, max_tokens=max_tokens)
    tools = get_tools_for_agent("bio_chat")
    return build_agent_graph(llm, tools, system_prompt=BIO_CHAT_SYSTEM_PROMPT)
Code Builder is special — needs RAG examples injected into system prompt:
python# server/agents/sub_agents/code_builder.py
async def build_code_builder_agent(model_id, api_key=None, *, user_query="", ...):
    llm = get_chat_model(model_id, api_key, ...)
    tools = get_tools_for_agent("code_builder")
    system_prompt = await _build_code_builder_prompt(user_query)  # merges prompts + RAG
    return build_agent_graph(llm, tools, system_prompt=system_prompt)
The _build_code_builder_prompt() function:

Starts with merged CODE_AGENT_SYSTEM_PROMPT + MVS_AGENT_SYSTEM_PROMPT_BASE
Calls mvs_rag.py to retrieve relevant examples for user_query
Appends RAG examples to the system prompt

Phase 3: Supervisor (new, parallel to existing)
Create server/agents/supervisor/:
FilePurpose__init__.pyExports build_supervisor_graphrouting.pyLLM-based routing functionstate.pySupervisorState TypedDict
Routing (supervisor/routing.py):

System prompt tells LLM to choose between bio_chat, code_builder, pipeline
Uses a fast/cheap LLM call (low max_tokens=50)
Returns (agent_id, reason) tuple
If manual_override is set, skip LLM call

No compiled supervisor graph needed for streaming. Instead, streaming goes:

Route (LLM or manual override)
Build sub-agent graph
Stream sub-agent via graph.astream(stream_mode="messages")

This avoids nested graph streaming complexity.
Phase 4: Runner Integration (switch-over)
Modify server/agents/runner.py:
Add new function run_supervisor_stream() alongside existing run_react_agent_stream():
pythonasync def run_supervisor_stream(
    *, user_text, current_code=None, history=None, selection=None,
    selections=None, uploaded_file_context=None, structure_metadata=None,
    pipeline_id=None, pipeline_data=None, model_override=None,
    manual_agent_id=None,  # NEW: from frontend AgentSelector
    temperature=0.5, max_tokens=1000,
) -> AsyncGenerator[Dict[str, Any], None]:
    # 1. Route
    if manual_agent_id:
        agent_id = manual_agent_id
    else:
        agent_id = await _supervisor_route(user_text, model_override)

    # 2. Yield routing event (frontend shows agent pill)
    yield {"type": "routing", "data": {"agentId": agent_id}}

    # 3. Build sub-agent
    sub_agent = await _build_sub_agent(agent_id, model_override, user_query=user_text)

    # 4. Build messages (reuse existing _build_react_messages)
    lc_messages = ...  # same as current

    # 5. Stream with tool_call detection
    tools_invoked = []
    async for event in sub_agent.astream({"messages": lc_messages}, ...):
        content = _content_from_event(event)
        if content:
            yield {"type": "content", "data": {"text": content}}
        tool_name = _tool_name_from_event(event)
        if tool_name and tool_name not in tools_invoked:
            tools_invoked.append(tool_name)
            yield {"type": "tool_call", "data": {"name": tool_name}}

    # 6. Complete with agent + tools metadata
    result = react_state_to_app_result(last_state)
    result["agentId"] = agent_id
    result["toolsInvoked"] = tools_invoked
    yield {"type": "complete", "data": result}
Helper _tool_name_from_event(event): Detects ToolMessage or ToolMessageChunk in stream events and extracts the tool name.
Modify _body_to_stream_args() in app.py:

Extract manual_agent_id from configurable.agentId or body.agentId
Pass it through to run_supervisor_stream

Modify SSE endpoint in app.py (route_stream_sse):

Replace run_react_agent_stream call with run_supervisor_stream
Handle new event types routing and tool_call:

python  if etype == "routing":
      payload = json.dumps({"agentId": event["data"]["agentId"]})
      yield f"event: metadata\ndata: {payload}\n\n"
  elif etype == "tool_call":
      payload = json.dumps({"tool": event["data"]["name"]})
      yield f"event: metadata\ndata: {payload}\n\n"

Add agentId and toolsInvoked to the values event appResult

Also update NDJSON endpoint (/api/agents/route/stream) the same way.
Phase 5: Frontend Updates
5a. Update AgentSelector.tsx

Simplify agent list to 3 + auto
Map old agent IDs: "bio-chat" → "bio_chat", "code-builder" → "code_builder"

5b. Create src/components/AgentPill.tsx
tsxconst AGENT_COLORS = {
  bio_chat: { bg: 'bg-green-100', text: 'text-green-700', label: 'BioChat' },
  code_builder: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Code Builder' },
  pipeline: { bg: 'bg-purple-100', text: 'text-purple-700', label: 'Pipeline' },
};
// Small pill/badge component
5c. Create src/components/ToolPill.tsx
tsxconst TOOL_LABELS = {
  open_alphafold_dialog: 'AlphaFold',
  open_diffdock_dialog: 'DiffDock',
  open_openfold2_dialog: 'OpenFold2',
  open_rfdiffusion_dialog: 'RFdiffusion',
  open_proteinmpnn_dialog: 'ProteinMPNN',
  search_uniprot: 'UniProt',
  show_smiles_in_viewer: 'SMILES 3D',
  validate_structure: 'Validation',
  mvs_builder: 'MVS Builder',
};
// Small amber pill/badge component
5d. Update src/utils/langgraphTransport.ts

Add toolsInvoked?: string[] to LangGraphState.appResult

5e. Update src/components/ChatPanel.tsx

Parse agentId and toolsInvoked from stream.values.appResult (already partially done at line 586-601)
Add toolsInvoked to ExtendedMessage interface
Render <AgentPill> and <ToolPill> above each AI message
Handle metadata SSE events for real-time pill updates during streaming

5f. Update src/stores/settingsStore.ts

Update selectedAgentId type/values to match new IDs

5g. Update src/stores/chatHistoryStore.ts

Add toolsInvoked?: string[] to message metadata

Phase 6: Cleanup
Delete/deprecate:

server/agents/main_graph.py — replaced by supervisor
server/agents/graph_state.py — replaced by supervisor/state.py
server/agents/graph_nodes.py — replaced by supervisor routing
server/agents/router.py — replaced by supervisor/routing.py
server/agents/example_official_pattern.py — no longer needed

Simplify:

server/agents/registry.py — reduce to 3 agents (bio_chat, code_builder, pipeline)
server/agents/tools/actions.py — delete after all tools migrated to individual files
server/agents/runner.py — remove old run_agent() and run_react_agent_stream() after cutover

Update:

CLAUDE.md — document new architecture

Phase 7: ProteinMPNN Dialog (if missing)
Check if ProteinMPNNDialog.tsx exists and handles open_proteinmpnn_dialog action. If not, add action handling in ChatPanel.tsx's handleAlphaFoldResponse() for the new action type.

Critical Files
Backend (modify)

server/agents/runner.py — add run_supervisor_stream(), keep old functions during migration
server/app.py — switch SSE endpoint to supervisor, handle new event types
server/agents/tools/__init__.py — add get_tools_for_agent() registry
server/agents/langchain_agent/graph.py — reuse as-is for sub-agent graphs
server/agents/langchain_agent/result.py — add toolsInvoked to result extraction
server/agents/registry.py — simplify to 3 agents

Backend (create)

server/agents/tools/{alphafold,openfold,rfdiffusion,proteinmpnn,diffdock,validation,uniprot,mvs_builder}.py
server/agents/sub_agents/{__init__,bio_chat,code_builder,pipeline}.py
server/agents/supervisor/{__init__,routing,state}.py

Frontend (modify)

src/components/ChatPanel.tsx — render pills, parse new appResult fields
src/components/AgentSelector.tsx — simplify to 3 agents
src/utils/langgraphTransport.ts — add toolsInvoked to interface
src/stores/settingsStore.ts — update agent ID types

Frontend (create)

src/components/AgentPill.tsx
src/components/ToolPill.tsx

Reuse (no changes needed)

server/agents/langchain_agent/graph.py — build_agent_graph() used by all 3 sub-agents
server/agents/langchain_agent/streaming.py — streaming utilities
server/agents/llm/model.py — get_chat_model()
server/agents/prompts/*.py — existing system prompts reused
server/memory/rag/mvs_rag.py — RAG retrieval for Code Builder
server/tools/nvidia/ — all NVIDIA clients unchanged
server/agents/handlers/ — all handlers unchanged (called by frontend after dialog)


Verification
Backend Testing

Tool isolation: Import each new tool file, call the function, verify it returns correct action JSON
Sub-agent build: Build each sub-agent, verify ainvoke() works with test messages
Routing: Test supervisor routing with various prompts:

"What is insulin?" → bio_chat
"Show me PDB 1HHO in cartoon" → code_builder
"Create a pipeline for protein design" → pipeline
"Fold this protein" → bio_chat (has AlphaFold tool)


Manual override: Pass manual_agent_id="code_builder", verify it bypasses routing
SSE streaming: Full end-to-end with curl or frontend, verify:

metadata events arrive with correct agentId
messages events stream token-by-token
values event includes agentId and toolsInvoked
Tool calls (e.g. AlphaFold dialog) still work



Frontend Testing

AgentSelector: Shows 3 agents + Auto, selection persists
Agent pills: Appear above AI messages with correct color/label
Tool pills: Appear when tools are invoked (try "search insulin in UniProt")
Dialog flow: "Fold insulin" → BioChat routes → AlphaFold tool called → dialog opens → job runs
Code generation: "Show PDB 1HHO" → Code Builder routes → MolStar code generated → viewer displays
Pipeline: "Create a protein design pipeline" → Pipeline routes → blueprint JSON generated

Run commands
bash# Backend
cd server && source venv/bin/activate
python -m pytest tests/ -v  # if tests exist
python app.py  # start server, test manually

# Frontend
npm run dev  # start frontend
npm run build  # verify no TypeScript errors