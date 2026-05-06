"""Testes do RAG: retrieve com mock do ChromaDB collection."""
from unittest.mock import MagicMock, patch


class TestRetrieve:
    @patch("app.rag._get_collection")
    def test_retrieve_returns_formatted_results(self, mock_get_col):
        mock_col = MagicMock()
        mock_col.query.return_value = {
            "documents": [["Chunk sobre taxa de juros", "Outro chunk relevante"]],
            "metadatas": [
                [{"source": "politica.txt", "chunk": 0}, {"source": "politica.txt", "chunk": 1}]
            ],
            "distances": [[0.3, 0.5]],  # abaixo do threshold 1.2
        }
        mock_get_col.return_value = mock_col

        from app.rag import retrieve

        results = retrieve("taxa de juros", top_k=2)

        assert len(results) == 2
        assert results[0]["source"] == "politica.txt"
        assert "taxa de juros" in results[0]["text"]

    @patch("app.rag._get_collection")
    def test_retrieve_filters_above_threshold(self, mock_get_col):
        """Chunks com distância acima do threshold devem ser descartados."""
        mock_col = MagicMock()
        mock_col.query.return_value = {
            "documents": [["Chunk irrelevante"]],
            "metadatas": [[{"source": "foo.txt", "chunk": 0}]],
            "distances": [[1.5]],  # acima do threshold 1.2
        }
        mock_get_col.return_value = mock_col

        from app.rag import retrieve

        results = retrieve("pergunta qualquer", top_k=1)
        assert results == []

    @patch("app.rag._get_collection")
    def test_retrieve_with_empty_result(self, mock_get_col):
        mock_col = MagicMock()
        mock_col.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        mock_get_col.return_value = mock_col

        from app.rag import retrieve

        results = retrieve("pergunta sem resposta")
        assert results == []
