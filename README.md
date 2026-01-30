### semantic-llm-cache

### Overview
`semantic-llm-cache` is a semantic caching service built with **FastAPI** + **Redis Stack** (RediSearch vector index). It reduces redundant LLM calls by serving exact matches **(L1 cache)** and semantic matches **(L2 cache)**. Cache ttl's are set via a helper llm that determines the keys risk of staleness.


### High-level flow (one request)
- **Assess Query Staleness Risk**: Use key word matching to identify time-sensitive high risk queries to bypass cache ('now', 'current', 'latest')
- **L1 lookup**: exact `l1:<query>` match returns immediately.
- **Embed + ANN search**: compute query embedding and run vector KNN search.
- **L2 lookup**: if similarity is above certain match threshold, return `l2:<cache_id>`.
- **LLM fallback**: If no cache hits, call and LLM and return response .
- **Async Cache Writes**: On cache misses, Asynchronously call cheap helper LLM to classify the queries TTL and write to both caches.

### Cache layers (what we store)
- **L1 (exact cache)**: exact string match cache (fast path).
- **L2 (semantic cache)**: semantic reuse across similar queries (embedding + ANN search (cosine similarity) to find a prior answer).
- **Metrics (counters/sums)**:
  - **Purpose**: Stores all cache miss/hit metrics for observability

### System design
![Semantic Cache System Design](images/SemanticCacheSystemDesign.png)

### UI (metrics dashboard)
- **URL**: `http://localhost:4000`
- **What it shows**: hit % and avg latency for L1 / L2 / LLM (derived client-side from `/api/metrics`).

### Load testing (Locust)
Use the load test API route (dev-only):
- `POST /api/loadtest` runs Locust headlessly inside the API container.
- The server clears Redis at the start of the run to ensure a cold start.

Params:
- **`users`**: max concurrent users
- **`spawn_rate`**: users spawned per second until `users`
- **`run_time`**: duration (e.g. `10s`, `1m`)

```bash
curl -s -X POST localhost:3000/api/loadtest \
  -H 'content-type: application/json' \
  -d '{"users":10,"spawn_rate":5,"run_time":"20s"}'
```

### Docker setup
1) Create `.env`:

```bash
cp .env.example .env
# set OPENROUTER_API_KEY in .env
```

2) Start everything:

```bash
docker compose up --build
```