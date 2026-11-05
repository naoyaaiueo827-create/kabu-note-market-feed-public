# KABU NOTE — 公開市場データフィード

このリポジトリは **JPX公式日報から集計した公開市場データのみ** を提供します。保有資産、取引記録、KABU NOTE本体のコード、個人情報、認証情報は含めません。

## JSONフィード

**[東証プライムの騰落・出来高データ（JSON）](https://raw.githubusercontent.com/naoyaaiueo827-create/kabu-note-market-feed-public/main/jpfg-breadth.json)**

KABU NOTEに登録するURL：

```text
https://raw.githubusercontent.com/naoyaaiueo827-create/kabu-note-market-feed-public/main/jpfg-breadth.json
```

JSONの内容は `market: TSE_PRIME`、`source`、`unchangedExcluded: true`、`rows: [{date,advancers,decliners,upVolume,downVolume,complete:true}]` です。上昇・下落出来高の単位はJPXの日報の**千株**に統一されています。変わらず銘柄はUDVRから除外します。

## 自動更新

- GitHub Actionsで月〜金曜日の **18:20 JST** に公開日報を確認（実行時刻は遅延する場合があります）
- 出典： [JPX 東京証券取引所日報](https://www.jpx.co.jp/markets/statistics-equities/daily/)
- 通常立会・東証プライム市場の集計だけを取得。スタンダード・グロース市場、ToSTNeT、ETFを混ぜません。
- JPX未公開日、休日、欠損、PDFレイアウト異常は推測して埋めません。
- 配信方法はGitHub Pagesではなく、**GitHubの公開rawファイル**です。

## KABU NOTEへの登録

KABU NOTE → 日本版Fear & Greed →「構成項目・出典・設定」→「騰落・上昇下落別出来高フィード（HTTPS JSON）」に上記URLを入力し、「設定を保存」→「実データを更新」。

「価格系列フィード（任意）」は変更せず、KABU NOTE自身の1306・2561・USDJPY・日経VIを使います。

外部URLからの読み込みが実際に成功するかは、KABU NOTEの画面で検証する必要があります。初回の投入・URL登録作業を行うまで、KABU NOTE本体への自動反映は完了していません。
