FROM python:3.14-slim

# System deps: ffmpeg for audio conversion, build tools for whisper
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js + Claude CLI
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && rm -rf /var/lib/apt/lists/*

# Build whisper.cpp from source
RUN git clone --depth 1 https://github.com/ggerganov/whisper.cpp /opt/whisper.cpp \
    && cd /opt/whisper.cpp && cmake -B build && cmake --build build --config Release -j$(nproc) \
    && cp build/bin/whisper-cli /usr/local/bin/ \
    && find build -name '*.so*' -exec cp {} /usr/local/lib/ \; \
    && ldconfig \
    && rm -rf /opt/whisper.cpp

# Download whisper model
RUN mkdir -p /root/.claude-superpowers/models \
    && curl -L -o /root/.claude-superpowers/models/ggml-base.en.bin \
       https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin

WORKDIR /app
COPY pyproject.toml ./
COPY superpowers/ superpowers/
COPY msg_gateway/ msg_gateway/

RUN pip install --no-cache-dir -e .

# Bot entry point
COPY telegram-bot/entrypoint.py .

CMD ["python", "entrypoint.py"]
