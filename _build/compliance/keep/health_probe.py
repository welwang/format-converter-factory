#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""電腦健康檢查的實機驗證殼（不經 UI，直接走產品的引擎路徑）。

用法：
    python health_probe.py inventory           # 只跑第一階段（硬體盤點，PowerShell）
    python health_probe.py parts               # 逐項探測最容易壞的 Windows 專屬部分
    python health_probe.py full [standard|pro] # 完整跑一次（等同 app.health_check → engine → run）

輸出：每一段都印出 PASS／FAIL、耗時、以及完整錯誤（traceback），
      完整的報告文字也會印出來（就像使用者第一次跑會看到的東西）。
"""
import json
import os
import sys
import time
import traceback

REPO = r"E:\四維八德"
SRC = os.path.join(REPO, "_build", "src")
VENDOR = os.path.join(REPO, "_build", "vendor")
for path in (SRC, VENDOR):
    if path not in sys.path:
        sys.path.insert(0, path)

OUT_DIR = os.path.join(os.environ.get("TEMP", REPO), "swbd-health-probe")


def banner(text):
    print("\n" + "=" * 72)
    print(text)
    print("=" * 72, flush=True)


def show(label, fn):
    """跑一個小探測，印出結果或完整錯誤。"""
    t0 = time.time()
    try:
        value = fn()
        dt = time.time() - t0
        text = json.dumps(value, ensure_ascii=False, default=str)
        print("  [PASS] %-34s %5.2fs  %s" % (label, dt, text[:400]))
        return True, value
    except Exception as exc:                                  # noqa: BLE001
        dt = time.time() - t0
        print("  [FAIL] %-34s %5.2fs  %s: %s" % (label, dt, type(exc).__name__, exc))
        traceback.print_exc()
        return False, None


def cmd_inventory():
    import health_check as HC
    banner("第一階段：硬體盤點（PS_INVENTORY，單次 PowerShell）")
    ok, inv = show("HC.inventory()", HC.inventory)
    if ok and isinstance(inv, dict):
        print("\n  盤點到的欄位（%d 個）：" % len(inv))
        for key in sorted(inv):
            value = inv[key]
            if isinstance(value, list):
                detail = "%d 筆" % len(value)
            elif isinstance(value, dict):
                detail = "{%s}" % ", ".join(sorted(value)[:6])
            else:
                detail = str(value)[:70]
            print("    %-28s %s" % (key, detail))
        errors = {k: v for k, v in inv.items() if k.endswith("_error")}
        if errors:
            print("\n  盤點內部的錯誤（PowerShell 每一段都被 try/catch 包住）：")
            for k, v in errors.items():
                print("    %-28s %s" % (k, str(v)[:160]))
    return 0 if ok else 1


def cmd_parts():
    import health_check as HC
    banner("逐項探測：Windows 專屬的部分")
    results = []
    results.append(show("HC._cpu_name()（winreg）", HC._cpu_name)[0])
    results.append(show("HC.available_mb()（kernel32）", HC.available_mb)[0])
    results.append(show("HC._top_processes()（PowerShell，用真實盤點）",
                        lambda: HC._top_processes(HC.inventory(), 1))[0])
    results.append(show("HC.battery_report()（powercfg）",
                        lambda: HC.battery_report(OUT_DIR))[0])
    results.append(show("HC._icmp 對外 8.8.8.8", lambda: HC._icmp("8.8.8.8", 2, lambda: False))[0])
    results.append(show("HC._tcp 對 1.1.1.1:443", lambda: HC._tcp("1.1.1.1", 443, 2, lambda: False))[0])
    results.append(show("HC._cpu_round()（CPU 暖身）", HC._cpu_round)[0])
    print("\n  小計：%d/%d 通過" % (sum(1 for r in results if r), len(results)))
    return 0 if all(results) else 1


def cmd_full(mode="standard"):
    import engine as E
    import health_check as HC

    banner("完整流程：app.health_check → engine._run_job → health_check.run（模式 %s）" % mode)
    os.makedirs(OUT_DIR, exist_ok=True)
    E.base_dir = lambda: REPO
    # 這一支是「產品外的」測試殼：engine 在 import 時就解析 FFMPEG，這裡補上，
    # 否則 detect_hw() 會因為 FFMPEG=None 而測不到硬體編碼器（會產生假的「無編碼器」結論）。
    if not getattr(E, "FFMPEG", None):
        cand = os.path.join(REPO, "tools", "ffmpeg.exe")
        if os.path.isfile(cand):
            E.FFMPEG = cand
            print("  測試殼補上 E.FFMPEG = %s" % cand)
    eng = E.Engine(1, light=1)
    try:
        o = HC.options({"mode": mode, "network": True})
        o.update(resource_mode="quiet", out_dir=OUT_DIR)
        print("  選項：%s" % json.dumps(o, ensure_ascii=False, default=str)[:400])
        job = E.Job(["電腦健康檢查"], "health_check", o, tool="health_check")
        job.state = "running"
        t0 = time.time()
        try:
            HC.run(eng, job)
            elapsed = time.time() - t0
            print("\n  [完成] 耗時 %.1fs  state=%s  cancelled=%s" %
                  (elapsed, getattr(job, "state", "?"), getattr(job, "cancelled", "?")))
            print("  msg=%r  encoder=%r  validation=%r" %
                  (getattr(job, "msg", ""), getattr(job, "encoder", ""), getattr(job, "validation", "")))
            print("  output=%r" % getattr(job, "output", ""))
            out = getattr(job, "output", "")
            if out and os.path.isfile(out):
                print("\n  ---- 報告文字（使用者第一次跑會看到的）----")
                with open(out, encoding="utf-8", errors="replace") as fh:
                    print(fh.read())
                js = os.path.splitext(out)[0] + ".json"
                if os.path.isfile(js):
                    data = json.load(open(js, encoding="utf-8"))
                    print("\n  ---- JSON 摘要 ----")
                    for key in ("mode", "mode_name", "created", "title", "lead"):
                        if key in data:
                            print("    %-14s %s" % (key, str(data[key])[:100]))
                    items = data.get("items") or []
                    print("    項目 %d 個：" % len(items))
                    for it in items:
                        print("      %-10s %-8s %s" % (it.get("name", "?"), it.get("state", "?"),
                                                       str(it.get("headline", ""))[:70]))
            else:
                print("\n  [警告] 沒有產生報告檔案")
            return 0
        except Exception:                                      # noqa: BLE001
            print("\n  [FAIL] 完整流程失敗，耗時 %.1fs" % (time.time() - t0))
            traceback.print_exc()
            return 1
    finally:
        try:
            eng.shutdown()
        except Exception:                                      # noqa: BLE001
            pass


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "inventory"
    if what == "inventory":
        sys.exit(cmd_inventory())
    if what == "parts":
        sys.exit(cmd_parts())
    if what == "full":
        sys.exit(cmd_full(sys.argv[2] if len(sys.argv) > 2 else "standard"))
    print(__doc__)
    sys.exit(2)
