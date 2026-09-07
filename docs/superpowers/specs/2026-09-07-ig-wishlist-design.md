# IGウィッシュリスト 設計書

日付: 2026-09-07
ステータス: 承認済み

## 目的

Instagramで見かけて「その場で見て終わり」になっている服を、iPhoneからワンタップで記録し、AI(Claude Code セッション)が手持ちの服(clothes.json)と照合してスコアリングした「厳選ウィッシュリスト」としてスマホ/PCから閲覧できるようにする。

制約: 従量課金API(Claude API)は使わない。既存構成(静的GitHub Pages、ビルドなし)を崩さない。

## 全体像

```
[iPhone] IG投稿 → 共有シート「欲しい服に追加」ショートカット
    → GitHub repository_dispatch を POST(fine-grained PAT使用)
[GitHub Action] 起動 → wishlist.json に inbox 項目を追記
    + 投稿画像/キャプションをベストエフォート取得 → commit & push
[PC] Claude Code で「ウィッシュリスト整理して」
    → inbox 項目を処理: 画像補完、clothes.json と照合しスコア・コメント付与
    → wishlist.json 更新 → commit & push
[閲覧] https://monoporhy.github.io/clothes/wishlist.html
```

## データスキーマ(`wishlist.json`)

ルート直下、clothes.json と並置。配列。

```json
{
  "id": "ig-DAbc123",
  "ig_url": "https://www.instagram.com/p/DAbc123/",
  "image": "images/wishlist/ig-DAbc123.jpg",
  "caption": "取得できたキャプション(なければ \"\")",
  "brand": "LIDNM",
  "category": "トップス",
  "score": 82,
  "ai_comment": "手持ちのウールスラックスと合わせやすい。白Tと用途が被る点は注意",
  "similar_owned": ["lidnm-white-l-2025-08"],
  "status": "inbox",
  "added_at": "2026-09-07"
}
```

- `id`: 投稿URLの shortcode から `ig-{shortcode}`。重複登録はこのidで排除
- `status`: `inbox`(未整理)→ `scored`(整理済み)。ページ上の非表示は localStorage で行い JSON には持たない
- `brand` / `category` / `score` / `ai_comment` / `similar_owned`: PC整理時にAIが付与。未整理時は `""` / `null` / `[]`
- `category` は clothes.json と同じ値域(トップス/ボトムス/アウター/シューズ/バッグ/アクセサリー/その他)

## コンポーネント

### 1. iPhoneショートカット「欲しい服に追加」

- 共有シートからURL(テキスト)を受け取る
- `POST https://api.github.com/repos/monoporhy/clothes/dispatches` に `{"event_type": "wishlist-add", "client_payload": {"url": "<共有されたURL>"}}` を送信
- 認証: fine-grained PAT(このリポジトリのみ、Contents: Read/Write 相当の最小権限)をショートカット内に保存
- 成功/失敗を通知で表示
- 作成は手動(セットアップ手順書を用意し、対話で案内する)

### 2. GitHub Action(`.github/workflows/wishlist-add.yml`)

- トリガー: `repository_dispatch` (`types: [wishlist-add]`)
- 処理(Pythonスクリプト `scripts/wishlist_add.py` を呼ぶ):
  1. `client_payload.url` から shortcode を抽出(`/p/`, `/reel/` 対応)。抽出できないURLは何もせず終了(ログに残す)
  2. wishlist.json に同 id があれば終了(重複排除)
  3. `https://www.instagram.com/p/{shortcode}/embed/captioned/` を UA 付きで取得し、画像URLとキャプションをベストエフォートで抽出。画像は `images/wishlist/ig-{shortcode}.jpg` に保存
  4. 取得可否に関わらず inbox 項目を wishlist.json に追記し、commit & push(`github-actions[bot]`)
- AI・外部課金APIは使わない。公開リポジトリなので Actions 無料枠
- 同時実行対策: `concurrency` グループで直列化

### 3. PC整理フロー(Claude Code 手順書 `docs/wishlist-triage.md`)

- ユーザーが「ウィッシュリスト整理して」と言ったら:
  1. `status: "inbox"` の項目を列挙
  2. 画像未取得の項目はブラウザ(claude-in-chrome)等で補完を試みる。無理ならユーザーにスクショを依頼
  3. 各項目を clothes.json と照合してスコアリング(下記基準)、`brand`/`category`/`score`/`ai_comment`/`similar_owned` を記入、`status: "scored"` に更新
  4. commit & push
- スコア基準(0–100):
  - 手持ちとの重複度が高い(同カテゴリ・同色・同シルエットを既に所有)→ 減点、`similar_owned` に記録
  - 手持ちとコーデが組みやすい(色・カテゴリの補完関係)→ 加点
  - 所有ブランド傾向(LIDNM等)との一致 → 小幅加点
  - コメントは「買うべきか迷ったときの判断材料」を1〜2文で

### 4. 閲覧ページ(`wishlist.html`)

- index.html / coordinate.html のダークUIを踏襲した自己完結の静的ページ(ビルドなし・依存なし)
- fetch で wishlist.json(+similar_owned 表示用に clothes.json)を読み込み
- スコア降順のカード表示: 画像、ブランド、スコア、AIコメント、IG投稿へのリンク、似た手持ち服のサムネイル
- `status: "inbox"` の項目は「整理待ち」セクションに分けて表示
- フィルタ: カテゴリ、スコア下限
- 非表示(却下)ボタン: localStorage に id を保存して除外。リセット操作あり
- index.html のヘッダーに wishlist.html への相互リンクを追加

## エラー処理

- ショートカット送信失敗(圏外・PAT失効): ショートカットが失敗通知を出す。再共有でリトライ
- Instagram が画像取得を拒否: URLのみの inbox 項目として登録され、PC整理時に補完
- 不正URL(IG以外を共有): Action が無視(wishlist.json は変更しない)
- Action の push 競合: concurrency 直列化で回避

## テスト

- `scripts/wishlist_add.py`: shortcode抽出・重複排除・JSON追記をローカルでユニットテスト(実IGアクセスはモック)
- Action: `gh api repos/monoporhy/clothes/dispatches` を手で叩いて end-to-end 確認
- wishlist.html: サンプルデータでローカル(`python3 -m http.server`)表示確認
- ショートカット: 実機で共有→Action起動→ページ反映まで通しで確認

## 公開範囲の注意

リポジトリは公開のため、ウィッシュリスト(欲しい服・IGリンク)も公開される。既存の手持ちカタログと同じ扱いで許容済み。

## セットアップ(実装後にユーザーと行う)

1. fine-grained PAT 発行(対象: monoporhy/clothes のみ)
2. iPhoneショートカット作成(手順書に従い対話で案内)
3. 実機テスト
