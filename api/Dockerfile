FROM python:3.12-slim

LABEL org.opencontainers.image.name="mem0/openmemory-mcp"

# 安装 wget 用于健康检查
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/openmemory

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.json .
COPY . .

# Apply mem0 patch to fix LLM response parsing
RUN python mem0_patch.py || echo "Warning: mem0 patch failed, but continuing..."

EXPOSE 8765
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]
