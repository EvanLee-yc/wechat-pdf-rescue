#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wx_extract_pdf.py —— 从微信小程序（Radium 运行时）的 webview HTTP 缓存中提取 PDF

适用场景：
  小程序内嵌 web-view / pdf.js 预览文档时，完整文件会走 webview 的 HTTP 缓存。
  即使前端只让你看前几页，完整文件往往已经落盘。本脚本直接从缓存里把 PDF 捞出来。

用法：
    python3 wx_extract_pdf.py                 # 扫描并提取
    python3 wx_extract_pdf.py -o ./output     # 指定输出目录

原理：
  WeChat 4.x 的小程序运行时叫 Radium，webview 使用 Chromium 的 Simple Cache 格式。
  缓存数据文件形如  Cache_Data/<hash>_0 ，内容 = [响应头][响应体]。
  PDF 响应体以 %PDF 开头、以 %%EOF 结尾，直接按这两个魔数切片即可还原原始文件。

作者备注：本工具仅用于提取已下发到你本机缓存中的文件，供个人归档。
"""

import argparse
import glob
import hashlib
import os
import re
import sys

__version__ = "1.0.0"

HOME = os.path.expanduser("~")

# 微信容器内可能的 webview 缓存位置（macOS）
CACHE_GLOBS = [
    # WeChat 4.x / Radium
    f"{HOME}/Library/Containers/com.tencent.xinWeChat/Data/Documents/app_data/radium/web/profiles/*/Cache/Cache_Data/*",
    f"{HOME}/Library/Containers/com.tencent.xinWeChat/Data/Documents/app_data/radium/web/profiles/*/IndexedDB/**/*",
    # 旧版 WeChat 3.x
    f"{HOME}/Library/Containers/com.tencent.xinWeChat/Data/Library/Caches/profiles/*/Cache/Cache_Data/*",
    # 通用兜底
    f"{HOME}/Library/Containers/com.tencent.xinWeChat/Data/Library/Caches/**/Cache_Data/*",
]

MAX_SCAN_BYTES = 200 * 1024 * 1024  # 单个文件超过 200MB 跳过


def find_pdf_payloads(blob: bytes):
    """从缓存块中切出 PDF 字节流。返回 [(offset, pdf_bytes), ...]"""
    results = []

    # 收集所有 %PDF 起点
    starts = []
    pos = 0
    while True:
        p = blob.find(b"%PDF", pos)
        if p < 0:
            break
        starts.append(p)
        pos = p + 4

    if not starts:
        return results

    # 收集所有 %%EOF 终点
    ends = []
    pos = 0
    while True:
        p = blob.find(b"%%EOF", pos)
        if p < 0:
            break
        e = p + len(b"%%EOF")
        while e < len(blob) and blob[e : e + 1] in (b"\n", b"\r"):
            e += 1
        ends.append(e)
        pos = e

    # 为每个起点配一个最近的、在其之后的终点
    for s in starts:
        cand = [e for e in ends if e > s]
        if not cand:
            continue
        e = cand[0]
        pdf = blob[s:e]
        # 体积下限，过滤噪声
        if len(pdf) > 1024:
            results.append((s, pdf))
    return results


def extract_source_url(blob: bytes, pdf_start: int) -> str:
    """从 %PDF 之前的响应头里提取原始 URL。"""
    head = blob[:pdf_start]
    # Chromium 缓存里 URL 常以 1/0/https://... 形式内联
    m = re.findall(rb"(https?://[^\x00-\x20\"'<>\\]{8,300})", head)
    if m:
        return m[-1].decode("utf-8", "replace")
    return "(未识别)"


def pdf_page_count(pdf: bytes):
    counts = [int(c) for c in re.findall(rb"/Count\s+(\d+)", pdf)]
    pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf))
    return max(counts) if counts else pages, pages


def main():
    ap = argparse.ArgumentParser(
        description="从微信小程序 webview HTTP 缓存中提取 PDF（macOS）"
    )
    ap.add_argument("-o", "--out", default="wx_extracted", help="输出目录")
    ap.add_argument("-V", "--version", action="version", version=__version__)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    candidates = []
    for g in CACHE_GLOBS:
        candidates.extend(glob.glob(g, recursive=True))
    candidates = [c for c in sorted(set(candidates)) if os.path.isfile(c)]

    print(f"扫描 {len(candidates)} 个缓存文件 …\n")

    found = 0
    seen_md5 = set()

    for path in candidates:
        try:
            if os.path.getsize(path) > MAX_SCAN_BYTES:
                continue
            with open(path, "rb") as f:
                blob = f.read()
        except OSError:
            continue

        if b"%PDF" not in blob:
            continue

        for offset, pdf in find_pdf_payloads(blob):
            md5 = hashlib.md5(pdf).hexdigest()
            if md5 in seen_md5:
                continue
            seen_md5.add(md5)

            url = extract_source_url(blob, offset)
            total, page_objs = pdf_page_count(pdf)

            base = "document"
            m = re.search(r"/([^/]+\.pdf)(?:\?|$)", url, re.I)
            if m:
                base = os.path.splitext(m.group(1))[0]
            else:
                m2 = re.search(r"/([^/?]+)(?:\?|$)", url)
                if m2:
                    base = m2.group(1)[:40]

            out_name = f"{base}.pdf"
            out_path = os.path.join(args.out, out_name)
            n = 1
            while os.path.exists(out_path):
                out_path = os.path.join(args.out, f"{base}_{n}.pdf")
                n += 1

            with open(out_path, "wb") as f:
                f.write(pdf)

            found += 1
            print(f"[{found}] {out_path}")
            print(f"    来源 URL : {url}")
            print(f"    大小     : {len(pdf):,} 字节")
            print(f"    页数     : /Count={total}  页对象={page_objs}")
            print(f"    MD5      : {md5}")
            print(f"    缓存位置 : {path}")
            print()

    if not found:
        print("未在缓存中找到 PDF。可能的原因：")
        print("  1. 未在微信中打开过该小程序的文档预览，或已清理过微信缓存；")
        print("  2. 终端缺少读取微信容器目录的权限（macOS 会静默拦截，不报错）。")
        print("     解决：系统设置 → 隐私与安全性 → 完全磁盘访问权限 →")
        print("     勾选你使用的终端 App（Terminal / iTerm），然后重启终端。")
        return 1

    print(f"完成，共提取 {found} 个文件到 {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
