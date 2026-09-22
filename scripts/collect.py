import csv, re, os, datetime
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date(2026, 9, 20)
MONTH = "2026-09"
OUT = f"{BASE}/outbox"
LETTERS = f"{OUT}/{MONTH}_催繳信"
os.makedirs(LETTERS, exist_ok=True)
for f_ in os.listdir(LETTERS):          # 同月重跑：清掉上一輪自己產的信
    if f_.endswith(".md"):
        os.remove(os.path.join(LETTERS, f_))
STATUS_LINE = "> 狀態：待確認"

def norm(s):
    return re.sub(r"\s+", "", s).replace("股份有限公司", "").replace("有限公司", "")

def d(s):
    y, m, dd = s.split("/")
    return datetime.date(int(y), int(m), int(dd))

def fmt(n):
    return f"{int(n):,}"

members = list(csv.DictReader(open(f"{BASE}/data/會員名冊_2026.csv", encoding="utf-8-sig")))
pays = list(csv.DictReader(open(f"{BASE}/data/銀行入帳明細_2026.csv", encoding="utf-8-sig")))
for m in members:
    m["年費"] = int(m["年費"])
for p in pays:
    p["金額"] = int(p["金額"])

by_name = defaultdict(list)
for m in members:
    by_name[norm(m["公司名稱"])].append(m)
by_contact = defaultdict(list)
for m in members:
    by_contact[m["聯絡人"]].append(m)
by_pre2 = defaultdict(list)
for m in members:
    by_pre2[norm(m["公司名稱"])[:2]].append(m)

# ---------- 配對 ----------
matched = defaultdict(list)   # 會員編號 -> [(pay, 依據)]
unmatched = []                # (pay, 候選說明)
for p in pays:
    name = p["匯款人／帳戶名"]
    n = norm(name)
    amt = p["金額"]
    c1 = by_name.get(n, [])
    if len(c1) == 1:
        m = c1[0]
        matched[m["會員編號"]].append((p, f"公司名一致（{name}）"))
        continue
    if len(c1) > 1:
        c1f = [m for m in c1 if m["年費"] == amt]
        if len(c1f) == 1:
            m = c1f[0]
            matched[m["會員編號"]].append((p, f"公司名一致（{name}），名冊有 {len(c1)} 家同名（股份／有限），以金額＝年費區分"))
            continue
        unmatched.append((p, f"名冊有 {len(c1)} 家「{n}」只差股份／有限，年費相同，匯款人名分不出",
                          [f"{m['會員編號']} {m['公司名稱']}（年費 {fmt(m['年費'])}）" for m in c1]))
        continue
    c2 = [m for m in by_pre2.get(n[:2], []) if m["年費"] == amt]
    if len(c2) == 1:
        m = c2[0]
        matched[m["會員編號"]].append((p, f"前兩字「{n[:2]}」＋金額＝年費（匯款人 {name}）"))
        continue
    c3 = [m for m in by_contact.get(name, []) if m["年費"] == amt]
    if len(c3) == 1:
        m = c3[0]
        matched[m["會員編號"]].append((p, f"匯款人＝聯絡人 {name}＋金額＝年費"))
        continue
    # 對不上：找最接近候選
    cands = []
    if len(c2) > 1:
        cands = [f"{m['會員編號']} {m['公司名稱']}（年費 {fmt(m['年費'])}）" for m in c2]
        why = f"前兩字「{n[:2]}」有 {len(c2)} 家年費同為 {fmt(amt)}，無法唯一"
    elif "○" in name:
        first, last = name[0], name[-1]
        cc = [m for m in members if m["聯絡人"][0] == first and m["聯絡人"][-1] == last and m["年費"] == amt]
        cands = [f"{m['會員編號']} {m['公司名稱']}（聯絡人 {m['聯絡人']}）" for m in cc]
        why = "匯款人姓名遮罩，只能比首尾字＋金額"
    else:
        why = "名冊查無此公司／聯絡人"
    unmatched.append((p, why, cands))

# ---------- 狀態 / 級別 ----------
rows = []
for m in members:
    fee = m["年費"]
    ps = matched.get(m["會員編號"], [])
    total = sum(p["金額"] for p, _ in ps)
    basis = "；".join(f"{p['交易序號']} {p['入帳日期']} {fmt(p['金額'])}：{b}" for p, b in ps) or "無入帳"
    if not ps:
        status, diff = "未繳", fee
    elif total == fee:
        status, diff = "已繳", 0
    elif total < fee:
        status, diff = "短繳", fee - total
    else:
        status, diff = "重複繳", total - fee
    if len(ps) >= 2 and status != "重複繳":
        basis += f"（{len(ps)} 筆合計）"
    days = (TODAY - d(m["應繳期限"])).days
    if status in ("未繳", "短繳"):
        level = "未到期" if days <= 0 else "提醒" if days < 30 else "強調" if days < 60 else "警告"
    else:
        level = ""
    rows.append({**m, "入帳合計": total, "狀態": status, "差額": diff, "依據": basis,
                 "逾期天數": days if status in ("未繳", "短繳") else "", "級別": level, "筆數": len(ps)})

# ---------- 寫檔 ----------
def write_csv(path, header, data):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(STATUS_LINE + "\n")
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(data)

write_csv(f"{OUT}/{MONTH}_對帳結果.csv",
          ["會員編號", "公司名稱", "會員級別", "年費", "入帳合計", "狀態", "差額／多繳額", "依據", "逾期天數", "級別"],
          [[r["會員編號"], r["公司名稱"], r["會員級別"], r["年費"], r["入帳合計"], r["狀態"], r["差額"], r["依據"], r["逾期天數"], r["級別"]] for r in rows])

write_csv(f"{OUT}/{MONTH}_待人工確認.csv",
          ["交易序號", "入帳日期", "管道", "匯款人／帳戶名", "金額", "備註", "對不上原因", "最接近候選"],
          [[p["交易序號"], p["入帳日期"], p["管道"], p["匯款人／帳戶名"], p["金額"], p["備註"], why, " / ".join(c) or "無"] for p, why, c in unmatched])

write_csv(f"{OUT}/{MONTH}_收據清單.csv",
          ["會員編號", "公司名稱", "聯絡人", "年費", "入帳日期", "交易序號", "管道", "Email"],
          [[r["會員編號"], r["公司名稱"], r["聯絡人"], r["年費"],
            "；".join(p["入帳日期"] for p, _ in matched[r["會員編號"]]),
            "；".join(p["交易序號"] for p, _ in matched[r["會員編號"]]),
            "；".join(p["管道"] for p, _ in matched[r["會員編號"]]), r["Email"]]
           for r in rows if r["狀態"] == "已繳"])

# 待認領入帳的候選會員：這些人目前算未繳／短繳，但可能款項已進來，認領前不要寄
pending_claim = defaultdict(list)
for p_, why, cands in unmatched:
    for c in cands:
        mid = c.split()[0]
        pending_claim[mid].append(f"{p_['交易序號']} {p_['入帳日期']} {p_['匯款人／帳戶名']} NT$ {fmt(p_['金額'])}")

def claim_note(r):
    ts = pending_claim.get(r["會員編號"], [])
    return "；".join(ts) if ts else ""

LEVEL_ORDER = {"警告": 0, "強調": 1, "提醒": 2}
chase = [r for r in rows if r["狀態"] in ("未繳", "短繳") and r["級別"] in LEVEL_ORDER]
chase.sort(key=lambda r: (LEVEL_ORDER[r["級別"]], -r["年費"]))
dup = [r for r in rows if r["狀態"] == "重複繳"]

def action(r):
    if r["狀態"] == "重複繳":
        return f"通知多繳 NT$ {fmt(r['差額'])}，請會員選退款或抵明年"
    what = f"催繳 NT$ {fmt(r['差額'])}" if r["狀態"] == "未繳" else f"補繳差額 NT$ {fmt(r['差額'])}"
    via = {"Email": "寄信", "LINE": "LINE 傳信＋簡短訊息", "電話": "先電話、再補信"}[r["聯絡偏好"]]
    if r["級別"] == "警告":
        return f"{what}；{via}；說明 60 天以上將暫停權益"
    if r["級別"] == "強調":
        return f"{what}；{via}；請一週內完成"
    return f"{what}；{via}"

write_csv(f"{OUT}/{MONTH}_催繳名單.csv",
          ["優先", "會員編號", "公司名稱", "聯絡人", "職稱", "會員級別", "年費", "狀態", "應收金額", "應繳期限", "逾期天數", "級別", "聯絡偏好", "Email", "電話", "建議動作", "待認領入帳（先不要寄）", "信件檔"],
          [[i + 1, r["會員編號"], r["公司名稱"], r["聯絡人"], r["職稱"], r["會員級別"], r["年費"], r["狀態"], r["差額"],
            r["應繳期限"], r["逾期天數"], r["級別"] or "—", r["聯絡偏好"], r["Email"], r["電話"], action(r),
            claim_note(r) or "—",
            f"{MONTH}_催繳信/{r['會員編號']}_{r['公司名稱']}.md"]
           for i, r in enumerate(chase + dup)])

# ---------- 信件 ----------
REMIND_DUE = (TODAY + datetime.timedelta(days=14)).strftime("%Y/%m/%d")   # 2026/10/04
WARN_DUE = (TODAY + datetime.timedelta(days=10)).strftime("%Y/%m/%d")     # 2026/09/30

def letter(r):
    head = f"{r['公司名稱']} {r['聯絡人']}{r['職稱']}："
    fee = fmt(r["年費"])
    if r["狀態"] == "未繳":
        state = "目前尚未收到款項。"
    elif r["狀態"] == "短繳":
        state = f"目前收到 NT$ {fmt(r['入帳合計'])}，尚差 NT$ {fmt(r['差額'])}。"
    else:
        state = f"目前收到 {r['筆數']} 筆共 NT$ {fmt(r['入帳合計'])}，多繳 NT$ {fmt(r['差額'])}。"
    body = f"本年度會費 NT$ {fee}，繳費期限 {r['應繳期限']}。{state}"
    if r["狀態"] == "重複繳":
        ask = "多繳的部分可以退款，也可以直接抵明年會費，兩種都可以，請回覆告訴我們您方便的方式。"
    else:
        target = "補匯差額" if r["狀態"] == "短繳" else "匯款"
        if r["級別"] == "提醒":
            ask = f"方便的話，請於 {REMIND_DUE} 前{target}，若已經匯出請忽略這封信，感謝您。"
        elif r["級別"] == "強調":
            ask = f"目前已逾期 {r['逾期天數']} 天，麻煩請於一週內{target}，若有困難請隨時跟秘書處說一聲。"
        else:
            ask = f"目前已逾期 {r['逾期天數']} 天，依章程欠費滿 60 天會暫停活動報名與投票權益，請於 {WARN_DUE} 前{target}，有任何狀況都歡迎跟我們聯絡。"
    if r["狀態"] == "重複繳":
        tail = "收據會先依年費金額開立寄出，多繳部分等您回覆後處理。秘書處 小美 分機 12。"
    else:
        tail = "匯款後請回傳帳號後五碼，收據隨即寄出。秘書處 小美 分機 12。"
    return head, body, ask, tail

def cjk_len(s):
    return len(re.sub(r"[\s：。，、；（）\d,$NT/]", "", s))

lengths = []
for r in chase + dup:
    head, body, ask, tail = letter(r)
    tag = f"{r['狀態']}" + (f"／{r['級別']}" if r["級別"] else "")
    hold = claim_note(r)
    hold_line = f"> 先不要寄：有待認領入帳可能是本會員（{hold}），認領後這封要抽掉或改寫。\n" if hold else ""
    text = f"{STATUS_LINE}\n{hold_line}\n# {r['會員編號']} {r['公司名稱']}｜{tag}\n\n{head}\n\n{body}\n\n{ask}\n\n{tail}\n"
    with open(f"{LETTERS}/{r['會員編號']}_{r['公司名稱']}.md", "w", encoding="utf-8") as f:
        f.write(text)
    lengths.append((r["會員編號"], len(head + body + ask + tail)))

# ---------- 統計 ----------
cnt = {s: sum(1 for r in rows if r["狀態"] == s) for s in ("已繳", "短繳", "重複繳", "未繳")}
cnt["對不上"] = len(unmatched)
unpaid_total = sum(r["差額"] for r in rows if r["狀態"] in ("未繳", "短繳"))
over_total = sum(r["差額"] for r in dup)
lv = {l: [r for r in chase if r["級別"] == l] for l in ("警告", "強調", "提醒")}
unmatched_amt = sum(p["金額"] for p, _, _ in unmatched)
received = sum(r["入帳合計"] for r in rows)
paid_by_level = defaultdict(lambda: [0, 0])
for r in rows:
    paid_by_level[r["會員級別"]][1] += 1
    if r["狀態"] in ("已繳", "重複繳"):
        paid_by_level[r["會員級別"]][0] += 1
by_deadline = defaultdict(lambda: [0, 0])
for r in rows:
    by_deadline[r["應繳期限"]][1] += 1
    if r["狀態"] == "未繳":
        by_deadline[r["應繳期限"]][0] += 1

twins = [k for k, v in by_name.items() if len(v) > 1]
twin_names = "、".join(twins)
twin_cnt = sum(1 for p, why, c in unmatched if "只差股份" in why)
masked_names = "、".join(p["匯款人／帳戶名"] for p, why, c in unmatched if "遮罩" in why)
warn_630 = [r for r in lv["警告"] if r["應繳期限"] == "2026/06/30"]
warn_old = [r for r in lv["警告"] if r["應繳期限"] != "2026/06/30"]
old_names = "、".join(f"{r['會員編號']} {r['公司名稱']}" for r in warn_old)
top_warn = max(lv["警告"], key=lambda r: r["差額"])
short_min = min(r["差額"] for r in rows if r["狀態"] == "短繳")
short_max = max(r["差額"] for r in rows if r["狀態"] == "短繳")
short_dist = sorted(Counter(r["差額"] for r in rows if r["狀態"] == "短繳").items())
short_desc = "、".join(f"差 {fmt(v)} 有 {c} 家" for v, c in short_dist)
# 前兩字同族但配不出唯一對象的入帳
pre2_un = [(p_, why, c) for p_, why, c in unmatched if "前兩字" in why]
pre2_prefix = "、".join(sorted(set(p_["匯款人／帳戶名"] for p_, _, _ in pre2_un)))
pre2_family = sorted(set(norm(p_["匯款人／帳戶名"])[:2] for p_, _, _ in pre2_un))
pre2_family_desc = "、".join(f"名冊「{k}」開頭共 {len(by_pre2.get(k, []))} 家" for k in pre2_family)
# 金額對不上任一候選年費的入帳（不是純粹同名分不出）
odd_amt = [(p_, c) for p_, why, c in unmatched
           if "只差股份" in why and all(p_["金額"] != m["年費"] for m in by_name[norm(p_["匯款人／帳戶名"])])]
odd_amt_desc = "、".join(f"{p_['交易序號']} {p_['匯款人／帳戶名']} NT$ {fmt(p_['金額'])}" for p_, _ in odd_amt)

hold_rows = [r for r in chase + dup if claim_note(r)]
hold_tbl = "\n".join(f"| {r['會員編號']} | {r['公司名稱']} | {r['狀態']} | NT$ {fmt(r['差額'])} | {r['級別'] or '—'} | {claim_note(r)} |" for r in hold_rows) or "| — | 無 | — | — | — | — |"

def tbl(rs, cols):
    out = ["| " + " | ".join(c for c, _ in cols) + " |", "|" + "---|" * len(cols)]
    for r in rs:
        out.append("| " + " | ".join(str(f(r)) for _, f in cols) + " |")
    return "\n".join(out)

warn_tbl = tbl(lv["警告"], [("編號", lambda r: r["會員編號"]), ("公司", lambda r: r["公司名稱"]), ("級別", lambda r: r["會員級別"]),
                          ("狀態", lambda r: r["狀態"]), ("應收", lambda r: "NT$ " + fmt(r["差額"])), ("期限", lambda r: r["應繳期限"]),
                          ("逾期", lambda r: f"{r['逾期天數']} 天"), ("聯絡偏好", lambda r: r["聯絡偏好"])])
dup_tbl = tbl(dup, [("編號", lambda r: r["會員編號"]), ("公司", lambda r: r["公司名稱"]), ("年費", lambda r: fmt(r["年費"])),
                    ("入帳合計", lambda r: fmt(r["入帳合計"])), ("多繳", lambda r: "NT$ " + fmt(r["差額"])), ("依據", lambda r: r["依據"])])
short_tbl = tbl([r for r in rows if r["狀態"] == "短繳"],
                [("編號", lambda r: r["會員編號"]), ("公司", lambda r: r["公司名稱"]), ("年費", lambda r: fmt(r["年費"])),
                 ("已收", lambda r: fmt(r["入帳合計"])), ("尚差", lambda r: "NT$ " + fmt(r["差額"])), ("級別", lambda r: r["級別"])])
um_tbl = "\n".join(f"| {p['交易序號']} | {p['入帳日期']} | {p['匯款人／帳戶名']} | {fmt(p['金額'])} | {p['備註'] or '—'} | {why} | {' / '.join(c) or '無'} |"
                   for p, why, c in unmatched)
lvl_tbl = "\n".join(f"| {k} | {v[0]}/{v[1]} | {v[0] * 100 // v[1]}% |" for k, v in paid_by_level.items())
dl_tbl = "\n".join(f"| {k} | {v[0]}/{v[1]} |" for k, v in sorted(by_deadline.items()))

summary = f"""{STATUS_LINE}

# {MONTH} 會費催繳摘要

產出日期：{TODAY}｜資料：名冊 {len(members)} 家、入帳 {len(pays)} 筆｜依據秘書長 2026-09-20 指示

## 一、結論

120 家會員中 **{cnt['已繳']} 家已繳、{cnt['短繳']} 家短繳、{cnt['重複繳']} 家重複繳、{cnt['未繳']} 家未繳**；另有 **{cnt['對不上']} 筆入帳（NT$ {fmt(unmatched_amt)}）配不到人**。
未收會費合計 **NT$ {fmt(unpaid_total)}**（未繳＋短繳差額）。要催的 {len(chase)} 家裡，**警告級 {len(lv['警告'])} 家、強調級 {len(lv['強調'])} 家、提醒級 {len(lv['提醒'])} 家**。多繳待處理 NT$ {fmt(over_total)}。

| 狀態 | 家數 | 金額 |
|---|---|---|
| 已繳 | {cnt['已繳']} | 已入帳，開收據 |
| 短繳 | {cnt['短繳']} | 尚差 NT$ {fmt(sum(r['差額'] for r in rows if r['狀態'] == '短繳'))} |
| 重複繳 | {cnt['重複繳']} | 多繳 NT$ {fmt(over_total)} |
| 未繳 | {cnt['未繳']} | 應收 NT$ {fmt(sum(r['差額'] for r in rows if r['狀態'] == '未繳'))} |
| 對不上（入帳筆） | {cnt['對不上']} | NT$ {fmt(unmatched_amt)} 待人工認領 |

## 二、警告級（逾期 60 天以上，秘書長先看這批）

{warn_tbl}

## 三、短繳

{short_tbl}

## 四、重複繳

{dup_tbl}

## 五、對不上的入帳（待人工確認）

| 序號 | 日期 | 匯款人 | 金額 | 備註 | 原因 | 最接近候選 |
|---|---|---|---|---|---|---|
{um_tbl}

## 五之二、受待認領入帳影響的催繳對象（**先不要寄**）

這些人目前算未繳／短繳，但第五節有入帳可能就是他們的；認領後信要抽掉或改寫。

| 編號 | 公司 | 目前狀態 | 應收 | 級別 | 可能屬於他的入帳 |
|---|---|---|---|---|---|
{hold_tbl}

## 六、三個發現

1. **對不上的 {cnt['對不上']} 筆（NT$ {fmt(unmatched_amt)}）每筆都有候選，人工一比就能收掉。** 三種卡法：(a) 名冊有 {len(twins)} 組公司只差「股份」兩字（{twin_names}），銀行匯款人名分不出來，佔 {twin_cnt} 筆——建議秘書處查匯款帳號或直接問會員；(b) 匯款人姓名遮罩（{masked_names}），用首尾字＋金額都找到唯一候選；(c) 匯款人只寫共同前兩字（{pre2_prefix}，{len(pre2_un)} 筆），{pre2_family_desc}，同年費的分不出是哪一家。另外 {odd_amt_desc} 金額不等於候選任一家的年費，認領後多半還是短繳，要一併確認。收掉後未繳家數會再降，這批候選公司目前仍列未繳、也擬了信，**認領前先不要寄**。
2. **警告級 {len(lv['警告'])} 家分兩種。** {len(warn_630)} 家是 6/30 到期、逾期 82 天，權益暫停條款正要啟動，這批建議聯絡偏好是電話的先打電話；另外 {len(warn_old)} 家是 1/15、2/15 到期、逾期已超過 200 天（{old_names}），這種通常是去年就沒繳或已退會，建議先確認還在不在會，再決定要不要寄。金額最大的是 {top_warn['會員編號']} {top_warn['公司名稱']}（{top_warn['會員級別']}，NT$ {fmt(top_warn['差額'])}）。
3. **短繳 {cnt['短繳']} 家差額都在 NT$ {fmt(short_min)}～{fmt(short_max)}，不像故意不繳（{short_desc}）。** 小額像是手續費或匯費被扣，金額較大的像是分次匯或級別記錯；差額怎麼來的名冊與入帳看不出來，信裡只寫清楚尚差多少，不推測原因、不施壓。

## 七、各級別繳費率

| 會員級別 | 已繳（含多繳）／總數 | 繳費率 |
|---|---|---|
{lvl_tbl}

## 八、各期限未繳分布

| 應繳期限 | 未繳／該期總數 |
|---|---|
{dl_tbl}

## 九、我做了什麼假設（請秘書長確認）

- 抬頭用「聯絡人＋職稱」（例：羅雅欣副總），沒有猜先生／小姐。
- 提醒級信裡的「請於 X 前匯款」統一寫 {REMIND_DUE}（今天＋14 天）；範本的「期限＋14 天」對 8/31 到期的人已經過期，所以改用今天起算。
- 警告級信裡的處理期限寫 {WARN_DUE}（今天＋10 天）。
- 名冊裡「XX股份有限公司」與「XX有限公司」同時存在時，匯款人名去後綴後兩家都對得上；年費不同就用金額分（泰宇材料 6,000 vs 36,000），年費相同就不硬配，列待人工確認。
- 前兩字比對若有兩家以上候選，一律不硬配，列待人工確認。
- 對不上的 {cnt['對不上']} 筆入帳**沒有**算進任何人的入帳，所以候選公司目前仍列「未繳」並附了催繳信；人工認領後這幾封要抽掉。

## 十、下一步

1. 秘書長看第二節警告級 {len(lv['警告'])} 家與第五節對不上 {cnt['對不上']} 筆；第五之二的 {len(hold_rows)} 家在認領前先不要寄。
2. 小美依待人工確認清單打電話認領入帳，認領後跟我說「M0xx 是 TX20xx」，我更新對帳結果並抽掉那封信。
3. 秘書長說「發下去」，我把 outbox 標已確認、log 補記；實際寄信由秘書處按下去。
"""
with open(f"{OUT}/{MONTH}_摘要.md", "w", encoding="utf-8") as f:
    f.write(summary)

# ---------- log ----------
now = f'{TODAY} {datetime.datetime.now().strftime("%H:%M")}'   # 作業基準日固定 2026-09-20
if os.environ.get("WRITE_LOG"):
  with open(f"{BASE}/log/dues_log.md", "a", encoding="utf-8") as f:
    f.write(f"| {now} | {MONTH} | {len(members)}／{len(pays)} | {cnt['已繳']}／{cnt['短繳']}／{cnt['重複繳']}／{cnt['未繳']}／{cnt['對不上']} | NT$ {fmt(unpaid_total)} | {len(lv['警告'])} | outbox/{MONTH}_對帳結果.csv、待人工確認.csv、催繳名單.csv、收據清單.csv、催繳信/（{len(chase) + len(dup)} 封）、摘要.md | 未確認 |\n")

print(cnt, "未收", unpaid_total, "多繳", over_total, "對不上金額", unmatched_amt)
print({k: len(v) for k, v in lv.items()}, "信件數", len(chase) + len(dup))
print("信件字數範圍", min(l for _, l in lengths), max(l for _, l in lengths))
print("字數超界:", [(i, l) for i, l in lengths if l < 120 or l > 180])
