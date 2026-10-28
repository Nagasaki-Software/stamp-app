"""記録の置き場所の名前（名前ロック・設定・ログ・レジストリ）。

社内版と公開版は鍵が違うため、同じ場所を使うと互いの名前ロックを「改ざん」と判断してしまう。
core/_secrets.py の DATA_NAME で分ける。書いていなければ従来どおり "StampApp"。
"""
try:
    from core._secrets import DATA_NAME
except ImportError:
    DATA_NAME = "StampApp"
