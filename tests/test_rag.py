from unittest.mock import patch, MagicMock


class TestRetrieve:
    @patch("app.rag._get_collection")
    def test_retrieve_returns_formatted_results(self, mock_get_col):
        mock_col = MagicMock()
        mock_col.query.return_value = {
            "documents": [["Chunk sobre taxa de juros", "Outro chunk relevante"]],
            "metadatas": [
                [{"source": "politica.txt", "chunk": 0}, {"source": "politica.txt", "chunk": 1}]
            ],
        }
        mock_get_col.return_value = mock_col

        from app.rag import retrieve
        results = retrieve("taxa de juros", top_k=2)

        assert len(results) == 2
        assert results[0]["source"] == "politica.txt"
        assert "taxa de juros" in results[0]["text"]

    @patch("app.rag._get_collection")
    def test_retrieve_with_empty_result(self, mock_get_col):
        mock_col = MagicMock()
        mock_col.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
        }
        mock_get_col.return_value = mock_col

        from app.rag import retrieve
        results = retrieve("pergunta sem resposta")
        assert results == []
