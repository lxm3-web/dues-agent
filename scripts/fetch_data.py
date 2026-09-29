#!/usr/bin/env python3
"""從公開的 Google Sheet 更新 data/ 的 CSV——G Drive 是資料來源，repo 內 CSV 只是備援快照。
抓不到（沒網路、環境擋 docs.google.com、表頭對不上）就沿用快照，照樣能跑。只用標準庫。
規則：只匯入本機檔已有的欄位；本機檔整欄留空的欄＝要 Agent 自己產出的結果欄，不匯入（避免 Sheet 上預填的答案洩給 Agent）。"""
import csv, io, os, sys, urllib.parse, urllib.request
SHEET_ID = "1yjmX5zgFrRigq0RCmylW3RH_2qeidRyG1TwumXS5mLQ"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
JOBS = [("會員名冊","會員名冊_2026.csv","會員編號"),("銀行入帳","銀行入帳明細_2026.csv","交易序號")]  # (分頁名, 本機檔, 必要表頭)
TRANSFORM = {}
def fetch(tab):
    u = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(tab)}"
    return list(csv.reader(io.StringIO(urllib.request.urlopen(u, timeout=15).read().decode("utf-8"))))
def merge(sheet, path):
    old = list(csv.reader(open(path, encoding="utf-8-sig")))
    want = old[0]
    skip = {h for j, h in enumerate(want) if not any(len(r) > j and r[j] for r in old[1:])}
    idx = {h: sheet[0].index(h) for h in want if h not in skip}
    return [want] + [[(r[idx[h]] if h in idx and idx[h] < len(r) else "") for h in want] for r in sheet[1:]]
for tab, local, key in JOBS:
    path = os.path.join(ROOT, "data", local)
    try:
        rows = fetch(tab)
        while rows and not any(rows[-1]): rows.pop()
        if not rows or key not in rows[0]: raise ValueError("表頭對不上")
        rows = TRANSFORM.get(tab, lambda r, p: r)(rows, path)
        rows = merge(rows, path) if os.path.exists(path) else rows
        crlf = "\r\n" if os.path.exists(path) and b"\r\n" in open(path, "rb").read(4000) else "\n"
        bom = os.path.exists(path) and open(path, "rb").read(3) == b"\xef\xbb\xbf"
        with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
            csv.writer(f, lineterminator=crlf).writerows(rows)
        print(f"{tab:<8} {len(rows)-1} 列（已從 Google Sheet 更新）→ data/{local}")
    except Exception as e:
        if os.path.exists(path): print(f"{tab:<8} 沿用快照（{e.__class__.__name__}: {e}）→ data/{local}")
        else: print(f"⚠️  {tab}：抓不到也沒有快照"); sys.exit(1)
