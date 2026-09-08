#!/bin/bash

set -e

echo "Starting Jenkins..."
docker start jenkins-server

echo "Starting MySQL..."
docker start local-mysql

echo "Starting Ollama..."
ollama serve > ollama.log 2>&1 &
ollama run qwen2.5-coder:1.5b "Hi how are you?"
echo "All services started."
