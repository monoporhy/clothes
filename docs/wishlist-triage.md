# ウィッシュリスト整理手順(Claude Code向け)

ユーザーが「ウィッシュリスト整理して」と言ったら、この手順で `wishlist.json` の
`status: "inbox"` 項目を処理する。

## 手順

1. `git pull` してから `wishlist.json` の inbox 項目を列挙する
2. `image` が空の項目は補完を試みる:
   - `ig_url` の embed ページ(`{ig_url}embed/captioned/`)を WebFetch またはブラウザで取得
   - 無理ならユーザーにスクリーンショット共有を依頼し、`images/wishlist/{id}.jpg` に保存
3. 各項目について画像・キャプションを見て以下を記入する:
   - `brand`: 投稿者・キャプションから推定(不明なら `""`)
   - `category`: トップス / ボトムス / アウター / シューズ / バッグ / アクセサリー / その他
   - `score`: 0–100(下記基準)
   - `ai_comment`: 買うべきか迷ったときの判断材料を1〜2文
   - `similar_owned`: clothes.json の似た手持ち服の id 配列
   - `status`: `"scored"` に変更
4. `git add wishlist.json images/wishlist && git commit -m "feat: ウィッシュリストを整理" && git push`

## スコア基準(0–100)

- **減点**: 手持ちとの重複(同カテゴリ・同色・同シルエットを既に所有)。重複相手は `similar_owned` に必ず記録
- **加点**: 手持ちとコーデが組みやすい(色相環の同系色/補色関係、不足カテゴリの補完)
- **小幅加点**: 所有ブランド傾向(LIDNM / WYM など)との一致
- 目安: 80+ = 買い候補、60–79 = 検討、60未満 = 見送り推奨
