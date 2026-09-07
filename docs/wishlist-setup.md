# ウィッシュリスト セットアップ手順(iPhone)

## 1. GitHub PAT(fine-grained)を発行する

1. https://github.com/settings/personal-access-tokens/new を開く
2. Token name: `wishlist-shortcut`
3. Expiration: 1年(失効したら再発行してショートカット内のトークンを差し替える)
4. Repository access: **Only select repositories** → `monoporhy/clothes`
5. Permissions → Repository permissions → **Contents: Read and write**(これだけでよい)
6. Generate token → 表示されたトークン(`github_pat_...`)をコピー

## 2. iPhoneショートカットを作る

ショートカットアプリ → 「+」で新規作成:

1. 名前: **欲しい服に追加**
2. 上部の(i)→ **共有シートに表示** をオン。「共有シートタイプ」は **URL** と **テキスト** にする
3. アクションを追加: **URLの内容を取得**
   - URL: `https://api.github.com/repos/monoporhy/clothes/dispatches`
   - 「方法を表示」を開き Method: **POST**
   - ヘッダを追加:
     - `Authorization` = `Bearer github_pat_XXXX`(手順1のトークン)
     - `Accept` = `application/vnd.github+json`
   - 本文を要求: **JSON**
     - `event_type`(テキスト)= `wishlist-add`
     - `client_payload`(辞書)→ 中に `url`(テキスト)= 変数「**ショートカットの入力**」
4. アクションを追加: **通知を表示** → 「ウィッシュリストに追加しました」

## 3. 使い方

Instagramアプリで投稿の「共有」(紙飛行機ではなく「…」→共有 でもよい)→ 共有シートから **欲しい服に追加** をタップ。
1〜2分後に https://monoporhy.github.io/clothes/wishlist.html の「整理待ち」に現れる。

## トラブルシューティング

- 通知が失敗(401): PATの期限切れ → 手順1で再発行し、ショートカットの `Authorization` ヘッダを差し替える
- 「整理待ち」に出ない: GitHub の Actions タブで `wishlist-add` の実行ログを確認
- 画像が NO IMAGE: Instagram側の取得拒否。PCで「ウィッシュリスト整理して」と頼めば補完を試みる
