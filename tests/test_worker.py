"""Testes do worker: ciclo completo RAG + LLM + envio WhatsApp."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.worker import process_event


BASE_EVENT = {
    "msg_id": "wamid.abc123",
    "phone": "5511977777777",
    "text": "qual a taxa de juros?",
    "phone_number_id": "123456789",
}


@pytest.mark.asyncio
async def test_process_event_with_rag_context():
    """worker deve chamar RAG, LLM e enviar resposta correta ao usuário."""
    chunks = [{"text": "Taxa de juros é 12,5% ao mês", "source": "faq.txt", "chunk": 0}]
    llm_answer = "A taxa de juros do crédito rotativo é 12,5% ao mês."

    with patch("app.worker.retrieve", return_value=chunks) as mock_rag, \
         patch("app.worker.generate_response", new_callable=AsyncMock, return_value=llm_answer) as mock_llm, \
         patch("app.worker.send_text_message", new_callable=AsyncMock) as mock_send:

        await process_event(BASE_EVENT)

        mock_rag.assert_called_once_with("qual a taxa de juros?", top_k=3)
        mock_llm.assert_awaited_once()
        mock_send.assert_awaited_once_with("123456789", "5511977777777", llm_answer)


@pytest.mark.asyncio
async def test_process_event_no_rag_context():
    """Quando RAG não encontra chunks, LLM ainda é chamado com contexto vazio."""
    with patch("app.worker.retrieve", return_value=[]) as mock_rag, \
         patch("app.worker.generate_response", new_callable=AsyncMock, return_value="Não possuo essa informação.") as mock_llm, \
         patch("app.worker.send_text_message", new_callable=AsyncMock) as mock_send:

        await process_event({**BASE_EVENT, "text": "qual o horário?"})

        mock_rag.assert_called_once_with("qual o horário?", top_k=3)
        mock_llm.assert_awaited_once()
        # Verifica que a resposta de fallback foi enviada
        args = mock_send.await_args[0]
        assert "Não possuo" in args[2]


@pytest.mark.asyncio
async def test_process_event_passes_correct_phone_number_id():
    """phone_number_id do evento deve ser repassado corretamente para send_text_message."""
    with patch("app.worker.retrieve", return_value=[]), \
         patch("app.worker.generate_response", new_callable=AsyncMock, return_value="ok"), \
         patch("app.worker.send_text_message", new_callable=AsyncMock) as mock_send:

        event = {**BASE_EVENT, "phone_number_id": "PHONE_ID_XYZ"}
        await process_event(event)

        args = mock_send.await_args[0]
        assert args[0] == "PHONE_ID_XYZ"


@pytest.mark.asyncio
async def test_process_event_does_not_raise_on_send_failure():
    """Falha no envio ao WhatsApp não deve derrubar o worker."""
    with patch("app.worker.retrieve", return_value=[]), \
         patch("app.worker.generate_response", new_callable=AsyncMock, return_value="ok"), \
         patch("app.worker.send_text_message", new_callable=AsyncMock, side_effect=Exception("API down")):

        # Não deve lançar excessão — o loop do worker não pode parar
        try:
            await process_event(BASE_EVENT)
        except Exception:
            pytest.fail("process_event() não deve propagar exceções do send_text_message")
