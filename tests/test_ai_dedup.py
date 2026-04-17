"""Tests for semantic alert deduplication via LLM embeddings (issue #81)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from opensoar.ai.embeddings import (
    EmbeddingClient,
    EmbeddingResponse,
    cosine_similarity,
    get_embedding_client,
)
from opensoar.integrations.cache import InMemoryCacheBackend


# ── Unit: cosine similarity ─────────────────────────────────────────


class TestCosineSimilarity:
    def test_identical_vectors_return_one(self):
        assert cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_return_zero(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors_return_negative_one(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_empty_vectors_return_zero(self):
        assert cosine_similarity([], []) == 0.0

    def test_zero_vector_returns_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_mismatched_length_returns_zero(self):
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


# ── Unit: embedding client ──────────────────────────────────────────


class TestEmbeddingClient:
    def test_supports_multiple_providers(self):
        c = EmbeddingClient(provider="openai", api_key="k", model="text-embedding-3-small")
        assert c.provider == "openai"
        c = EmbeddingClient(provider="ollama", base_url="http://x", model="nomic-embed-text")
        assert c.provider == "ollama"
        c = EmbeddingClient(provider="anthropic", api_key="k", model="voyage-3")
        assert c.provider == "anthropic"

    async def test_embed_calls_provider(self):
        c = EmbeddingClient(provider="openai", api_key="k", model="text-embedding-3-small")
        with patch.object(
            c,
            "_call_provider",
            new_callable=AsyncMock,
            return_value=EmbeddingResponse(vector=[0.1, 0.2, 0.3], model="text-embedding-3-small"),
        ):
            resp = await c.embed("some text")
            assert resp.vector == [0.1, 0.2, 0.3]
            assert resp.model == "text-embedding-3-small"

    def test_unknown_provider_raises(self):
        c = EmbeddingClient(provider="bogus", api_key="k", model="x")
        with pytest.raises(ValueError):

            async def _call():
                await c._call_provider(text="hello")

            import asyncio
            asyncio.get_event_loop().run_until_complete(_call())


# ── Unit: provider factory ──────────────────────────────────────────


class TestGetEmbeddingClient:
    def test_none_when_no_provider(self):
        with patch("opensoar.ai.embeddings.settings") as mock_settings:
            mock_settings.ai_embedding_provider = None
            mock_settings.openai_api_key = None
            mock_settings.anthropic_api_key = None
            mock_settings.ollama_url = None
            assert get_embedding_client() is None

    def test_openai_when_configured(self):
        with patch("opensoar.ai.embeddings.settings") as mock_settings:
            mock_settings.ai_embedding_provider = "openai"
            mock_settings.openai_api_key = "sk-test"
            mock_settings.anthropic_api_key = None
            mock_settings.ollama_url = None
            mock_settings.ai_embedding_model = None
            c = get_embedding_client()
            assert c is not None
            assert c.provider == "openai"
            assert c.model == "text-embedding-3-small"

    def test_ollama_when_configured(self):
        with patch("opensoar.ai.embeddings.settings") as mock_settings:
            mock_settings.ai_embedding_provider = "ollama"
            mock_settings.openai_api_key = None
            mock_settings.anthropic_api_key = None
            mock_settings.ollama_url = "http://localhost:11434"
            mock_settings.ai_embedding_model = None
            c = get_embedding_client()
            assert c is not None
            assert c.provider == "ollama"

    def test_auto_detect_openai_key(self):
        """When no explicit provider is set, fall back to first available api key."""
        with patch("opensoar.ai.embeddings.settings") as mock_settings:
            mock_settings.ai_embedding_provider = None
            mock_settings.openai_api_key = "sk-test"
            mock_settings.anthropic_api_key = None
            mock_settings.ollama_url = None
            mock_settings.ai_embedding_model = None
            c = get_embedding_client()
            assert c is not None
            assert c.provider == "openai"


# ── Integration: /ai/deduplicate endpoint ───────────────────────────


@pytest.fixture
def memory_cache_backend():
    """Provide an in-memory cache backend for dedup tests."""
    from opensoar.integrations.cache import EnrichmentCache

    backend = InMemoryCacheBackend()
    cache = EnrichmentCache(backend=backend)
    with patch("opensoar.api.ai_dedup.get_default_cache", return_value=cache):
        yield cache


class TestDeduplicateEndpoint:
    async def test_returns_503_when_no_provider(self, client, registered_analyst, sample_alert_via_api):
        alert_id = sample_alert_via_api["alert_id"]
        with patch("opensoar.api.ai_dedup.get_embedding_client", return_value=None):
            resp = await client.post(
                "/api/v1/ai/deduplicate",
                json={"alert_id": str(alert_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 503
            assert "not configured" in resp.json()["detail"].lower()

    async def test_returns_404_for_missing_alert(self, client, registered_analyst):
        with patch("opensoar.api.ai_dedup.get_embedding_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.embed.return_value = EmbeddingResponse(
                vector=[0.1] * 8, model="text-embedding-3-small"
            )
            mock_get.return_value = mock_client
            resp = await client.post(
                "/api/v1/ai/deduplicate",
                json={"alert_id": "00000000-0000-0000-0000-000000000000"},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 404

    async def test_requires_authentication(self, client, sample_alert_via_api):
        alert_id = sample_alert_via_api["alert_id"]
        resp = await client.post(
            "/api/v1/ai/deduplicate",
            json={"alert_id": str(alert_id)},
        )
        assert resp.status_code == 401

    async def test_empty_corpus_returns_empty_candidates(
        self, client, registered_analyst, sample_alert_via_api, memory_cache_backend
    ):
        """With a high threshold and unique vectors, no corpus alert should match."""
        alert_id = sample_alert_via_api["alert_id"]

        with patch("opensoar.api.ai_dedup.get_embedding_client") as mock_get:
            mock_client = AsyncMock()
            call_count = {"n": 0}

            async def _embed(text):
                # Each call returns a unique orthogonal basis vector in a large
                # space. The first alert gets [1,0,0,...,0], the second
                # [0,1,0,...,0], etc. — so cosine similarity between any two
                # is exactly 0.0.
                call_count["n"] += 1
                v = [0.0] * 64
                v[call_count["n"] % 64] = 1.0
                return EmbeddingResponse(vector=v, model="mock")

            mock_client.embed.side_effect = _embed
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/deduplicate",
                json={"alert_id": str(alert_id), "threshold": 0.99},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["alert_id"] == str(alert_id)
            assert data["candidates"] == []
            assert data["threshold"] == 0.99

    async def test_similarity_threshold_filters_candidates(
        self,
        client,
        registered_analyst,
        db_session_factory,
        memory_cache_backend,
    ):
        """Only alerts with similarity >= threshold should appear."""
        import uuid as uuidlib

        from opensoar.models.alert import Alert

        # Build three alerts in the DB, assigning known embeddings.
        a_id = uuidlib.uuid4()
        b_id = uuidlib.uuid4()  # near-duplicate
        c_id = uuidlib.uuid4()  # far

        async with db_session_factory() as sess:
            for aid, title in [
                (a_id, "Brute force login attempts on web-01"),
                (b_id, "Brute force login attempts against web-01"),
                (c_id, "Disk usage at 95% on db-server"),
            ]:
                sess.add(
                    Alert(
                        id=aid,
                        source="webhook",
                        source_id=str(aid),
                        title=title,
                        severity="high",
                        status="new",
                        raw_payload={"title": title},
                        normalized={"title": title},
                    )
                )
            await sess.commit()

        # Prime the cache with deterministic vectors.
        vectors = {
            str(a_id): [1.0, 0.0, 0.0],
            str(b_id): [0.99, 0.14, 0.0],  # cos ≈ 0.99
            str(c_id): [0.0, 1.0, 0.0],  # cos ≈ 0.0
        }
        for aid, vec in vectors.items():
            await memory_cache_backend.backend.set(
                f"opensoar:ai_embedding:{aid}",
                json.dumps({"vector": vec, "model": "mock"}),
                ttl_seconds=3600,
            )

        with patch("opensoar.api.ai_dedup.get_embedding_client") as mock_get:
            mock_client = AsyncMock()

            async def _embed(text):
                # Fallback: return something orthogonal so untouched alerts stay
                # below threshold. Cached entries should short-circuit this.
                return EmbeddingResponse(vector=[0.0, 0.0, 1.0], model="mock")

            mock_client.embed.side_effect = _embed
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/deduplicate",
                json={"alert_id": str(a_id), "threshold": 0.9},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["threshold"] == 0.9
            cand_ids = [c["alert_id"] for c in data["candidates"]]
            assert str(b_id) in cand_ids
            assert str(c_id) not in cand_ids
            assert str(a_id) not in cand_ids  # don't self-match

            # Each candidate has a similarity score.
            for c in data["candidates"]:
                assert 0.0 <= c["similarity"] <= 1.0

    async def test_uses_cached_embedding_when_available(
        self,
        client,
        registered_analyst,
        db_session_factory,
        memory_cache_backend,
    ):
        """A cached embedding should be reused without re-embedding the target."""
        import uuid as uuidlib

        from opensoar.models.alert import Alert

        unique_title = f"CacheTest-{uuidlib.uuid4().hex[:12]}"
        alert_id = uuidlib.uuid4()

        async with db_session_factory() as sess:
            sess.add(
                Alert(
                    id=alert_id,
                    source="webhook",
                    source_id=str(alert_id),
                    title=unique_title,
                    severity="high",
                    status="new",
                    raw_payload={"title": unique_title},
                    normalized={"title": unique_title},
                )
            )
            await sess.commit()

        await memory_cache_backend.backend.set(
            f"opensoar:ai_embedding:{alert_id}",
            json.dumps({"vector": [0.5, 0.5, 0.5], "model": "cached-model"}),
            ttl_seconds=3600,
        )

        embedded_texts: list[str] = []

        async def _embed(text):
            embedded_texts.append(text)
            return EmbeddingResponse(vector=[0.0, 1.0, 0.0], model="mock")

        with patch("opensoar.api.ai_dedup.get_embedding_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.embed.side_effect = _embed
            mock_get.return_value = mock_client

            resp = await client.post(
                "/api/v1/ai/deduplicate",
                json={"alert_id": str(alert_id)},
                headers=registered_analyst["headers"],
            )
            assert resp.status_code == 200
            # The target's unique title never gets embedded (cache hit on id).
            assert not any(unique_title in t for t in embedded_texts)
