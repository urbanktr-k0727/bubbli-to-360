# bubbli-to-360

終了した Bubbli の共有URLを、360度写真（Equirectangular JPEG）にします。画像は自分のパソコンに保存されるだけで、どこかへ送りません。

## 使い方

Python 3.10 以上が必要です。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python convert_bubbli.py "https://on.bubb.li/共有ID/"
```

できたファイルは `out/<共有ID>/equirect.jpg` です。元の6枚は `out/<共有ID>/faces/` に残ります。

360度写真として開けるよう、`ProjectionType=equirectangular` を書き込みます。共有ページに撮影日が残っていれば、Exif の撮影日時にも入れます。時刻は、コマンドを実行したパソコンのタイムゾーンです。

macOS では Finder の作成日も撮影日に合わせます。クラウド同期のフォルダだと、作成日がファイルを保存した日に戻ることがあります。撮影日は Exif を見てください。

## 共有ページが止まったとき

画像は `https://d39cwcjmzdw2iw.cloudfront.net/<共有ID>/stitched_px.jpg` のような6枚（px, nx, py, ny, pz, nz）です。撮影日は `https://v1.api.bubblicorp.com/bubble/<共有ID>` の `captured` です。どちらも止まったら、このツールも動きません。

## English

```bash
python convert_bubbli.py "https://on.bubb.li/SHARE_ID/"
```

Writes `out/SHARE_ID/equirect.jpg`, marked as an equirectangular panorama. When the Bubbli API still has a capture time, it is stored in Exif using the computer's timezone.
