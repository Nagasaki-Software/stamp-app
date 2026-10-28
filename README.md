# StampApp

PDF上のマーカー（ArUcoマーカー）の位置に、電子印鑑（丸印）を自動で押すWindowsデスクトップアプリ。
使い方は [使い方.txt](使い方.txt) を参照。

## 免責事項

- 本ソフトウェアは現状有姿で提供し、いかなる保証もしません。
- 本ソフトウェアの使用により生じた損害について、作者は一切の責任を負いません。
- 法令にもとづく記録・契約・承認の判断に、本ソフトウェアだけを用いないでください。
- 名前のロック機能は、普通の利用者による名前の付け替えを防ぐためのものです。高度な改ざんへの対策ではありません。
- ドキュメントやテストに出てくる人名・データは架空のものです。

## セットアップ

```
py -V:Astral/CPython3.13.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 実行

```
python main.py
```

## EXEビルド

配布用のEXEには、Git 管理外の秘密値ファイル `core/_secrets.py` が必要です（無いとビルドが止まります）。

```python
SIGNING_SECRET = "<64文字のランダムな16進文字列>"
ADMIN_KEY_HASH = "<管理者キーワードの SHA-256（16進）>"
DATA_NAME = "StampApp-Public"  # 省略可。記録（名前ロック・設定・ログ）の置き場所の名前。省略すると "StampApp"
```

鍵が違う版どうしが同じ置き場所を使うと、互いの名前ロックを「改ざん」と判断して押印できなくなります。鍵を変えたら `DATA_NAME` も変えてください。

このファイルが無い状態で `python main.py` を実行すると、開発用の値で動きます。開発用の値は公開されているため、配布には使わないでください。

```
pyinstaller build.spec
```

生成物：`dist/StampApp/StampApp.exe`

## ライセンス

[Apache License 2.0](LICENSE)。同梱しているフォントなどの他者の著作物については [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) を参照。
