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
sudo apt-get install -y zstd
curl -fsSL https://ollama.com/install.sh | sh

echo "=== Ollama 自動起動設定 ==="
# bashrc に ollama serve の自動起動を追加
cat <<'EOF' >> ~/.bashrc

# Ollama サーバーが起動していなければ自動起動
if ! pgrep -x ollama > /dev/null; then
  ollama serve > /tmp/ollama.log 2>&1 &
fi
EOF

# 初回はここで起動しておく
ollama serve > /tmp/ollama.log 2>&1 &
sleep 3

echo "=== 完了 ==="
echo "次のステップ:"
echo "  CDK:     cd infra && npm install"
echo "  Ollama:  ollama pull gemma4:e4b"
