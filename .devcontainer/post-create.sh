#!/bin/bash
set -e

echo "=== AWS CDK CLI ==="
npm install -g aws-cdk

echo "=== uv (Python package manager) ==="
curl -LsSf https://astral.sh/uv/install.sh | sh
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc

echo "=== Playwright (ローカル動作確認用) ==="
pip install playwright
playwright install chromium --with-deps

echo "=== Ollama (Gemma4 ローカル推論用) ==="
curl -fsSL https://ollama.com/install.sh | sh

echo "=== 完了 ==="
echo "次のステップ:"
echo "  CDK:     cd infra && npm install"
echo "  Ollama:  ollama pull gemma3  # gemma4リリース後は gemma4 に変更"
