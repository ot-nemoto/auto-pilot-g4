# EC2 vs Fargate 比較検討

## 結論

**EC2をタスクごとに使い捨てする構成は可能**。ただし実現方法によって特性が異なる。
GPU推論が必要な場合はFargateが使えないため、以下の3つのEC2ベース案から選ぶ。

---

## EC2ベース 3パターン比較

### パターン1: EC2 RunInstances（直接起動・自己終了）

```
[Lambda]
  ├─ RunInstances API で g4dn インスタンス起動
  ├─ UserData にテスト実行スクリプトを埋め込む
  └─ インスタンスはテスト完了後に自分で terminate

UserData スクリプト:
  #!/bin/bash
  docker run --gpus all auto-pilot-runner \
    --prompt "$TEST_PROMPT" \
    --target "$TARGET_URL"
  aws ec2 terminate-instances --instance-ids $(ec2-metadata -i)
```

**起動までの時間目安**

| フェーズ | 時間 |
|----------|------|
| EC2インスタンス起動 | 1〜2分 |
| Dockerイメージpull（ECR） | 1〜3分（イメージサイズ次第） |
| GPUドライバ初期化 | 〜30秒 |
| Gemma4モデルロード | 1〜3分（S3から取得する場合） |
| **合計コールドスタート** | **3〜8分** |

**メリット**: シンプル、追加サービス不要  
**デメリット**: 起動失敗時のリトライ・エラーハンドリングを自前で実装する必要がある

---

### パターン2: AWS Batch（推奨）

**AWS Batchはまさにこのユースケースのためのサービス**。
ジョブが来たときだけEC2を起動し、完了後に自動終了・スケールゼロする。

```
[API Gateway] → [Lambda]
                    │ Batch SubmitJob
                    ▼
              [AWS Batch]
               ┌──────────────────────────────┐
               │  Job Queue                   │
               │       │                      │
               │       ▼                      │
               │  Compute Environment         │
               │  （EC2 g4dn / Spot）         │
               │  ・ジョブがあれば起動         │
               │  ・完了後は自動スケールゼロ   │
               └──────────────────────────────┘
                    │
                    ▼
              [Container実行]
              Gemma4 + Playwright
```

**Batchが自動でやってくれること**
- インスタンスの起動・終了
- ジョブキューイング（同時実行数の制限）
- 失敗時の自動リトライ
- Spot Instanceの中断ハンドリング
- CloudWatch Logsへのログ転送

**メリット**: 運用負荷が最も低い、Spot対応でコスト削減可能  
**デメリット**: Batchの概念（Job Definition, Job Queue, Compute Environment）の学習コスト

---

### パターン3: ECS on EC2（Fargate → EC2 Launch Type 変更）

案Aの ECS Fargate を EC2 Launch Type に変更する案。
ECS Cluster に Auto Scaling Group（GPU対応）を紐づける。

```
[ECS Cluster]
  └── Auto Scaling Group（g4dn インスタンス）
        ・ECS Task が来たら EC2 を起動
        ・Task 完了後、スケールゼロで EC2 を終了
```

**メリット**: 案A（ECS Fargate）の設計をほぼ流用できる  
**デメリット**: スケールゼロ〜スケールアップのタイミング調整が複雑（ECS Capacity Provider の設定が必要）

---

## 3パターン総合比較

| 項目 | パターン1（直接RunInstances） | パターン2（AWS Batch） | パターン3（ECS on EC2） |
|------|------------------------------|------------------------|------------------------|
| 実装シンプルさ | ○ シンプル | ◎ マネージド | △ ECS設定が複雑 |
| エラーハンドリング | △ 自前実装 | ◎ 自動リトライ | ○ ECSが管理 |
| Spot対応 | △ 自前実装 | ◎ ネイティブ対応 | ○ 対応可能 |
| スケール制御 | △ 自前実装 | ◎ 自動 | ○ Capacity Provider |
| 起動時間 | 3〜8分 | 3〜8分（同じ） | 3〜8分（同じ） |
| 学習コスト | 低 | 中 | 中〜高 |

**→ パターン2（AWS Batch）を推奨**

---

## コスト試算（g4dn.xlarge の場合）

| 項目 | 単価 |
|------|------|
| g4dn.xlarge オンデマンド | $0.526/時間 |
| g4dn.xlarge Spot（目安） | $0.16〜$0.25/時間 |

**1テスト実行あたりのコスト目安**

| 処理時間 | オンデマンド | Spot |
|----------|-------------|------|
| コールドスタート〜終了: 10分 | $0.088 | $0.027 |
| コールドスタート〜終了: 20分 | $0.175 | $0.053 |

月100回実行（1テスト15分想定）:
- オンデマンド: 約 **$1,300/月**（$0.131 × 100）
- Spot: 約 **$400/月**（$0.04 × 100）

---

## コールドスタート短縮策

起動時間を短縮するには以下のアプローチが有効：

### 1. EFS にモデルを配置
```
EFS（Gemma4モデルを格納）
  └── ECS/Batch Task マウント → S3ダウンロード不要
```
S3ダウンロード（1〜3分）をスキップできる。

### 2. カスタムAMIにモデルをプリインストール
- Gemma4モデルをビルトインしたAMIを作成
- インスタンス起動直後からモデルが使用可能
- AMIのサイズが大きくなる（EBSコスト増）

### 3. Warm Pool（EC2 Auto Scaling）
- インスタンスを停止状態でプールしておく
- 起動時は停止からの再開（1分以内）
- 停止中もEBSコストは発生するが、インスタンスコストはゼロ

### 比較

| 方式 | 短縮効果 | コスト影響 |
|------|----------|------------|
| EFSモデル配置 | 1〜3分短縮 | EFS費用（〜$0.30/GB/月） |
| カスタムAMI | 1〜3分短縮 | EBSスナップショット費用 |
| Warm Pool | 最大5分短縮 | EBS費用のみ（少額） |

---

## 推奨アーキテクチャ更新（GPU対応版）

```
[外部クライアント]
      │ POST /tests
      ▼
[API Gateway]
      │
      ▼
[Lambda: オーケストレーター]
  ・入力バリデーション
  ・AWS Batch SubmitJob
  ・Job ID をクライアントへ返却
      │
      ▼
[AWS Batch]
  ├── Job Queue
  └── Compute Environment
      └── EC2 g4dn（Spot Instance 優先）
            │ Auto Scaling（0〜N台）
            ▼
      [Container: auto-pilot-runner]
      ・Gemma4（GPU推論）
      ・Playwright + Chromium
      ・テスト実行 → S3保存 → 終了
            │
            ├─▶ [S3] テスト結果・スクリーンショット
            ├─▶ [CloudWatch Logs] 実行ログ
            └─▶ [SNS / Webhook] 完了通知
```
