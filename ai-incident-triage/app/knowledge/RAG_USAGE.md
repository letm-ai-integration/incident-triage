# Using the Shared RAG Knowledge Base

This project has one shared vector store with separate **collections** per
knowledge domain (e.g. `runbooks`, and later `logs`, `k8s`). You don't need
a new vector store for your agent — you need a new `.md` file and a new
collection name.

The stack mirrors the reference RAG POC (`ayush-ai-poc/rag-qna-bot-poc`):
a local **FAISS** index per collection plus local
`sentence-transformers/all-MiniLM-L6-v2` embeddings. Everything is embedded
and persisted on disk under `settings.vector_store_path` (default
`vectorstore/`) — no external service, no API key for embeddings, and it is
independent of whichever LLM provider is active for chat (`openrouter` or
`groq`).

## Adding your own knowledge source

1. Create a markdown file under `knowledge_base/<your_domain>/<name>.md`.
2. Structure it with one `## Section Title` per discrete entry (alert,
   log pattern, k8s issue, etc.) — everything under a `##` heading is
   ingested as a single chunk, so keep each entry self-contained and put
   your most distinctive/searchable terms in the heading and the first
   couple of lines.
3. Pick a collection name for your domain (e.g. `logs`, `k8s`). Collection
   names are just strings — no registration step required.

## Ingesting (you control when)

Ingestion is **manual** — nothing runs automatically when you edit the
file. After you're happy with your `.md` file (or updated it):

```bash
python scripts/ingest_knowledge.py --file knowledge_base/<your_domain>/<name>.md --collection <your_collection>
```

Run this again any time you update the source file — it upserts, so
re-running is safe.

## Querying from your agent

```python
from app.knowledge.retriever import retrieve, RetrievedChunk

results: list[RetrievedChunk] = retrieve(collection="<your_collection>", query_text=alert_description, k=3)
for r in results:
    print(r.score, r.metadata["title"], r.text[:200])
```

`RetrievedChunk.score` is cosine similarity (higher = more relevant). Tune
any relevance threshold (e.g. `MIN_RELEVANCE_SCORE` in the runbook agent)
against real scores before relying on it.

If your collection hasn't been ingested yet, `retrieve()` raises
`VectorStoreCollectionMissing` — handle this distinctly from "no relevant
results found," since it means you (or someone) needs to run the
ingestion script first, not that the search legitimately came up empty.

## Current collections

| Collection | Source file | Used by |
|---|---|---|
| `runbooks` | `knowledge_base/runbooks/runbook.md` | `agents/investigation/runbook` |
| `logs` | *(not yet created)* | *(future logs agent)* |
| `k8s` | `knowledge_base/kubernetes/pod-crash.md` | `agents/investigation/kubernetes` |

Update this table when you add a new collection.
