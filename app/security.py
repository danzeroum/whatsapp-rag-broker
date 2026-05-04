import hashlib
import hmac
import os

from fastapi import HTTPException, Request


async def verify_signature(request: Request) -> bool:
    """
    Valida a assinatura HMAC-SHA256 enviada pela Meta no header X-Hub-Signature-256.
    APP_SECRET é lido em tempo de execução para que monkeypatch funcione nos testes
    e para que rotação de segredos em produção (AWS Secrets Manager) seja possível
    sem reiniciar o processo.
    """
    app_secret = os.getenv("META_APP_SECRET", "minha_chave_secreta_meta")

    signature_header = request.headers.get("X-Hub-Signature-256")

    if not signature_header:
        raise HTTPException(status_code=403, detail="Header X-Hub-Signature-256 ausente.")

    try:
        _, signature = signature_header.split("=", 1)
    except ValueError:
        raise HTTPException(status_code=403, detail="Formato de assinatura inválido.")

    body = await request.body()

    expected = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=403, detail="Assinatura inválida — requisição rejeitada.")

    return True
