# PDF → Mindmap (Mermaid) with Depth

PDFから章節構造を解析し、**深さ(L)指定**でマインドマップ（Mermaid）として表示・出力するシンプルなツールです。

## 使い方

1. 必要ライブラリをインストール

```bash
pip install -r requirements.txt
```

2. 起動

```bash
streamlit run app.py
```

3. 画面左上の**PDFアップロード**からファイルを選択 → **深さ(L)** スライダーで表示階層を調整。  
4. **エクスポート**欄から JSON / Mermaid / テキストアウトラインをダウンロード可能。

## 注意点

- PDFの抽出は `PyPDF2` を使用しています。レイアウト依存で改行位置や空白が崩れる場合があります。
- 見出し抽出はヒューリスティック（正規表現）です。`第1章`、`付録`、`1.` / `1.1` / `1-1` / `1)` 等の形式を優先検出します。
- Mermaidはコードブロックとして出力しているので、GitHubなどのMermaid対応環境でレンダリングできます。

## 構成

- `app.py` …… Streamlitアプリ本体
- `requirements.txt` …… 依存ライブラリ
- `README.md` …… 使用手順
