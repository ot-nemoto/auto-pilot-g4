# セットアップガイド

## 前提条件

- AWS CLI 設定済み（適切な権限を持つ IAM ユーザー）
- Docker インストール済み
- Node.js 22 以上
- Python 3.12 以上
- AWS CDK CLI（`npm install -g aws-cdk`）

## 1. リポジトリのクローン

```bash
git clone https://github.com/ot-nemoto/auto-pilot-g4.git
cd auto-pilot-g4
```

## 2. 開発環境（devcontainer）

VS Code の devcontainer を使用すると、必要なツールが自動でセットアップされる。

```
# VS Code で開く
code .
# → "Reopen in Container" を選択
```

devcontainer に含まれるツール：
- Node.js 22 / Python 3.12 / AWS CLI / AWS CDK / Ollama / Playwright

## 3. Docker イメージのビルドと ECR への Push

```bash
# ECR リポジトリ作成（CDK デプロイ後）
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin \
  <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com

# イメージビルド
docker build -t auto-pilot-g4-runner ./runner

# タグ付け & Push
docker tag auto-pilot-g4-runner:latest \
  <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/auto-pilot-g4-runner:latest
docker push \
  <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/auto-pilot-g4-runner:latest
```

## 4. AWS インフラのデプロイ（CDK）

```bash
cd cdk
npm install
cdk bootstrap  # 初回のみ
cdk deploy
```

デプロイされるリソース：
- API Gateway
- Lambda（オーケストレーター）
- AWS Batch（ジョブキュー・ジョブ定義）
- S3 バケット
- SNS トピック
- 必要な IAM ロール

## 5. 動作確認

```bash
# API エンドポイントへテストリクエストを送信
curl -X POST https://<api-id>.execute-api.ap-northeast-1.amazonaws.com/prod/tests \
  -H "Content-Type: application/json" \
  -H "x-api-key: <api-key>" \
  -d '{"repo_url": "https://github.com/ot-nemoto/eval-hub"}'

# レスポンス例
# {"execution_id": "exec-20260415-001", "status": "submitted"}
```

## 6. 結果の確認

```bash
# S3 から結果を取得
aws s3 ls s3://auto-pilot-g4-results/<execution_id>/
aws s3 cp s3://auto-pilot-g4-results/<execution_id>/result.json .
cat result.json
```

## 環境変数

Lambda および Batch ジョブで使用する環境変数：

| 変数名 | 説明 | 設定箇所 |
|--------|------|---------|
| `RESULT_BUCKET` | S3 バケット名 | CDK で自動設定 |
| `SNS_TOPIC_ARN` | 通知先 SNS トピック ARN | CDK で自動設定 |
| `GITHUB_TOKEN` | プライベートリポジトリ用（任意） | Secrets Manager |
