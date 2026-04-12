# ドキュメント一覧

Gemma4 × Playwright 自動E2Eテストシステムの概要設計ドキュメント。

## ドキュメント

| ファイル | 概要 |
|----------|------|
| [architecture-overview.md](./architecture-overview.md) | システム全体の構成案（A〜D）の比較と推奨アーキテクチャ |
| [ec2-vs-fargate.md](./ec2-vs-fargate.md) | ECS Fargate と AWS Batch + EC2 の比較・EC2ベース3パターンの検討 |
| [cost-comparison.md](./cost-comparison.md) | CPU推論・GPU推論それぞれのランニングコスト試算（月100回想定） |
| [cold-start-analysis.md](./cold-start-analysis.md) | コンテナ起動フェーズの分解・モデル配置戦略（ECR/AMI/EFS）のコスト込み比較 |
| [concerns-and-visualization.md](./concerns-and-visualization.md) | 懸念事項（セキュリティ・再現性等）と結果視覚化の選択肢 |
| [dev-stack.md](./dev-stack.md) | 開発基盤の技術選定（IaC/Lambda/コンテナの言語・ツール構成） |

## 設計サマリー

### 推奨アーキテクチャ

```
[API Gateway] → [Lambda] → [AWS Batch] → [EC2 g4dn + Docker]
                                              Gemma4 + Playwright
                                                   │
                                    ┌──────────────┼──────────────┐
                                   [S3]    [CloudWatch Logs]    [SNS]
                               テスト結果        ログ           完了通知
```

### 技術スタック

| レイヤー | 採用技術 |
|----------|----------|
| IaC | AWS CDK（TypeScript） |
| CI/CD | GitHub Actions |
| オーケストレーター | Lambda（Python） |
| ジョブ管理 | AWS Batch |
| コンテナ実行 | EC2 g4dn（Spot） |
| Gemma4推論 | llama-cpp-python |
| E2Eテスト | Playwright（Python） |
| 結果保存 | S3 + Playwright HTML Report |
| 通知 | SNS / Slack Webhook |

### モデル配置方針

- **PoC〜月100回**: 毎回ECRからpull（シンプル優先）
- **月1,000回超**: AMIにDockerイメージをキャッシュ（コスト最適化）
