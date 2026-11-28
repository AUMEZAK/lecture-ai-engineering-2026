# 第6回 解答

## 演習

<!-- [tool call] の行は、表示された行をそのまま貼り付けてください。終わらなかった STEP は、空欄のままでかまいません。 -->

- STEP 1 のツールの名前：
- STEP 2 の [tool call]：
- STEP 3 の [tool call]：
- STEP 4 の [tool call]：
- 気づき・疑問：

## 宿題

- 取り組んだレベル：基礎
- やったこと：
  - 第6回の開始タグ `lec06-start`（`03d0fd36d58ada1ac1366c0d485ac103ef44ca52`）を基点に、`app/mcp_server.py` のTODO直下へ `server.tool()(tools.get_lecture_summary)` を1行追加した。
  - `app/mcp_agent.py`、`app/mcp_servers.json`、`app/tools.py`、`tests/` は変更していない。解答記入前の変更ファイルは `app/mcp_server.py` だけだった。
- 結果：
  - `uv run python -m app.mcp_agent --list-tools` で、変更前は `glossary_search_glossary` の1個、変更後は `glossary_get_lecture_summary` を含む2個になった。追加ツールの引数 `lecture` は整数型として表示された。
  - `uv run python -m app.mcp_agent --trace "第2回では何を学びますか？"` を実行し、次の呼び出しと戻り値を確認した。

    ```text
    [tool call]   glossary_get_lecture_summary({'lecture': 2})
    [tool return] glossary_get_lecture_summary -> # 第2回 ファインチューニングとLoRA
    ```

  - 最終回答には、事前学習とファインチューニングの違い、SFT、PEFTとLoRA、Google Colabでの演習が含まれ、関連する回として第2回が示された。
  - 実行時の設定モデルは `gemini-3.5-flash-lite`。使用量は入力1,274トークン、出力248トークン、モデル応答2回だった。API応答側のモデル名はこのCLIログには含まれない。
  - `uv run pytest -q` は変更前・変更後とも21件成功した（変更前4.11秒、変更後3.88秒）。
- 気づき・疑問：
  - エージェントは起動時にサーバーから公開ツールを取得するため、サーバー側の公開行だけを追加して、エージェント本体や接続設定を変えずに新しいツールを使えた。
  - 関数の説明文と型ヒントがツールの説明・引数として表示される。設定のサーバー名 `glossary` がツール名の接頭辞になっていることも確認できた。
  - 既存テストの成功だけで追加ツールの実使用まで証明できるわけではないため、一覧の追加と実モデルのtraceも確認した。実モデルでの確認は今回1回であり、毎回同じ文面や使用量になるとまでは言えない。

### 実行ログ

- [変更前のツール一覧](evidence/basic/tools_before.txt)
- [変更後のツール一覧](evidence/basic/tools_after.txt)
- [実モデルの回答・trace](evidence/basic/trace_after.txt)
- [変更前のテスト](evidence/basic/tests_before.txt) / [変更後のテスト](evidence/basic/tests_after.txt)
- [解答記入前の変更ファイル](evidence/basic/status_implementation.txt) / [追加した1行の差分](evidence/basic/implementation.diff)
- [実行条件・終了コード](evidence/basic/run.json) / [照合結果](evidence/basic/verification.json)

配布CLIの `[tool return]` は戻り値の先頭120文字だけを表示するため、ログの末尾に省略記号が付く。元データは [`data/lectures/02.md`](../../data/lectures/02.md) にある。
