# dues-agent — 會費對帳催繳專員（Agent 版）

同事拿到這包後：claude.ai/code 選這個 repo（或本機 `claude`）→ 說「秘書長的指示在 inbox，做本月催繳」→ 它對帳、分級、每人一封信、催繳名單、收據清單寫到 `outbox/` → 看完說「好，發下去」。

資料全部虛構；「北區科技產業協會」為虛構。

**demo 完要歸零**：`inbox/*.txt.done` 改回 `.txt`、清空 `outbox/`、`log/dues_log.md` 只留表頭。
