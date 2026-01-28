# semantic-llm-cache
A high-performance semantic caching layer for LLM applications designed to minimize redundant LLM calls, built with FastAPI and Redis, featuring exact and embedding-based cache reuse with smart, query-aware TTLs set by a helper llm.

## Run with Docker

```bash
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY
docker compose up --build
```

This starts the API on `localhost:3000` and Redis on `localhost:6379`.
RedisInsight is available at `http://localhost:8001`.

Example usage:

```bash
curl -s -X POST localhost:3000/api/query \
  -H 'content-type: application/json' \
  -d '{"query":"hello"}'
```
