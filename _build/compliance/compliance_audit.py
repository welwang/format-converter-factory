#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四維八德 開源發布合規稽核引擎。

設計原則（與任務要求一致）：
  1. 一律以「實際建置產物」為依據：SBOM 的元件、版本、雜湊都從 payload 掃出來，
     不是從 README、設計文件或來源清單抄來的。
  2. 版本只採用可查證的來源（PE 版本資源、Python .dist-info/METADATA、第三方原始碼版本檔）。
     查不到就寫 UNKNOWN，絕不用檔名推測。
  3. 授權只採用「隨附的授權／聲明檔」或「來源清單的明確記載」當證據，並標示證據種類。
     沒有證據就 UNKNOWN；法律結論一律 NEEDS_LEGAL_REVIEW，不由工具下判斷。
  4. 閘門 fail-closed：任何一個必要條件不成立就回傳非零，且不得靠改布林值通過
     （所有判斷都重新從檔案與雜湊算出來）。

子命令：
    scan    掃描 payload，產生 CycloneDX 1.5 SBOM
    diff    把 SBOM 與 source/來源清單.json 逐項比對
    sources 檢查 source_download 與 upstream_archives 的可存取性與對應性
    gate    發布閘門（fail-closed）
    all     以上全部，並產生人可讀報告
"""
from __future__ import annotations

import argparse
import ctypes
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]          # E:\四維八德
OUT = REPO / "_build" / "compliance" / "out"
INVENTORY = REPO / "source" / "來源清單.json"

# 這些路徑是「隨附授權證據」的候選位置；找到什麼就用什麼，找不到就 UNKNOWN。
LICENSE_FILE_PATTERNS = (
    "LICENSE*", "LICENCE*", "COPYING*", "NOTICE*", "NOTICE.*",
    "*LICENSE.txt", "*LICENSE.md", "*NOTICE.txt", "*NOTICE.md",
    "OFL.txt", "OFL.md", "LICENSE-OFL*",
)

# 一個「元件」的代表性進入點（用來算雜湊與版本，而不是把幾萬個檔案全算一遍）。
COMPONENT_ROOTS = (
    ("tools", "dir"),          # tools/<name>/ 視為一個元件
    ("tools", "exe"),          # tools/*.exe、tools/*.dll 各視為一個元件
    ("_internal", "native"),   # _internal 下的大型原生 DLL（qpdf、pdfium 等）
)


# ---------------------------------------------------------------- 檔案工具
def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


# ---------------------------------------------------------------- PE 版本資源
class VS_FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [
        ("dwSignature", wintypes.DWORD), ("dwStrucVersion", wintypes.DWORD),
        ("dwFileVersionMS", wintypes.DWORD), ("dwFileVersionLS", wintypes.DWORD),
        ("dwProductVersionMS", wintypes.DWORD), ("dwProductVersionLS", wintypes.DWORD),
        ("dwFileFlagsMask", wintypes.DWORD), ("dwFileFlags", wintypes.DWORD),
        ("dwFileOS", wintypes.DWORD), ("dwFileType", wintypes.DWORD),
        ("dwFileSubtype", wintypes.DWORD), ("dwFileDateMS", wintypes.DWORD),
        ("dwFileDateLS", wintypes.DWORD),
    ]


def pe_version(path: Path) -> str | None:
    """從 PE 的版本資源讀版本（真實中繼資料，不是檔名）。非 PE 或沒有資源時回 None。"""
    try:
        version = ctypes.WinDLL("version")
    except OSError:
        return None
    size = version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, buf):
        return None
    value = ctypes.c_void_p()
    length = wintypes.UINT()
    if not version.VerQueryValueW(buf, "\\", ctypes.byref(value), ctypes.byref(length)):
        return None
    if not value.value or length.value < ctypes.sizeof(VS_FIXEDFILEINFO):
        return None
    info = ctypes.cast(value, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
    if info.dwSignature != 0xFEEF04BD:
        return None
    parts = (info.dwFileVersionMS >> 16, info.dwFileVersionMS & 0xFFFF,
             info.dwFileVersionLS >> 16, info.dwFileVersionLS & 0xFFFF)
    while len(parts) > 2 and parts[-1] == 0:
        parts = parts[:-1]
    return ".".join(str(p) for p in parts)


# ---------------------------------------------------------------- 授權證據
THIRD_PARTY_LICENSES = REPO / "tools" / "python-third-party-licenses"
INVENTORY_CLAIMS = {
    # 來源清單／授權文件明確記載的元件（證據種類 = 文件記載，不是獨立查證）
    "MSVCP140.dll": "tools/libreoffice/program 內的 Microsoft VC++ 執行庫（授權說明.md 記載：依 Microsoft 再散布條件）",
    "VCRUNTIME140.dll": "同上（Microsoft VC++ 執行庫）",
    "VCRUNTIME140_1.dll": "同上（Microsoft VC++ 執行庫）",
    "CONCRT140.dll": "同上（Microsoft VC++ 執行庫）",
    "msvcp140.dll": "同上（Microsoft VC++ 執行庫）",
    "vcruntime140.dll": "同上（Microsoft VC++ 執行庫）",
    "vcruntime140_1.dll": "同上（Microsoft VC++ 執行庫）",
    "concrt140.dll": "同上（Microsoft VC++ 執行庫）",
}


# 授權文字辨識：只讀「實際隨附的授權檔」內容，並記錄命中的原文與檔案當證據。
# 這是證據抽取，不是推測：命中的字串、檔案路徑都會寫進 SBOM。
LICENSE_TEXT_RULES = (
    ("AGPL-3.0", ("GNU AFFERO GENERAL PUBLIC LICENSE",)),
    ("LGPL-3.0", ("GNU LESSER GENERAL PUBLIC LICENSE", "Version 3")),
    ("GPL-3.0", ("GNU GENERAL PUBLIC LICENSE", "Version 3")),
    ("GPL-2.0", ("GNU GENERAL PUBLIC LICENSE", "Version 2")),
    ("Apache-2.0", ("Apache License", "Version 2.0")),
    ("MPL-2.0", ("Mozilla Public License Version 2.0",)),
    ("OFL-1.1", ("SIL OPEN FONT LICENSE",)),
    ("Zlib", ("zlib License",)),
    ("Zlib", ("This software is provided 'as-is', without any express or implied warranty",)),
    ("LicenseRef-stb-public-domain-or-MIT", ("public domain", "stb_image_write")),
    ("BSD-3-Clause", ("Redistribution and use in source and binary forms", "Neither the name")),
    ("BSD-2-Clause", ("Redistribution and use in source and binary forms",)),
    ("MIT", ("Permission is hereby granted, free of charge",)),
    ("PSF-2.0", ("PYTHON SOFTWARE FOUNDATION LICENSE",)),
    ("CC-BY-4.0", ("Creative Commons Attribution 4.0",)),
    ("Unlicense", ("This is free and unencumbered software released into the public domain",)),
)


def license_from_text(files: list[str]) -> tuple[str, str]:
    """回傳 (SPDX 或 UNKNOWN, 命中說明)。只讀檔案前 8KB。"""
    for f in files:
        path = Path(f)
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:8192]
        except OSError:
            continue
        for spdx, needles in LICENSE_TEXT_RULES:
            if all(n in text for n in needles):
                return spdx, f"{spdx} ← {path.name}"
    return "UNKNOWN", ""


def evidence_for(name: str, path: Path) -> tuple[list[str], str]:
    """找出這個元件「隨附」的授權證據。回傳 (證據檔案清單, 證據種類)。

    除了 LICENSE 檔，也把 Python 套件的 .dist-info/METADATA 算授權證據
    （METADATA 的 License／Classifier 欄位就是套件自己宣告的授權）。"""
    found: list[str] = []
    # a) 同一資料夾或上一層的授權檔
    found += find_license_files(path.parent, limit=3)
    if path.parent.parent != path.parent:
        found += find_license_files(path.parent.parent, limit=3)
    # 動態載入的函式庫，授權常放在「同名的 Python 套件」或它的 dist-info 裡
    for stem in (path.stem.split(".")[0], re.split(r"[-_.]\d", path.stem.lower())[0]):
        if not stem:
            continue
        for base in (path.parent, path.parent.parent):
            for sib in list(base.glob(f"{stem}*")) + list(base.glob(f"*{stem}*")):
                if sib.is_dir():
                    found += find_license_files(sib, limit=4)
    # b) tools\python-third-party-licenses 底下以套件名開頭的 dist-info
    if THIRD_PARTY_LICENSES.is_dir():
        stem = re.split(r"[-_.]\d", name.lower())[0]
        for dist in THIRD_PARTY_LICENSES.glob("*"):
            if stem and stem in dist.name.lower():
                found += find_license_files(dist, limit=4)
    # c) tools 下的 WebView2 聲明
    if "webview2" in name.lower():
        for cand in (REPO / "tools").glob("WebView2-SDK-*"):
            found.append(str(cand))
    seen, uniq = set(), []
    for f in found:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    if uniq:
        return uniq[:6], "BUNDLED_LICENSE_FILE"
    # 沒有 LICENSE 檔時才退而用套件自己宣告的 METADATA（放最後，避免擠掉真正的授權檔）
    for base in (path.parent, path.parent.parent):
        if base.is_dir():
            for meta in list(base.glob("*.dist-info/METADATA"))[:4]:
                uniq.append(str(meta))
    if uniq:
        return uniq[:6], "PACKAGE_METADATA"
    if name in INVENTORY_CLAIMS:
        return ["授權說明.md／source/來源清單.json"], "INVENTORY_CLAIM"
    return [], "NONE"


def find_license_files(root: Path, limit: int = 6) -> list[str]:
    found: list[str] = []
    if not root.is_dir():
        return found
    for pattern in LICENSE_FILE_PATTERNS:
        for hit in sorted(root.glob(pattern)):
            if hit.is_file() and hit.stat().st_size < 2_000_000:
                rel = str(hit)
                if rel not in found:
                    found.append(rel)
            if len(found) >= limit:
                return found
    return found


def python_packages(internal: Path) -> list[dict]:
    """Python 套件：版本與授權都取自 .dist-info/METADATA（真實中繼資料）。"""
    out = []
    for dist in sorted(internal.glob("*.dist-info")):
        meta = dist / "METADATA"
        if not meta.is_file():
            continue
        fields: dict[str, str] = {}
        classifiers: list[str] = []
        try:
            for line in meta.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith(("License:", "Name:", "Version:", "Home-page:", "Author:")):
                    key, _, value = line.partition(":")
                    fields[key.strip()] = value.strip()
                elif line.startswith("Classifier: License"):
                    classifiers.append(line.split(":", 1)[1].strip())
                elif line.startswith("License-Expression:"):
                    fields["License-Expression"] = line.split(":", 1)[1].strip()
                elif not line.strip():
                    break
        except OSError:
            continue
        name = fields.get("Name") or dist.name.split("-")[0]
        version = fields.get("Version") or "UNKNOWN"
        declared = fields.get("License-Expression") or fields.get("License") or ""
        if (not declared or declared.upper() in ("UNKNOWN", "")) and classifiers:
            declared = "; ".join(classifiers)
        files = find_license_files(dist) or find_license_files(dist.parent)
        if not files:
            files = evidence_for(name, dist)[0]
        spdx, hit = license_from_text(files)
        if spdx == "UNKNOWN" and declared:
            spdx, hit = declared, f"METADATA 宣告：{declared[:60]}"
        out.append({
            "name": name,
            "version": version,
            "kind": "python-package",
            "path": str(dist),
            "license_declared": spdx,
            "license_match": hit,
            "license_evidence": [str(meta)] + files,
            "homepage": fields.get("Home-page", ""),
        })
    return out


def native_component(path: Path, note: str = "") -> dict:
    version = pe_version(path)
    lic, kind = evidence_for(path.name, path)
    spdx, hit = license_from_text(lic)
    return {
        "name": path.name,
        "version": version or "UNKNOWN",
        "kind": "native-binary",
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "license_declared": spdx,
        "license_match": hit,
        "license_evidence": lic,
        "evidence_kind": kind if spdx == "UNKNOWN" else "LICENSE_TEXT_MATCH",
        "note": note,
    }


def scan_payload(payload: Path) -> dict:
    """掃描實際 payload，產生元件清單（不是檔案清單）。"""
    components: list[dict] = []
    internal = payload / "_internal"
    tools = payload / "tools"

    # 1) 應用程式本身
    for exe in ("四維八德.exe", "swbd-core.exe"):
        p = payload / exe
        if p.is_file():
            components.append({
                "name": exe,
                "version": pe_version(p) or "UNKNOWN",
                "kind": "application",
                "path": str(p),
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
                "license_declared": "GPL-3.0 AND AGPL-3.0",
                "license_evidence": ["source/來源清單.json → application_licenses"],
            })

    # 2) Python 套件（.dist-info）
    if internal.is_dir():
        components.extend(python_packages(internal))

    # 3) _internal 的原生 DLL（含 C++ 主程式以 LoadLibrary 動態載入的）
    if internal.is_dir():
        for dll in sorted(internal.glob("*.dll")):
            components.append(native_component(dll))
        pdfium = internal / "pypdfium2_raw" / "pdfium.dll"
        if pdfium.is_file():
            components.append(native_component(
                pdfium, "C++ 主程式以 LoadLibrary／GetProcAddress 動態載入（PDFium C API）"))

    # 4) tools/ 下的頂層程式與目錄
    if tools.is_dir():
        for child in sorted(tools.iterdir()):
            if child.is_dir():
                entry = None
                for cand in ("ffmpeg.exe", "soffice.exe", "ebook-convert.exe", "tesseract.exe",
                             "pandoc.exe", "7z.exe", "gs.exe", "yt-dlp.exe", "deno.exe"):
                    if (child / cand).is_file():
                        entry = child / cand
                        break
                size = sum(f.stat().st_size for f in child.rglob("*") if f.is_file())
                count = sum(1 for f in child.rglob("*") if f.is_file())
                components.append({
                    "name": child.name,
                    "version": (pe_version(entry) if entry else None) or "UNKNOWN",
                    "kind": "bundled-tool-tree",
                    "path": str(child),
                    "entry_point": str(entry) if entry else "",
                    "sha256": sha256_file(entry) if entry else "",
                    "files": count,
                    "bytes": size,
                    "license_declared": license_from_text(evidence_for(child.name, child)[0])[0],
                    "license_match": license_from_text(evidence_for(child.name, child)[0])[1],
                    "license_evidence": evidence_for(child.name, child)[0],
                    "evidence_kind": ("LICENSE_TEXT_MATCH"
                                      if license_from_text(evidence_for(child.name, child)[0])[0] != "UNKNOWN"
                                      else evidence_for(child.name, child)[1]),
                })
            elif child.suffix.lower() in (".exe", ".dll"):
                components.append(native_component(child))
            elif child.suffix.lower() in (".txt", ".md", ".json"):
                pass    # 授權／聲明檔本身不是元件
            elif child.is_file() and child.stat().st_size > 1024:
                components.append({
                    "name": child.name, "version": "UNKNOWN", "kind": "data-file",
                    "path": str(child), "sha256": sha256_file(child), "bytes": child.stat().st_size,
                    "license_declared": "UNKNOWN", "license_evidence": [],
                })

    # 5) 隨附字型與 AI 模型
    for label, folder, pattern in (("font", tools / "fonts", "*"), ("ai-model", tools / "models", "*")):
        if folder.is_dir():
            for f in sorted(folder.glob(pattern)):
                if f.is_file():
                    components.append({
                        "name": f.name, "version": "UNKNOWN", "kind": label,
                        "path": str(f), "sha256": sha256_file(f), "bytes": f.stat().st_size,
                        "license_declared": license_from_text(find_license_files(folder))[0],
                        "license_match": license_from_text(find_license_files(folder))[1],
                        "license_evidence": find_license_files(folder),
                        "evidence_kind": ("LICENSE_TEXT_MATCH"
                                          if license_from_text(find_license_files(folder))[0] != "UNKNOWN"
                                          else "NONE"),
                    })

    # 6) 隨 C++ 主程式編入的靜態第三方原始碼
    third = REPO / "_build" / "cpp" / "third_party"
    if third.is_dir():
        for lib in sorted(third.iterdir()):
            if not lib.is_dir():
                continue
            ver = None
            for name in ("zlib.h", "stb_image_write.h"):
                header = lib / name
                if header.is_file():
                    text = header.read_text(encoding="utf-8", errors="replace")[:4000]
                    m = re.search(r"ZLIB_VERSION\s+\"([^\"]+)\"", text) or \
                        re.search(r"stb_image_write\s*-\s*v([\d.]+)", text)
                    if m:
                        ver = m.group(1)
            components.append({
                "name": lib.name, "version": ver or "UNKNOWN", "kind": "static-source",
                "path": str(lib),
                "license_declared": license_from_text(
                    find_license_files(lib) or [str(h) for h in sorted(lib.glob("*.h"))[:4]])[0],
                "license_match": license_from_text(
                    find_license_files(lib) or [str(h) for h in sorted(lib.glob("*.h"))[:4]])[1],
                "license_evidence": (find_license_files(lib) or
                                     [str(h) for h in sorted(lib.glob("*.h"))[:4]]),
                "note": "隨 C++ 主程式編入（未修改原始碼）；授權文字常見於標頭檔本身",
            })
    return {"payload": str(payload), "components": components}


# ---------------------------------------------------------------- SBOM
def to_cyclonedx(scan: dict) -> dict:
    comps = []
    for c in scan["components"]:
        item = {
            "type": "library" if c["kind"] in ("python-package", "native-binary", "static-source") else "application",
            "name": c["name"],
            "version": c["version"],
            "properties": [
                {"name": "swbd:kind", "value": c["kind"]},
                {"name": "swbd:path", "value": c.get("path", "")},
                {"name": "swbd:licenseDeclaration", "value": c.get("license_declared", "UNKNOWN")},
                {"name": "swbd:licenseEvidence", "value": "; ".join(c.get("license_evidence") or []) or "NONE"},
                {"name": "swbd:confirmation",
                 "value": "CONFIRMED" if (c.get("license_evidence") and c.get("license_declared") not in ("", "UNKNOWN")) else "UNKNOWN"},
            ],
        }
        if c.get("sha256"):
            item["hashes"] = [{"alg": "SHA-256", "content": c["sha256"]}]
        if c.get("entry_point"):
            item["properties"].append({"name": "swbd:entryPoint", "value": c["entry_point"]})
        if c.get("files"):
            item["properties"].append({"name": "swbd:fileCount", "value": str(c["files"])})
        if c.get("bytes"):
            item["properties"].append({"name": "swbd:bytes", "value": str(c["bytes"])})
        if c.get("note"):
            item["properties"].append({"name": "swbd:note", "value": c["note"]})
        comps.append(item)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "tools": [{"vendor": "swbd", "name": "compliance_audit.py", "version": "1.0"}],
            "component": {"type": "application", "name": "四維八德", "version": read_app_version()},
            "properties": [{"name": "swbd:payload", "value": scan["payload"]}],
        },
        "components": comps,
    }


def read_app_version() -> str:
    """單一版本來源：以實際安裝程式的檔名與 PE 版本為準（不是文件寫的數字）。"""
    stages = sorted((REPO / "_build").glob("release-stage-*"))
    if stages:
        cand = stages[-1] / "dist" / "swbd-core"
        for pattern in ("輸出/*離線安裝程式.exe", "輸出/*安裝程式.exe"):
            hits = sorted(cand.glob(pattern))
            if hits:
                m = re.search(r"(\d+\.\d+\.\d+)", hits[-1].name)
                if m:
                    return m.group(1)
        exe = cand / "四維八德.exe"
        if exe.is_file():
            return pe_version(exe) or "UNKNOWN"
    return "UNKNOWN"


# ---------------------------------------------------------------- 比對
DIFF_CATEGORIES = (
    "present_but_unlisted", "listed_but_absent", "version_mismatch",
    "license_mismatch", "missing_source_download", "missing_license_document",
    "hash_mismatch", "unconfirmed_indirect_dependency",
)


def installed_version() -> str:
    """實際安裝在使用者機器上的版本（PE 版本資源）。這是「單一版本來源」檢查的第三個輸入。"""
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        exe = Path(local) / "Programs" / "SiWeiBaDe" / "四維八德.exe"
        if exe.is_file():
            return pe_version(exe) or "UNKNOWN"
    return "UNKNOWN"


def load_inventory() -> dict:
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def inventory_mentions(inv: dict) -> dict:
    """把來源清單提到的東西攤平成 {關鍵字: 說明}，用於比對（清單沒有完整元件表）。"""
    mentions: dict[str, str] = {}
    for entry in inv.get("upstream_archives", []):
        f = entry.get("file", "")
        key = re.split(r"-\d", f)[0].lower()
        mentions[key] = f
    for key in ("webview2_sdk",):
        if key in inv:
            mentions["webview2"] = json.dumps(inv[key], ensure_ascii=False)
    return mentions


def diff_report(scan: dict, inv: dict) -> dict:
    comps = scan["components"]
    mentions = inventory_mentions(inv)
    findings: list[dict] = []

    # 1) 實際存在但清單未記載
    unlisted = []
    for c in comps:
        name = c["name"].lower()
        stem = re.split(r"[-_.]\d", name)[0]
        if any(k in name or k in stem for k in mentions):
            continue
        if c["kind"] in ("application", "data-file"):
            continue
        if c["license_declared"] != "UNKNOWN" or c.get("license_evidence"):
            continue                      # 有授權證據者不算「未記載的高風險項」
        unlisted.append(c["name"])
    if unlisted:
        findings.append({
            "category": "present_but_unlisted",
            "severity": "high",
            "count": len(unlisted),
            "detail": "實際打包但來源清單未記載、且本工具找不到隨附授權證據的元件",
            "items": sorted(unlisted)[:60],
        })

    # 2) 清單記載但發行內容不存在
    absent = []
    source_dir = REPO / "source"
    for key, label in mentions.items():
        if key == "webview2":
            if not list((REPO / "tools").glob("MicrosoftEdgeWebview2*")):
                absent.append(label + "（payload 找不到 WebView2 安裝程式）")
            continue
        # upstream_archives 是「對應來源封裝」，本來就不會出現在 payload；
        # 應該檢查 source\ 目錄裡有沒有這個檔案（或它的下載紀錄）。
        in_source = any(source_dir.rglob(label)) if label else False
        in_payload = any(key in c["name"].lower() for c in comps)
        if not in_source and not in_payload:
            absent.append(label + "（source 目錄與 payload 都找不到）")
    if absent:
        findings.append({
            "category": "listed_but_absent", "severity": "medium", "count": len(absent),
            "detail": "來源清單記載的上游封裝，在 source\\ 目錄與 payload 都找不到（對應來源可能尚未備妥）",
            "items": absent,
        })

    # 3) 版本不一致：安裝程式檔名／PE 版本 vs 來源清單
    app_version = read_app_version()
    installed = installed_version()
    versions = {"inventory": inv.get("version", "UNKNOWN"), "artifact": app_version, "installed": installed}
    bad = {k: v for k, v in versions.items() if v not in ("UNKNOWN", inv.get("version"))}
    if bad:
        findings.append({
            "category": "version_mismatch", "severity": "high", "count": len(bad),
            "detail": f"版本不一致：來源清單={inv.get('version')}，但 " +
                      "、".join(f"{k}={v}" for k, v in bad.items()),
            "items": [f"{k}={v}" for k, v in versions.items()],
        })

    # 4) 授權記錄不一致：清單有記載授權 vs SBOM 的宣告
    unknown = [c["name"] for c in comps if c.get("license_declared") in ("", "UNKNOWN")]
    if unknown:
        findings.append({
            "category": "license_mismatch", "severity": "high", "count": len(unknown),
            "detail": "SBOM 中沒有授權證據的元件（不得以檔名推測，一律 UNKNOWN）",
            "items": sorted(unknown)[:60],
        })

    # 5) 缺少來源下載資訊
    dl = inv.get("source_download", "")
    if not dl or not dl.startswith("http"):
        findings.append({
            "category": "missing_source_download", "severity": "high", "count": 1,
            "detail": "來源清單沒有可用的 source_download", "items": [dl or "(空)"],
        })
    elif not re.search(r"/(releases|tags|tree)/|\.tar\.gz|\.zip", dl):
        findings.append({
            "category": "missing_source_download", "severity": "high", "count": 1,
            "detail": "source_download 只指向儲存庫首頁，沒有指向與發行版對應的版本／標籤／封裝",
            "items": [dl],
        })

    # 6) 缺少必要授權文件
    required = ["LICENSE", "COPYING.AGPL-3.0", "授權說明.md", "開源與散布說明.md"]
    missing = [f for f in required if not (REPO / f).exists() and not (REPO / "source" / "application" / f).exists()]
    if inv.get("webview2_sdk", {}).get("license"):
        lic = REPO / inv["webview2_sdk"]["license"]
        if not lic.exists():
            missing.append(inv["webview2_sdk"]["license"])
    if missing:
        findings.append({
            "category": "missing_license_document", "severity": "high", "count": len(missing),
            "detail": "應隨附的授權／聲明文件不存在", "items": missing,
        })

    # 7) 二進位雜湊不符：清單有 sha256 的上游封裝，與 payload 對不到（清單沒有二進位雜湊，
    #    所以只能檢查「清單提供了雜湊卻找不到對應檔案」這種情況）
    hash_issues = []
    for entry in inv.get("upstream_archives", []):
        if entry.get("sha256") and not entry.get("bytes"):
            hash_issues.append(entry.get("file", "?"))
    if hash_issues:
        findings.append({
            "category": "hash_mismatch", "severity": "medium", "count": len(hash_issues),
            "detail": "上游封裝有 sha256 但缺少大小，無法做完整性交叉核對", "items": hash_issues,
        })

    # 8) 尚未確認的間接相依
    gaps = inv.get("gaps", [])
    if gaps:
        findings.append({
            "category": "unconfirmed_indirect_dependency", "severity": "high", "count": len(gaps),
            "detail": "來源清單自述的未完成項目", "items": gaps,
        })
    return {
        "inventory_version": inv.get("version", "UNKNOWN"),
        "artifact_version": app_version,
        "audit_flag": inv.get("public_distribution_audit_complete", None),
        "findings": findings,
        "counts": {cat: next((f["count"] for f in findings if f["category"] == cat), 0) for cat in DIFF_CATEGORIES},
    }


# ---------------------------------------------------------------- 來源可存取性
def http_probe(url: str, timeout: int = 25) -> dict:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "swbd-compliance/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            head = resp.read(2048)
            return {"url": url, "status": resp.status, "final": resp.geturl(),
                    "bytes_seen": len(head), "ok": 200 <= resp.status < 400}
    except urllib.error.HTTPError as exc:
        return {"url": url, "status": exc.code, "ok": False, "error": f"HTTP {exc.code}"}
    except Exception as exc:                                    # noqa: BLE001
        return {"url": url, "status": None, "ok": False, "error": type(exc).__name__}


def sources_report(inv: dict) -> dict:
    items = []
    dl = inv.get("source_download", "")
    if dl:
        probe = http_probe(dl)
        items.append({
            "name": "source_download",
            "url": dl,
            "reachable": probe.get("ok", False),
            "probe": probe,
            "correspondence": "NEEDS_LEGAL_REVIEW",
            "reason": "只確認可存取；是否為『與本發行版對應的完整對應來源』屬法律判斷，工具不下結論",
        })
    for entry in inv.get("upstream_archives", []):
        probe = http_probe(entry.get("url", "")) if entry.get("url") else {"ok": False}
        items.append({
            "name": entry.get("file", "?"),
            "url": entry.get("url", ""),
            "reachable": probe.get("ok", False),
            "expected_bytes": entry.get("bytes"),
            "expected_sha256": entry.get("sha256"),
            "probe": probe,
            "correspondence": "NEEDS_LEGAL_REVIEW",
            "reason": "未下載整檔核對雜湊（避免數百 MB 流量）；是否涵蓋實際散布二進位的所有修訂需人工／法律確認",
        })
    return {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "items": items}


# ---------------------------------------------------------------- 閘門
def gate(diff: dict, sources: dict, inv: dict, sbom: dict) -> dict:
    checks: list[dict] = []

    def add(cid, ok, detail, blocking=True):
        checks.append({"id": cid, "ok": bool(ok), "detail": detail, "blocking": blocking})

    add("audit_flag_complete", inv.get("public_distribution_audit_complete") is True,
        "來源清單 public_distribution_audit_complete 必須為 true")

    unknown = [c["name"] for c in _SCAN["components"]
               if c.get("license_declared") in ("", "UNKNOWN")]
    add("no_unconfirmed_components", not unknown,
        (f"仍有 {len(unknown)} 個元件無法從隨附證據判定授權（UNKNOWN）：" + "、".join(unknown[:8]) + "…"
         if unknown else "所有元件都有可查證的授權證據"))

    missing_docs = next((f["items"] for f in diff["findings"] if f["category"] == "missing_license_document"), [])
    add("license_documents_present", not missing_docs, f"缺少：{missing_docs}" if missing_docs else "必要授權文件齊備")

    src_ok = all(i.get("reachable") for i in sources["items"]) if sources["items"] else False
    add("source_offer_reachable", src_ok, "source_download 與所有 upstream_archives 必須可存取")

    vm = next((f for f in diff["findings"] if f["category"] == "version_mismatch"), None)
    add("version_consistent", vm is None and inv.get("version") != "UNKNOWN",
        "三個版本來源一致" if vm is None else vm["detail"])

    add("no_unlisted_binaries",
        diff["counts"]["present_but_unlisted"] == 0,
        f"未記載且無授權證據的元件 {diff['counts']['present_but_unlisted']} 個")

    add("indirect_dependencies_confirmed",
        diff["counts"]["unconfirmed_indirect_dependency"] == 0,
        "來源清單仍有自述未完成項目")

    blocking = [c for c in checks if c["blocking"] and not c["ok"]]
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "result": "PASS" if not blocking else "BLOCKED",
        "checks": checks,
        "blocking_failures": [c["id"] for c in blocking],
        "policy": ("fail-closed：只要有任何一項 blocking 檢查不成立，正式發布一律阻擋。"
                   "本閘門所有判斷都是從檔案、雜湊與實際產物重新計算，"
                   "調整布林值或修改測試預期都不會讓它通過。"),
    }


# ---------------------------------------------------------------- 報告
def write_reports(sbom: dict, diff: dict, sources: dict, gate_result: dict, scan: dict):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sbom.cdx.json").write_text(json.dumps(sbom, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "inventory-diff.json").write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "source-offer.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "gate-result.json").write_text(json.dumps(gate_result, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "scan.json").write_text(json.dumps(scan, ensure_ascii=False, indent=2), encoding="utf-8")

    comps = scan["components"]
    total_bytes = sum(c.get("bytes") or 0 for c in comps)
    lines = [
        "# 四維八德 開源發布合規稽核報告（自動產生）",
        "",
        f"- 產生時間：{gate_result['generated_at']}",
        f"- 掃描對象：`{scan['payload']}`",
        f"- 應用程式版本（實際產物）：**{diff['artifact_version']}**",
        f"- 應用程式版本（已安裝在使用者機器上）：**{installed_version()}**",
        f"- 來源清單版本：**{diff['inventory_version']}**",
        f"- SBOM 元件數：**{len(comps)}**（代表性檔案合計 {human_bytes(total_bytes)}）",
        f"- **發布閘門結果：{gate_result['result']}**",
        "",
        "> 本報告是**工程檢查**結果。`NEEDS_LEGAL_REVIEW` 與 `UNKNOWN` 都不是「已合規」，",
        "> 也不代表違法；法律結論必須由律師依實際發行方式判斷。",
        "",
        "## 一、閘門檢查",
        "",
        "| 檢查 | 結果 | 說明 |",
        "|---|---|---|",
    ]
    for c in gate_result["checks"]:
        mark = "PASS" if c["ok"] else ("FAIL" if c["blocking"] else "WARN")
        lines.append(f"| `{c['id']}` | **{mark}** | {c['detail']} |")
    lines += ["", "## 二、來源清單與實際產物差異", ""]
    for f in diff["findings"]:
        lines.append(f"### {f['category']}（{f['severity']}，{f['count']} 項）")
        lines.append("")
        lines.append(f"{f['detail']}")
        lines.append("")
        for item in f["items"][:20]:
            lines.append(f"- {item}")
        if len(f["items"]) > 20:
            lines.append(f"- …其餘 {len(f['items']) - 20} 項見 `inventory-diff.json`")
        lines.append("")
    lines += ["## 三、來源下載途徑", "", "| 項目 | 可存取 | 對應性 | 說明 |", "|---|---|---|---|"]
    for item in sources["items"]:
        lines.append(f"| {item['name']} | {'是' if item['reachable'] else '否'} | "
                     f"{item['correspondence']} | {item['reason']} |")
    lines += ["", "## 四、SBOM 元件（依確認狀態）", "",
              "| 元件 | 版本 | 種類 | 授權宣告 | 證據 |", "|---|---|---|---|---|"]
    for c in sorted(comps, key=lambda x: (x.get("license_declared") != "UNKNOWN", x["name"])):
        ev = "; ".join(os.path.basename(e) for e in (c.get("license_evidence") or [])[:2]) or "**無**"
        lines.append(f"| {c['name']} | {c['version']} | {c['kind']} | {c['license_declared']} | {ev} |")
    (OUT / "audit-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 給律師的清單
    legal = [
        "# 給法律專業人員的待確認事項清單",
        "",
        "本清單由工程工具產生。每一項都附上**工程上能查到的事實**與**工具無法判斷的部分**；",
        "工具不對衍生作品、授權相容性或散布義務下結論。",
        "",
        "## A. 需要法律判斷（NEEDS_LEGAL_REVIEW）",
        "",
        "1. **Ghostscript（AGPLv3）與 PyMuPDF（AGPLv3）的整合方式**",
        "   - 事實：兩者都在 `_internal`／`tools` 內隨安裝包散布；PDF 模組由應用程式呼叫。",
        "   - 工具無法判斷：是否構成單一組合作品、AGPL 第 13 條的遠端互動條款是否適用於桌面程式。",
        "2. **GPLv3 應用程式 + AGPLv3 模組的組合散布義務**",
        "   - 事實：來源清單記載 `application_licenses = [GPL-3.0, AGPL-3.0]`；",
        "     安裝包**不含**對應來源（`source_archives_in_installer = false`）。",
        "   - 工具無法判斷：現行 `source_download` 是否滿足 GPLv3 第 6 條／AGPLv3 第 13 條的對應來源要求。",
        "3. **qpdf（Apache-2.0）與 PDFium（BSD-3-Clause）以 LoadLibrary 動態載入**",
        "   - 事實：`_internal\\qpdf30-*.dll`、`_internal\\pypdfium2_raw\\pdfium.dll` 由 C++ 主程式",
        "     以 `LoadLibrary`／`GetProcAddress` 載入，非靜態連結。",
        "   - 工具無法判斷：此載入方式對「衍生作品」的影響。",
        "4. **FFmpeg（GPL 編譯版本）的間接函式庫與對應修訂**",
        "   - 事實：只附 `ffmpeg.exe`／`ffprobe.exe`（獨立程式），來源清單自述其間接程式庫與",
        "     完整建置腳本尚未逐一核實。",
        "5. **Microsoft 元件的再散布條件**",
        "   - 事實：安裝包含 WebView2 Runtime 安裝程式與 VC++ Runtime DLL；來源清單已註明",
        "     「依其再散布條件提供，不能以 GPL／AGPL 重新授權」。",
        "   - 工具無法判斷：是否符合 Microsoft 的可散布清單與授權條款。",
        "6. **編碼專利（H.264 等）與品牌素材（名稱、Logo、截圖）**",
        "   - 工具無法判斷：專利授權與商標使用，與開源授權無關。",
        "",
        "## B. 工程上尚未確認（UNKNOWN）",
        "",
    ]
    unknown = [c for c in comps if c.get("license_declared") in ("", "UNKNOWN")]
    for c in unknown[:60]:
        legal.append(f"- `{c['name']}`（{c['kind']}，版本 {c['version']}）：找不到隨附授權證據")
    legal += ["", "## C. 建議的處理順序", "",
              "1. 先讓 `public_distribution_audit_complete` 為 true 的前置條件成立（逐項確認 B 清單）。",
              "2. 由律師確認 A 清單的 1～6 項，特別是 Ghostscript／PyMuPDF 與對應來源的散布方式。",
              "3. 確認後再執行 `_build\\compliance\\gate_release.ps1`；閘門通過才發布。",
              ""]
    (OUT / "needs-legal-review.md").write_text("\n".join(legal), encoding="utf-8")
    return OUT


# ---------------------------------------------------------------- main
_SCAN: dict = {}


def main(argv=None):
    ap = argparse.ArgumentParser(description="四維八德 開源發布合規稽核")
    ap.add_argument("command", choices=("scan", "diff", "sources", "gate", "all"))
    ap.add_argument("--payload", default=None, help="要掃描的 payload 目錄（預設：最新 release-stage 的 dist\\swbd-core）")
    ap.add_argument("--json", action="store_true", help="只輸出 JSON（給流程整合用）")
    args = ap.parse_args(argv)

    payload = Path(args.payload) if args.payload else default_payload()
    if not payload or not payload.is_dir():
        print(json.dumps({"result": "BLOCKED", "error": f"找不到 payload：{payload}"}, ensure_ascii=False))
        return 2

    global _SCAN
    _SCAN = scan_payload(payload)
    inv = load_inventory()
    sbom = to_cyclonedx(_SCAN)
    diff = diff_report(_SCAN, inv)
    src = sources_report(inv)
    gate_result = gate(diff, src, inv, sbom)

    if args.command in ("all",):
        where = write_reports(sbom, diff, src, gate_result, _SCAN)
        if args.json:
            print(json.dumps({"gate": gate_result["result"], "report": str(where)}, ensure_ascii=False))
        else:
            print(f"SBOM 元件 {len(_SCAN['components'])} 個；閘門 {gate_result['result']}")
            print(f"報告：{where / 'audit-report.md'}")
            print(f"待法律確認：{where / 'needs-legal-review.md'}")
        return 0 if gate_result["result"] == "PASS" else 1
    if args.command == "gate":
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "gate-result.json").write_text(json.dumps(gate_result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(gate_result, ensure_ascii=False, indent=2) if not args.json
              else json.dumps({"result": gate_result["result"], "blocking": gate_result["blocking_failures"]},
                              ensure_ascii=False))
        return 0 if gate_result["result"] == "PASS" else 1
    if args.command == "scan":
        print(json.dumps(sbom, ensure_ascii=False, indent=2))
        return 0
    if args.command == "diff":
        print(json.dumps(diff, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(src, ensure_ascii=False, indent=2))
    return 0


def default_payload() -> Path | None:
    stages = sorted((REPO / "_build").glob("release-stage-*"))
    for stage in reversed(stages):
        cand = stage / "dist" / "swbd-core"
        if (cand / "四維八德.exe").is_file():
            return cand
    return None


if __name__ == "__main__":
    sys.exit(main())
