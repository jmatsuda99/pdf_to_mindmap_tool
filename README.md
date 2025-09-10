# PDF → 構文木（Graphviz / Sunburst） v5.2

- **PDF抽出ライブラリの自動フォールバック**：`pypdf` → `PyPDF2` の順
- **テキスト入力モード**：PDF抽出が難しい環境でも試せます
- **python-graphviz不要**：DOTを自前生成して `st.graphviz_chart()` で描画
- 既定の深さ **L=2**、表示モードは **Graphvizツリー / Sunburst / Treemap / アウトライン**

## 使い方
```bash
pip install -r requirements.txt
streamlit run app.py
```
- Cloudで `requirements.txt` が効かない場合は、`pypdf` を個別に追加してください。
