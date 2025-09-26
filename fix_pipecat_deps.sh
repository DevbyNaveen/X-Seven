#!/bin/bash

# Fix PipeCat AI missing dependencies
echo "🔧 Fixing PipeCat AI dependencies..."

# Activate virtual environment
source .venv/bin/activate

# Install missing dependencies
pip install "websockets>=12.0"
pip install "aiohttp>=3.9.0"
pip install "aiortc>=1.6.0"
pip install "pyaudio>=0.2.11"
pip install "sounddevice>=0.4.6"
pip install "speechrecognition>=3.10.0"

# Install PipeCat with all services
pip install "pipecat-ai[elevenlabs,openai,deepgram]"

echo "✅ PipeCat dependencies fixed!"
