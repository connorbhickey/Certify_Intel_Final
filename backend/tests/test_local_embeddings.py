"""
Certify Intel - Local Embeddings Tests

Tests for the local sentence-transformers embedding provider.

Run: python -m pytest -xvs tests/test_local_embeddings.py
"""

import pytest
from unittest.mock import MagicMock, patch
import numpy as np


class TestLocalEmbeddingsConfig:
    """Test local embeddings configuration and defaults."""

    def test_disabled_by_default(self, monkeypatch):
        """Local embeddings should be disabled by default."""
        monkeypatch.delenv("USE_LOCAL_EMBEDDINGS", raising=False)
        import importlib
        import local_embeddings
        importlib.reload(local_embeddings)
        assert local_embeddings.USE_LOCAL_EMBEDDINGS is False

    def test_embedding_dimension(self):
        """get_embedding_dimension() should return 384."""
        from local_embeddings import get_embedding_dimension
        assert get_embedding_dimension() == 384

    def test_is_available_when_disabled(self, monkeypatch):
        """is_available() should return False when disabled."""
        monkeypatch.setenv("USE_LOCAL_EMBEDDINGS", "false")
        import importlib
        import local_embeddings
        importlib.reload(local_embeddings)
        assert local_embeddings.is_available() is False


class TestLocalEmbeddingsFunctions:
    """Test embedding functions with mocked model."""

    def test_embed_text_returns_384_dim_vector(self):
        """embed_text() should return a 384-dimension vector."""
        from local_embeddings import embed_text

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(384)

        with patch("local_embeddings._get_model", return_value=mock_model):
            result = embed_text("test text")

        assert isinstance(result, list)
        assert len(result) == 384
        mock_model.encode.assert_called_once_with(
            "test text", convert_to_numpy=True
        )

    def test_embed_batch_returns_correct_count(self):
        """embed_batch() should return correct number of vectors."""
        from local_embeddings import embed_batch

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(3, 384)

        with patch("local_embeddings._get_model", return_value=mock_model):
            result = embed_batch(["text1", "text2", "text3"])

        assert isinstance(result, list)
        assert len(result) == 3
        assert len(result[0]) == 384

    def test_embed_batch_empty_input(self):
        """embed_batch() should return empty list for empty input."""
        from local_embeddings import embed_batch
        result = embed_batch([])
        assert result == []

    def test_embed_batch_uses_batch_size_32(self):
        """embed_batch() should pass batch_size=32 to model."""
        from local_embeddings import embed_batch

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(2, 384)

        with patch("local_embeddings._get_model", return_value=mock_model):
            embed_batch(["text1", "text2"])

        mock_model.encode.assert_called_once_with(
            ["text1", "text2"],
            convert_to_numpy=True,
            batch_size=32,
        )

    def test_get_model_raises_on_missing_dependency(self):
        """_get_model() should raise ImportError if sentence-transformers missing."""
        import local_embeddings
        # Reset cached model
        local_embeddings._model = None

        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError):
                local_embeddings._get_model()

        # Restore
        local_embeddings._model = None

    def test_embed_text_values_are_floats(self):
        """embed_text() should return list of Python floats."""
        from local_embeddings import embed_text

        mock_model = MagicMock()
        mock_model.encode.return_value = np.ones(384)

        with patch("local_embeddings._get_model", return_value=mock_model):
            result = embed_text("test")

        assert all(isinstance(v, float) for v in result)

    def test_is_available_returns_false_when_model_fails(self, monkeypatch):
        """is_available() should return False if model fails to load."""
        monkeypatch.setenv("USE_LOCAL_EMBEDDINGS", "true")
        import importlib
        import local_embeddings
        importlib.reload(local_embeddings)
        local_embeddings._model = None

        with patch(
            "local_embeddings._get_model",
            side_effect=ImportError("no module")
        ):
            assert local_embeddings.is_available() is False

    def test_get_embedding_dimension_is_constant(self):
        """get_embedding_dimension() always returns 384 regardless of state."""
        from local_embeddings import get_embedding_dimension
        assert get_embedding_dimension() == 384
        assert get_embedding_dimension() == 384  # Idempotent
