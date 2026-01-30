import json
import random
import time

from locust import HttpUser, SequentialTaskSet, between, task


def _post_query(client, query: str, force_refresh: bool = False, name: str = "/api/query"):
    payload = json.dumps({"query": query, "forceRefresh": force_refresh})
    return client.post(
        "/api/query",
        data=payload,
        headers={"content-type": "application/json"},
        name=name,
    )


class CorrectnessFlow(SequentialTaskSet):
    def on_start(self) -> None:
        self.q0 = "Who is the best soccer player?"
        self.q1 = "Who is one of the best soccer players?"

    @task
    def prime(self) -> None:
        with _post_query(self.client, self.q0, name="/api/query [prime]") as resp:
            if resp.status_code != 200:
                resp.failure(f"expected 200, got {resp.status_code}")
                return
            meta = (resp.json() or {}).get("metadata", {})
            if meta.get("source") != "llm":
                resp.failure(f"expected prime source=llm, got {meta.get('source')!r}")
                return

    @task
    def exact_duplicate_should_hit_l1(self) -> None:
        time.sleep(2)  # allow async write to complete
        with _post_query(self.client, self.q0, name="/api/query [dup]") as resp:
            if resp.status_code != 200:
                resp.failure(f"expected 200, got {resp.status_code}")
                return
            meta = (resp.json() or {}).get("metadata", {})
            if meta.get("source") != "cache" or meta.get("cache_type") != "l1":
                resp.failure(f"expected l1 cache hit, got {meta!r}")
                return

    @task
    def paraphrase_should_hit_l2(self) -> None:
        with _post_query(self.client, self.q1, name="/api/query [paraphrase]") as resp:
            if resp.status_code != 200:
                resp.failure(f"expected 200, got {resp.status_code}")
                return
            meta = (resp.json() or {}).get("metadata", {})
            if meta.get("source") != "cache" or meta.get("cache_type") != "l2":
                resp.failure(f"expected l2 cache hit, got {meta!r}")
                return

    @task
    def paraphrase_repeat_stays_l2(self) -> None:
        # After an L2 hit, the service may promote this exact query into L1 asynchronously.
        with _post_query(self.client, self.q1, name="/api/query [paraphrase dup]") as resp:
            if resp.status_code != 200:
                resp.failure(f"expected 200, got {resp.status_code}")
                return
            meta = (resp.json() or {}).get("metadata", {})
            if meta.get("source") != "cache" or meta.get("cache_type") not in {"l1", "l2"}:
                resp.failure(f"expected cache hit (l1 or l2), got {meta!r}")
                return


class CorrectnessUser(HttpUser):
    tasks = [CorrectnessFlow]
    wait_time = between(0.0, 0.0)
    weight = 1


LOW_RISK = [
    "What is the capital of France?",
    "Explain what semantic caching is in one sentence.",
    "Define vector search.",
    "Who is the best soccer player?",
    "Who is one of the best soccer players?",
]

SOCCER_L2_VARIANTS = [
    "Who is the best soccer player",
    "Who is the best soccer player??",
    "Who is the best soccer player?!",
    "Who's the best soccer player?",
    "Who is the best soccer player in the world?",
    "Who is the best soccer player in one sentence?",
    "Who is the best soccer player (soccer)?",
    "Who is one of the best soccer players",
    "Who is one of the best soccer players?",
    "Who is one of the best soccer players??",
    "Who is one of the best soccer players?!",
    "Who is one of the best soccer players in the world?",
    "Who is one of the best soccer players in one sentence?",
    "Who is one of the best soccer players (soccer)?",
]

HIGH_RISK = [
    "What's the weather today in New York?",
    "What is the current price of Bitcoin?",
    "Latest news today",
]


class LoadUser(HttpUser):
    wait_time = between(0.05, 0.2)
    weight = 5

    @task
    def mixed_load(self) -> None:
        roll = random.random()
        
        force_refresh = roll < 0.05

        if roll < 0.45:
            query = random.choice(SOCCER_L2_VARIANTS)
        else:
            pick = HIGH_RISK if roll < 0.15 else LOW_RISK
            query = random.choice(pick)
        _post_query(self.client, query, force_refresh=force_refresh, name="/api/query [load]")

