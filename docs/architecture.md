# Resume Tailoring RAG API – MVP Design (Local‑only)

> **Purpose**
> Give a job‑seeker an API that rewrites their one master résumé so it perfectly matches any Job Description (JD) they supply—without inventing facts and without sending private data to third‑party embedding services.

---

## 1. Product Goals

| ID | Goal                                                                      | Success Metric                                          |
| -- | ------------------------------------------------------------------------- | ------------------------------------------------------- |
| G1 | **Keep it factual** – use only text already present in the résumé chunks. | 100 % of bullets cite at least one chunk id.            |
| G2 | **Easy to demo** – run on a laptop via Podman‑compose in <2 min.          | `podman-compose up` returns 200 on `/health` first try. |
| G3 | **Zero embedding cost** – no paid API for vectors.                        | \$0 spent on embeddings per 1 000 requests.             |
| G4 | **Good rewrite quality** – bullets read naturally and mirror JD keywords. | Pilot users rate ≥4/5 on relevance & tone.              |

### Non‑Goals (MVP)

* User auth or multi‑tenancy security.
* Web UI – API only.
* Full offline generation – still uses GPT‑4o for rewriting.
* Docker support – this project is Podman-first.

---

## 2. End‑to‑End Flow

```
User → POST /resume (raw text/PDF)
      ↳ ingestion.py → chunk + MiniLM embed → store in Postgres
User → POST /tailor {resume_id, jd_text}
      ↳ retrieval.py → MiniLM embed JD → pgvector similarity → top‑k chunks
      ↳ generation.py → GPT‑4o prompt(chunks+JD) → bullets w/ [C1] cites
API → JSON {tailored_text, chunk_ids}
```

---

## 3. File/Directory Layout

*(unchanged but repeated here for convenience)*

```
resume‑rag/
├─ README.md            # quickstart & API examples
├─ pyproject.toml       # Poetry deps (FastAPI, MiniLM, GPT‑4o client…)
├─ Dockerfile
├─ docker‑compose.yml   # FastAPI + Postgres/pgvector (use with podman-compose)
├─ app/ …               # entrypoint, routers, services
└─ docs/architecture.md # diagrams, future notes
```

---

## 4. Minimal DB Schema

```sql
CREATE TABLE resumes (
  id SERIAL PRIMARY KEY,
  raw_text TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE resume_chunks (
  id SERIAL PRIMARY KEY,
  resume_id INT REFERENCES resumes(id) ON DELETE CASCADE,
  chunk_text TEXT NOT NULL,
  embedding VECTOR(384)
);
```

---

## 5. Local Embedding & Retrieval

1. **Model** – `sentence-transformers/all-MiniLM-L6-v2`, CPU‑friendly, 384‑dim vectors.
2. **Chunk size** – \~200 words max to avoid context blow‑up.
3. **Similarity query** – `ORDER BY embedding <-> :q LIMIT 12` (k=12).
4. **Quality** – \~5‑10 pp below OpenAI embeddings; acceptable for retrieval‑only stage.

---

## 6. API Endpoints (v0.1)

| Verb | Path      | Body                   | Returns                      |
| ---- | --------- | ---------------------- | ---------------------------- |
| POST | `/resume` | text or PDF            | `{"resume_id": 1}`           |
| POST | `/tailor` | `{resume_id, jd_text}` | `tailored_text, chunk_ids[]` |
| GET  | `/health` | –                      | `{"status":"ok"}`            |

---

## 7. Next Increments (post‑MVP)

1. **LLMOps** – add cost logging, retry, and eval harness.
2. **Azure container deploy doc** – optional JD checkbox.
3. **Agentic skill‑gap explainer** – small LangGraph chain for bonus JD bullet.

---

This document now combines **product goals, detailed workflow, file layout, DB schema**, and clear API contract—enough context for Claude or any engineer to scaffold, implement, and iterate without confusion.
