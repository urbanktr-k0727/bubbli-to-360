# bubbli-to-360

Bubbli は終わってしまったサービスです。共有URLが残っていれば、まだ360度写真として取り出せます。URLを1つ渡すと、Google フォトなどで部屋の中を見回せるJPEGが1枚できます。写真は自分のパソコンに保存されるだけで、外には送られません。

## 準備

Python 3.10 以降が必要です。ターミナルで `python3 --version` と打って、3.10 以上と出れば大丈夫です。

このリポジトリを取得します。

```bash
git clone https://github.com/urbanktr-k0727/bubbli-to-360.git
cd bubbli-to-360
```

はじめて使うときだけ、次を上から順に実行します。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows では、2行目を `.venv\Scripts\activate` に読み替えてください。

## 変換する

Bubbli の共有URLを、そのまま渡します。

```bash
python convert_bubbli.py "https://on.bubb.li/ここにID/"
```

終わると `out/ここにID/equirect.jpg` ができます。これが360度写真です。変換前の6枚は、同じ場所の `faces` フォルダに残してあります。

プレビューや Google フォトで開くと、パノラマとして扱われます。共有ページに撮影日が残っていれば、その日時も写真の情報に入ります。時刻は、このパソコンのタイムゾーンに合わせています。

Mac の Finder で「作成日」を見ると、iCloud や Synology Drive のような同期フォルダでは、保存した日に戻ってしまうことがあります。撮影日を確認するときは、写真の情報にある Exif を見てください。

## うまくいかないとき

共有ページが「Loading...」のままでも、変換できることが多いです。失敗したときは、次の2つがまだ開くかを確認してください。

- 画像は `https://d39cwcjmzdw2iw.cloudfront.net/共有ID/stitched_px.jpg` のような6枚です。名前の末尾は `px` `nx` `py` `ny` `pz` `nz` です
- 撮影日は `https://v1.api.bubblicorp.com/bubble/共有ID` にあります

どちらも消えていると、このツールでは取り出せません。

## English

Bubbli has shut down. If you still have a share URL, this tool can turn it into one 360° JPEG that Google Photos and other panorama viewers can open. The pictures stay on your computer. Nothing is uploaded.

You need Python 3.10 or newer. Check with `python3 --version`.

```bash
git clone https://github.com/urbanktr-k0727/bubbli-to-360.git
cd bubbli-to-360
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python convert_bubbli.py "https://on.bubb.li/YOUR_ID/"
```

On Windows, use `.venv\Scripts\activate` instead of `source .venv/bin/activate`.

The finished photo is `out/YOUR_ID/equirect.jpg`. The original six cube faces remain in `out/YOUR_ID/faces/`.

The JPEG is marked as an equirectangular panorama. If the share page still has a capture time, that time is written into the photo's Exif, using your computer's timezone. On a Mac, Finder's created date can snap back to today when the file is in a synced folder such as iCloud. For the day the photo was taken, read the Exif date.

The share page can sit on "Loading..." and still convert. If it fails, check that these are still online:

- the six images, for example `https://d39cwcjmzdw2iw.cloudfront.net/YOUR_ID/stitched_px.jpg` (`px`, `nx`, `py`, `ny`, `pz`, `nz`)
- the capture time at `https://v1.api.bubblicorp.com/bubble/YOUR_ID`

If both are gone, this tool cannot recover the photo.
