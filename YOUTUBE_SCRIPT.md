# YOUTUBE SCRIPT — PolicyPal: Multi-Tenant RAG Chatbot with Conversation Memory

**Video title:** Build an AI HR Chatbot That Remembers Your Conversations (Multi-Tenant RAG + PostgreSQL Memory)  
**Target length:** ~20 minutes  
**Thumbnail concept:** Chat interface showing "What is our remote work policy?" with a clean answer, badge showing "HR Workspace"

---

## [INTRO — 0:00–1:30]

*[Screen: PolicyPal running — user uploads a PDF, asks "What is our vacation policy?", gets a streamed answer with source badges]*

"Imagine you upload your company's HR handbook, remote work policy, and expense reimbursement guide — and then you have an AI assistant that can answer any question about them, in plain English, and remember what you asked before.

That's PolicyPal. And it solves a real problem.

Most employees don't read policy documents. They're long, formatted weirdly, and hard to search. But if they could just ask 'How many sick days do I get?' or 'What's the process for reimbursing a home office expense?' and get a direct answer from the actual policy — that's genuinely useful.

In this video, we build the full thing:
- A FastAPI backend that accepts PDF uploads and indexes them into Qdrant Cloud
- Multi-tenant namespacing so different departments get isolated data
- Conversation memory in Neon PostgreSQL — the bot remembers what you asked
- A React chat interface with streaming answers

Let's go."

---

## [ARCHITECTURE OVERVIEW — 1:30–3:30]

*[Screen: README Mermaid diagram]*

"Two flows:

**Upload flow:** User drags in a PDF → FastAPI reads it with PyPDF → chunks it → embeds with BGE-small-en-v1.5 (free, local) → upserts to Qdrant Cloud in a namespaced collection.

The collection name follows the pattern `policypal_{tenant}`. So the HR department gets `policypal_hr`, engineering gets `policypal_engineering`. Complete isolation.

**Chat flow:** User asks a question → embed the query → vector search in the correct tenant collection → pull last 8 messages from Neon PostgreSQL → send all of that to Groq Llama 3.3-70b → stream the answer via SSE → write the completed turn back to PostgreSQL.

The key architectural insight: the API server is completely stateless. All state — documents, conversation history — lives in Qdrant and Neon. This means you can run multiple API replicas without issues."

---

## [SETUP WITH UV — 3:30–4:00]

*[Screen: Terminal]*

"UV for Python dependencies:

```bash
cd policypal-rag/backend
uv sync
```

UV reads `pyproject.toml`, creates a venv, installs everything. Faster than pip, lockfile included."

---

## [DATABASE LAYER — NEON POSTGRESQL — 4:00–6:00]

*[Screen: core/database.py]*

"This is what makes PolicyPal different from a basic RAG demo: **persistent conversation memory**.

We're using Neon — serverless PostgreSQL, free tier, no credit card. The connection string looks like a normal Postgres URL.

The `conversations` table is simple:

```sql
CREATE TABLE conversations (
    id          UUID PRIMARY KEY,
    session_id  TEXT,     -- browser localStorage ID
    tenant      TEXT,     -- which workspace
    role        TEXT,     -- 'user' or 'assistant'
    content     TEXT,
    created_at  TIMESTAMPTZ
);
```

We have three operations:
- `append_message()` — writes one turn
- `get_history()` — fetches the last N messages in chronological order
- `clear_history()` — deletes all messages for a session

The `init_db()` function runs on startup and creates the table if it doesn't exist. Idempotent — safe to call multiple times.

Why PostgreSQL instead of just keeping history in memory? Because:
1. The backend on Render free tier sleeps after 15 minutes — in-memory state would be lost
2. Users on different devices or after browser reload get their history back
3. You could build analytics, export, audit trails — all the things enterprises care about"

---

## [MULTI-TENANT INDEXING — 6:00–8:30]

*[Screen: services/indexer.py]*

"The indexer accepts file bytes, a filename, and a tenant name.

First, it sanitises the tenant name:
```python
safe = ''.join(c if c.isalnum() or c == '_' else '_' for c in tenant.lower())
collection = f'policypal_{safe}'
```

This prevents injection attacks and ensures valid Qdrant collection names.

Then it creates the collection if it doesn't exist — `ensure_collection()` checks the list of existing collections and only creates if missing.

PDF loading with PyPDF is one line:
```python
loader = PyPDFLoader(tmp_path)
docs = loader.load()  # returns one Document per page
```

We chunk with `RecursiveCharacterTextSplitter(chunk_size=700, overlap=100)`. 700 tokens is about one full policy paragraph — enough context, not too much noise.

After chunking, batch embed with BGE-small, then upsert to Qdrant.

**Important:** We write the file to a temp file, load it, then delete the temp file. Never leave temp files around on a server."

---

## [RETRIEVAL — 8:30–9:30]

*[Screen: services/retrieval.py]*

"Retrieval is simple because we already solved multi-tenancy at the collection level.

```python
def retrieve(query, tenant, top_k=5):
    cname = collection_name(tenant)
    # Check collection exists (tenant may not have uploaded anything)
    if cname not in existing:
        return []
    query_vector = embed_query(query)
    hits = client.search(collection_name=cname, ...)
```

One thing worth noting: we check if the collection exists before searching. If a user hasn't uploaded anything for their tenant, we return an empty list and the endpoint returns a helpful message rather than throwing a 500."

---

## [LLM SERVICE WITH CONVERSATION MEMORY — 9:30–11:30]

*[Screen: services/llm.py]*

"The LLM service is where conversation memory plugs in.

```python
def stream_answer(question, context_chunks, history):
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    for msg in history[-8:]:     # last 4 exchanges
        messages.append({'role': msg['role'], 'content': msg['content']})
    messages.append({'role': 'user', 'content': f'Context:\n\n{context_text}\n\nQuestion: {question}'})
```

We prepend the system prompt, then the last 8 messages from history, then the current question with its context.

Why limit to 8 messages? Groq's Llama 3.3-70b has a 128k token context window, so technically we could send more. But in practice:
- Long histories increase latency
- Most follow-up questions only need the last 2-3 exchanges
- The retrieved context already provides the key information

The system prompt is crucial:
```
Answer ONLY from the policy context provided. Do not invent policies.
Never provide legal advice.
If not covered, say so and suggest contacting HR.
```

This is what prevents the model from confidently making up policy details."

---

## [API ROUTES — 11:30–13:00]

*[Screen: api/routes.py]*

"Four endpoints:

`POST /api/upload` — accepts multipart form with `tenant` field and `files`. Validates file type (PDF/TXT/MD) and size (max 10MB). Returns chunk count.

`POST /api/ask` — the main SSE endpoint. Runs retrieval, loads history, streams the answer.

`GET /api/history/{session_id}` — returns conversation history for a session.

`DELETE /api/history/{session_id}` — clears history (the 'New Chat' button).

The SSE stream pattern for the ask endpoint:
```python
async def event_stream():
    full_answer = ''
    yield 'data: ' + json.dumps({'type': 'sources', ...}) + '\n\n'
    for token in stream_answer(question, chunks, history):
        full_answer += token
        yield 'data: ' + json.dumps({'type': 'token', 'token': token}) + '\n\n'
    yield 'data: [DONE]\n\n'
    # Only write to DB after stream completes
    append_message(session_id, tenant, 'user', question)
    append_message(session_id, tenant, 'assistant', full_answer)
```

Notice we accumulate the full answer and write to DB only after the stream finishes. This ensures we store the complete response, not a partial one."

---

## [REACT FRONTEND — 13:00–16:00]

*[Screen: App.jsx]*

"The frontend has a sidebar + chat layout — classic enterprise chat UI.

Key state management decisions:

1. **Session ID** — generated with uuid4, stored in localStorage. Persists across page reloads. This is how we restore conversation history.

2. **Tenant** — editable input in the navbar. Changing the tenant clears the local message state (not the DB history).

3. **Streaming messages** — each message has a `streaming: true` flag while tokens are arriving. We show a blinking cursor for the active message.

*[Screen: components/ChatMessage.jsx]*

The ChatMessage component uses DaisyUI's `chat-start` / `chat-end` classes for the WhatsApp-style bubbles. User messages go right (chat-end), assistant messages go left (chat-start).

Source badges appear below assistant messages. They show the filename, page number, and similarity score.

*[Screen: components/UploadPanel.jsx]*

The upload panel is in the sidebar. It uses a regular HTML file input with `multiple` and `accept='.pdf,.txt,.md'`. FormData handles the multipart upload.

*[Screen: lib/api.js]*

The `askQuestion()` function streams SSE using `fetch` + `ReadableStream` — same pattern as StackBot. Source events come first, then tokens."

---

## [DEMO — 16:00–18:00]

*[Screen: running app]*

"Let me demo this:

First, I'll upload a sample remote work policy PDF. Watch the sidebar — it says 'Indexing...' then confirms the chunk count.

Now I ask: 'What are the requirements to work remotely?'

See the source badge appear first — it shows the filename and page. Then the answer streams in, citing 'According to the Remote Work Policy...'

Now I ask a follow-up: 'What about the equipment allowance?' — PolicyPal remembers we were discussing remote work and answers in context.

Now let me switch the workspace to 'engineering' — type that in the navbar input. The chat clears. If I ask the same question, I get 'No policy documents found' because we haven't uploaded anything to the engineering workspace yet. Isolation works."

---

## [DEPLOYMENT — 18:00–19:30]

*[Screen: Render + Vercel + Neon dashboards]*

"Backend → Render, frontend → Vercel, database → Neon.

Neon setup:
1. Create free project at neon.tech
2. Copy the connection string → looks like `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`
3. Add to Render environment variables as `DATABASE_URL`

The `init_db()` function creates the table on first startup. No migrations needed for this simple schema.

One gotcha: Neon's free tier also has a sleep mode for inactive connections. The psycopg2 connection might time out. The `get_conn()` function checks `conn.closed` and reconnects if needed."

---

## [OUTRO — 19:30–20:00]

"PolicyPal demonstrates three things that enterprise clients actually care about:

1. **Multi-tenancy** — data isolation by design, not by accident
2. **Conversation memory** — context that persists beyond a single session
3. **Grounded answers** — the system prompt explicitly forbids hallucinated policies

These are the patterns you'd find in production HR chatbots, customer support bots, and internal knowledge bases.

Subscribe for the next video: ResearchCraft — an autonomous research agent that uses LangGraph to plan, search the web, and write structured reports. That's where we get into agentic AI. See you there."

---

## Technical Summary Card

```
Stack:
• BGE-small-en-v1.5 — local embeddings (free)
• Qdrant Cloud — multi-tenant vector storage (free)
• Neon PostgreSQL — conversation history (free)
• Groq Llama-3.3-70b — LLM (free)
• FastAPI — backend
• React + DaisyUI — frontend
• UV — Python package manager

Source code: github.com/your-username/policypal-rag
```
