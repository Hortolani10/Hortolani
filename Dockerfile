# Imagem do bot. Roda como usuário sem privilégios; dados ficam no volume /app/runtime.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN useradd --create-home --uid 10001 bot
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade "pip>=26.2.2" certifi \
 && pip install --no-cache-dir -r requirements.txt
COPY bot ./bot
COPY config.yaml config_ativo.yaml config_aprendiz*.yaml PROMPT_ANALISE.md ./

USER bot
WORKDIR /app/runtime
ENTRYPOINT ["python", "-m", "bot", "--config", "/app/config.yaml"]
CMD ["paper"]
