#!/usr/bin/env python3
"""Bubbli の共有URLから6面を落とし、Equirectangular の360度 JPEG にする。"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from io import BytesIO
from pathlib import Path

import numpy as np
import py360convert
from PIL import Image

CDN = "https://d39cwcjmzdw2iw.cloudfront.net/{sphere_id}/stitched_{face}.jpg"
API = "https://v1.api.bubblicorp.com/bubble/{sphere_id}"
USER_AGENT = "Mozilla/5.0 (compatible; bubbli-rescue/1.0)"
XMP_NAMESPACE = b"http://ns.adobe.com/xap/1.0/\x00"
EXIF_HEADER = b"Exif\x00\x00"

# ImageMagick の -rotate は時計回り。
# ROTATE_270 が時計回り 90度、ROTATE_90 が反時計回り 90度。
# 対応は https://gist.github.com/smj10j/80e8437a6a4184c0cc0dbdd8aa8b6ff3
# py360convert の面は F R B L U D（前 右 後 左 上 下）。
FACE_SPEC: dict[str, tuple[str, Image.Transpose | None]] = {
    "F": ("px", Image.Transpose.ROTATE_270),
    "R": ("py", Image.Transpose.ROTATE_180),
    "B": ("nx", Image.Transpose.ROTATE_90),
    "L": ("ny", None),
    "U": ("pz", Image.Transpose.ROTATE_270),
    "D": ("nz", Image.Transpose.ROTATE_270),
}


class DownloadError(Exception):
    pass


def parse_sphere_id(value: str) -> str:
    text = value.strip()
    match = re.search(r"bubb\.li/([A-Za-z0-9]+)", text)
    if match:
        return match.group(1)
    bare = text.strip("/")
    if re.fullmatch(r"[A-Za-z0-9]+", bare):
        return bare
    raise SystemExit(f"共有URLから ID を取り出せませんでした: {value}")


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raise DownloadError(f"{exc.code} {url}") from exc
    except urllib.error.URLError as exc:
        raise DownloadError(f"{url} ({exc.reason})") from exc
    if data.startswith(b"\x1f\x8b"):
        data = gzip.decompress(data)
    if not data.startswith(b"\xff\xd8"):
        raise DownloadError(f"JPEG ではありません: {url} ({content_type})")
    return data


def fetch_face(sphere_id: str, face: str) -> bytes:
    url = CDN.format(sphere_id=sphere_id, face=face)
    try:
        return download(url)
    except DownloadError:
        return download(url + "?origin=http:on.bubb.licss")


def fetch_captured(sphere_id: str) -> datetime | None:
    """共有ページが表示する撮影日時。API の captured は UNIX 秒。"""
    url = API.format(sphere_id=sphere_id)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, UnicodeError) as exc:
        print(f"撮影日を取得できませんでした: {exc}", flush=True)
        return None
    captured = payload.get("captured")
    if not isinstance(captured, (int, float)):
        print("撮影日が共有情報にありません", flush=True)
        return None
    return datetime.fromtimestamp(int(captured)).astimezone()


def orient(image: Image.Image, turn: Image.Transpose | None) -> Image.Image:
    rgb = image.convert("RGB")
    if turn is None:
        return rgb
    return rgb.transpose(turn)


def to_equirect(faces: dict[str, np.ndarray], *, mirror: bool) -> Image.Image:
    sample = next(iter(faces.values()))
    face_h, face_w = sample.shape[:2]
    if face_h != face_w:
        raise SystemExit(f"立方体の面が正方形ではありません: {face_w}x{face_h}")
    for key, array in faces.items():
        if array.shape != sample.shape:
            raise SystemExit(f"{key} のサイズが他の面と違います: {array.shape} / {sample.shape}")
    equirect = py360convert.c2e(
        faces,
        h=face_w * 2,
        w=face_w * 4,
        mode="bicubic",
        cube_format="dict",
    )
    equirect = np.clip(equirect, 0, 255).astype(np.uint8)
    image = Image.fromarray(equirect, mode="RGB")
    if mirror:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return image


def xmp_datetime(when: datetime) -> str:
    return when.isoformat(timespec="seconds")


def gpano_xmp(width: int, height: int, captured: datetime | None = None) -> bytes:
    date_tags = ""
    date_xmlns = ""
    if captured is not None:
        date_xmlns = (
            "\n    xmlns:xmp='http://ns.adobe.com/xap/1.0/'"
            "\n    xmlns:photoshop='http://ns.adobe.com/photoshop/1.0/'"
        )
        created = xmp_datetime(captured)
        date_tags = (
            f"   <xmp:CreateDate>{created}</xmp:CreateDate>\n"
            f"   <photoshop:DateCreated>{created}</photoshop:DateCreated>\n"
        )
    packet = (
        "<?xpacket begin='\ufeff' id='W5M0MpCehiHzreSzNTczkc9d'?>\n"
        "<x:xmpmeta xmlns:x='adobe:ns:meta/'>\n"
        " <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>\n"
        "  <rdf:Description rdf:about=''\n"
        "    xmlns:GPano='http://ns.google.com/photos/1.0/panorama/'"
        f"{date_xmlns}>\n"
        "   <GPano:UsePanoramaViewer>True</GPano:UsePanoramaViewer>\n"
        "   <GPano:ProjectionType>equirectangular</GPano:ProjectionType>\n"
        "   <GPano:CroppedAreaLeftPixels>0</GPano:CroppedAreaLeftPixels>\n"
        "   <GPano:CroppedAreaTopPixels>0</GPano:CroppedAreaTopPixels>\n"
        f"   <GPano:CroppedAreaImageWidthPixels>{width}</GPano:CroppedAreaImageWidthPixels>\n"
        f"   <GPano:CroppedAreaImageHeightPixels>{height}</GPano:CroppedAreaImageHeightPixels>\n"
        f"   <GPano:FullPanoWidthPixels>{width}</GPano:FullPanoWidthPixels>\n"
        f"   <GPano:FullPanoHeightPixels>{height}</GPano:FullPanoHeightPixels>\n"
        f"{date_tags}"
        "  </rdf:Description>\n"
        " </rdf:RDF>\n"
        "</x:xmpmeta>\n"
        "<?xpacket end='w'?>\n"
    )
    return packet.encode("utf-8")


def exif_offset(when: datetime) -> str:
    offset = when.strftime("%z")
    return f"{offset[:3]}:{offset[3:]}"


def exif_payload(when: datetime) -> bytes:
    text = when.strftime("%Y:%m:%d %H:%M:%S")
    offset = exif_offset(when)
    exif = Image.Exif()
    exif[0x0132] = text
    ifd = exif.get_ifd(0x8769)
    ifd[0x9003] = text
    ifd[0x9004] = text
    ifd[0x9010] = offset
    ifd[0x9011] = offset
    ifd[0x9012] = offset
    return exif.tobytes()


def app1_segment(payload: bytes) -> bytes:
    segment_length = len(payload) + 2
    if segment_length > 0xFFFF:
        raise ValueError("APP1 が JPEG セグメントに収まりません")
    return b"\xff\xe1" + segment_length.to_bytes(2, "big") + payload


def find_app1(jpeg: bytes, key: bytes) -> tuple[int, int] | None:
    if not jpeg.startswith(b"\xff\xd8"):
        return None
    index = 2
    while index + 4 <= len(jpeg):
        if jpeg[index] != 0xFF:
            return None
        marker = jpeg[index + 1]
        if marker in (0xDA, 0xD9):
            return None
        length = int.from_bytes(jpeg[index + 2 : index + 4], "big")
        if length < 2 or index + 2 + length > len(jpeg):
            return None
        body = jpeg[index + 4 : index + 2 + length]
        end = index + 2 + length
        if marker == 0xE1 and body.startswith(key):
            return index, end
        index = end
    return None


def upsert_app1(jpeg: bytes, payload: bytes, key: bytes) -> bytes:
    if not jpeg.startswith(b"\xff\xd8"):
        raise ValueError("JPEG ではありません")
    segment = app1_segment(payload)
    span = find_app1(jpeg, key)
    if span is None:
        return jpeg[:2] + segment + jpeg[2:]
    start, end = span
    return jpeg[:start] + segment + jpeg[end:]


def read_xmp(jpeg: bytes) -> str | None:
    span = find_app1(jpeg, XMP_NAMESPACE)
    if span is None:
        return None
    start, end = span
    body = jpeg[start + 4 : end]
    return body[len(XMP_NAMESPACE) :].decode("utf-8", errors="replace")


def read_datetime_original(jpeg: bytes) -> str | None:
    with Image.open(BytesIO(jpeg)) as image:
        original = image.getexif().get_ifd(0x8769).get(0x9003)
    if original is None:
        return None
    return str(original)


def write_metadata(jpeg: bytes, width: int, height: int, captured: datetime | None) -> bytes:
    jpeg = upsert_app1(jpeg, XMP_NAMESPACE + gpano_xmp(width, height, captured), XMP_NAMESPACE)
    if captured is not None:
        jpeg = upsert_app1(jpeg, exif_payload(captured), EXIF_HEADER)
    return jpeg


def apply_file_times(path: Path, when: datetime) -> None:
    """変更日を撮影日時に合わせる。macOS では Finder の作成日も合わせる。"""
    timestamp = when.timestamp()
    os.utime(path, (timestamp, timestamp))
    if shutil.which("SetFile") is None:
        return
    stamp = when.strftime("%m/%d/%Y %H:%M:%S")
    result = subprocess.run(
        ["SetFile", "-d", stamp, "-m", stamp, str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        print(f"Finder の作成日は合わせられませんでした: {detail}", flush=True)


def write_jpeg(path: Path, jpeg: bytes, captured: datetime | None) -> None:
    """別ファイルに書いてから置き換える。同じ実体の日付だけ変えると作成日が戻る。"""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(jpeg)
    os.chmod(temporary, 0o644)
    if captured is not None:
        apply_file_times(temporary, captured)
    temporary.replace(path)


def save_equirect(image: Image.Image, path: Path, captured: datetime | None) -> None:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=95, subsampling=0)
    jpeg = write_metadata(buffer.getvalue(), *image.size, captured)
    written = read_xmp(jpeg)
    if written is None or "equirectangular" not in written:
        raise SystemExit(f"XMP を書き戻せませんでした: {path}")
    if captured is not None and read_datetime_original(jpeg) != captured.strftime("%Y:%m:%d %H:%M:%S"):
        raise SystemExit(f"撮影日を書き戻せませんでした: {path}")
    write_jpeg(path, jpeg, captured)


def convert(url: str, out_root: Path, *, mirror: bool) -> Path:
    sphere_id = parse_sphere_id(url)
    dest = out_root / sphere_id
    faces_dir = dest / "faces"
    faces_dir.mkdir(parents=True, exist_ok=True)

    oriented: dict[str, np.ndarray] = {}
    for key, (face, turn) in FACE_SPEC.items():
        raw_path = faces_dir / f"stitched_{face}.jpg"
        print(f"download stitched_{face}.jpg", flush=True)
        raw = fetch_face(sphere_id, face)
        raw_path.write_bytes(raw)
        with Image.open(raw_path) as image:
            turned = orient(image, turn)
        oriented[key] = np.asarray(turned)

    print("convert equirectangular", flush=True)
    equirect = to_equirect(oriented, mirror=mirror)
    captured = fetch_captured(sphere_id)
    output = dest / "equirect.jpg"
    save_equirect(equirect, output, captured)
    when = captured.isoformat(timespec="seconds") if captured else "なし"
    print(f"wrote {output} ({equirect.size[0]}x{equirect.size[1]}) captured={when}", flush=True)
    return output


def stamp_dates(out_root: Path, sphere_id: str | None = None) -> None:
    if sphere_id is None:
        targets = sorted(path for path in out_root.glob("*/equirect.jpg") if path.is_file())
    else:
        targets = [out_root / sphere_id / "equirect.jpg"]
    if not targets:
        raise SystemExit(f"equirect.jpg がありません: {out_root}")
    for path in targets:
        if not path.is_file():
            raise SystemExit(f"equirect.jpg がありません: {path}")
        captured = fetch_captured(path.parent.name)
        if captured is None:
            print(f"skip {path.parent.name}", flush=True)
            continue
        jpeg = path.read_bytes()
        with Image.open(BytesIO(jpeg)) as image:
            size = image.size
        jpeg = write_metadata(jpeg, *size, captured)
        if read_datetime_original(jpeg) != captured.strftime("%Y:%m:%d %H:%M:%S"):
            raise SystemExit(f"撮影日を書き戻せませんでした: {path}")
        write_jpeg(path, jpeg, captured)
        print(f"stamped {path.parent.name} {captured.isoformat(timespec='seconds')}", flush=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Bubbli の共有URLを Equirectangular JPEG にする")
    parser.add_argument("url", nargs="?", help="https://on.bubb.li/<id>/ または sphere ID")
    parser.add_argument(
        "--stamp-dates",
        action="store_true",
        help="変換はせず、既存の equirect.jpg に共有ページの撮影日を書く",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "out",
        help="出力先の親ディレクトリ（既定: スクリプトと同じ場所の out）",
    )
    parser.add_argument(
        "--mirror",
        action="store_true",
        help="左右を反転してから保存する",
    )
    args = parser.parse_args(argv)
    if args.stamp_dates:
        sphere_id = parse_sphere_id(args.url) if args.url else None
        stamp_dates(args.out, sphere_id)
        return
    if not args.url:
        parser.error("共有URLを指定するか、--stamp-dates を使ってください")
    try:
        convert(args.url, args.out, mirror=args.mirror)
    except DownloadError as exc:
        raise SystemExit(f"ダウンロードに失敗しました: {exc}") from exc


if __name__ == "__main__":
    main(sys.argv[1:])
