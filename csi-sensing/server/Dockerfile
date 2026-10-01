FROM python:3.12-slim

WORKDIR /app
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ /app/server/
COPY web/ /app/web/

ENV CSI_WEB_DIR=/app/web
EXPOSE 8000 5006

WORKDIR /app/server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
