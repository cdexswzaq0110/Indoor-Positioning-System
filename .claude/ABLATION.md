# 常駐面消融紀錄

> **這份檔的用途只有一個**：想加一條常駐規則時，先回答 ——
>
> ## 「這條是因為模型反覆犯什麼錯才存在？」
>
> **答不出來就不准加。** 改寫成 skill 按需載入，或進 `.out-of-scope/`。

本檔不常駐。維護契約第 6 條的落地處。

## 加東西之前

判斷類型：

| 類型 | 是什麼 | 處置 |
|---|---|---|
| **補丁** | 修正模型的錯誤行為 | 每個模型大版本**重驗**，沒證據就刪 |
| **意圖** | 我的方法論、決策邊界、成長設計 | **不消融** |

判準：刪掉它，壞的是**模型的行為**還是**這套配置的目的**？

然後在下方分類表新增一列，填「失敗證據」。

## 消融流程（每個模型大版本或滿六個月）

1. `rules/` 暫時只留 `core-rules.md`
2. 跑三個最常做的任務
3. 只記**反覆出現**的同一種失敗（一次性失誤不算）
4. 一次加回一行，登記證據
5. 沒加回的不留

> **為什麼要這樣做**：常駐內容不是免費的。它每一輪都在花 token 與注意力，而且規則之間互相牴觸時模型會猶豫。更麻煩的是**補丁型規則有保存期限**——它為某個模型版本的行為而寫，模型換代後就從「修正」變成「多餘的約束」，但沒人會主動去刪一條看起來很有道理的規則。
>
> 沒有這個機制，常駐面只會單向長大：加規則感覺安全，刪規則感覺有風險。

## 機械化優先

一條常駐規則在被登記證據之前，先問一個更前面的問題：

**它能不能由 hook 強制？**

能就寫成 hook，常駐面砍掉那幾行。hook 是確定性的，模型配不配合都會執行；常駐文字是機率性的，而且每輪都在花 token。這是設計原則 2（確定性工程 × Agent）在 git 與 router 這一層的落地。

**判準一條**：判定條件寫得成 shell 的 → hook。需要語意理解的 → 留在 rules 或降級 skill。

| 原規則 | Hook | 觸發 | 模式 |
|---|---|---|---|
| `git-workflow.md` 先開分支 | `hooks/guard-branch.sh` | PreToolUse `Edit\|Write\|NotebookEdit` ＋ `Bash(git commit*)` | **warn**（exit 1，提示不阻擋） |
| `git-workflow.md` backup tag | `hooks/guard-critical.sh` | PreToolUse `Bash(git *)`，腳本自行判定 reset --hard／push --force／branch -D／rebase | **block**（exit 2） |
| 維護契約 #1 Router 不說謊 | `hooks/check-router.sh` | PreToolUse `Bash(git commit*)` | **block**（exit 2） |

**Gate 要先被證明會擋，才能相信它的綠燈**——hook 寫壞的預設失敗模式是靜默放行（見 [`../docs/lessons/0002-hook-silent-failure-windows.md`](../docs/lessons/0002-hook-silent-failure-windows.md)）。自測：

```bash
bash .claude/hooks/selftest.sh
```

22 條案例（含 3 個誤判陷阱），2026-08-31 全數通過。改動任一支 hook 後必須重跑。

**hook 不能取代規則文字的部分要留著**：hook 只回答「這一次擋不擋」，規則文字回答「為什麼」與「怎麼做才對」。已機械化的條目在下表標 `已機械化`，但仍保留最短的敘述句。

**Windows 注意**：hook 一律用 shell form（`shell: "bash"`）＋ `bash "<path>"`，**不要**用 exec form 直接指向 `.sh`。官方文件明示 Windows 的 exec form 需要真正的 `.exe`；而且 `bash` 在 Windows PATH 上會解析到 `C:\Windows\system32\bash.exe`（WSL launcher），不是 Git Bash。【已確認：2026-08-31 於本機 `Get-Command bash`】

## 分類現況

盤點日 2026-08-31（第一輪，hook 化已執行，實測消融尚未執行）。

常駐面 = 根目錄 `CLAUDE.md`(37) ＋ `.claude/CLAUDE.md`(38) ＋ `rules/*.md`(266) = **341 行**（2026-08-14 為 339）。

> ⚠ **這個數字偏高，而且有一半的規則沒有本地實證。** 第一輪消融的重點是 `evidence-grades`(47) 與
> `dispatch`(45)——它們是這套配置的核心賭注，但賭注要用實測驗證，不是用信心。
> 拿掉之後模型行為沒變差的，該降級成 Skill。

| 檔案 | 類型 | 失敗證據 | 下次處置 |
|---|---|---|---|
| 根目錄 `CLAUDE.md` 入口與節奏 | 意圖 | — | 保留（只放入口；長出細節就是該下放的訊號） |
| `.claude/CLAUDE.md` 元件責任 | 意圖 | — | 保留 |
| `.claude/CLAUDE.md` 維護契約 | 補丁 | router 說謊（索引沒同步）、frontmatter 指向已刪檔。**2026-08-31 實測命中**：根 `CLAUDE.md` 指向不存在的 `/se-bootstrap`【已確認：`check-router.sh` exit 2】 | 保留；#1 已機械化 |
| `core-rules.md` 1–5 | 意圖 | — | 保留（他檔以「第 N 條」引用，編號須穩定） |
| `core-rules.md` 6 留下領悟 | 意圖 | — | 保留（這是這套配置存在的理由） |
| `core-rules.md` 3 部分結果不覆蓋 | 補丁 | **未登記** | ⚠ 第一輪後重驗 |
| `evidence-grades.md` | 補丁 | **核心賭注**：模型把推論寫成事實，讀者無法從措辭分辨「我跑過」與「我覺得應該」 | 保留，但第一輪要量它有沒有真的改變行為 |
| `dispatch.md` 1 預設 Coroutine | 補丁 | 模型傾向為「分工感」派 subagent | ⚠ 重驗：base 提示可能已足夠 |
| `dispatch.md` 2 切片換 Process | 意圖 | — | 保留 |
| `dispatch.md` 3 平行前確認鎖 | 補丁 | 跨 session duplicate cherry-pick、stale branch | 保留 |
| `dispatch.md` 4 GIL | 補丁 | 一次丟多個問題給人，全部卡住 | ⚠ 本地未實證 |
| `git-workflow.md` 先開分支 | 補丁 | **已機械化（warn）**：`guard-branch.sh` 的攔截次數即為證據，2026-08-31 起觀察 | 一到兩週後：有攔截 → 改 block；零攔截 → 刪常駐文字，只留 hook |
| `git-workflow.md` backup tag | 補丁 | **已機械化（block）**：`guard-critical.sh`，13/13 判定案例通過【已確認：2026-08-31 stdin 測試】 | 保留最短敘述；hook 是真正的守門人 |
| `git-workflow.md` commit→push→PR 連貫 | 補丁 | base 提示預設「只在使用者要求時 push」，需覆寫 | 保留 |
| ~~`git-workflow.md` body 按需寫~~ | 補丁 | **已移除（2026-08-31）**：衝突對象不存在——全域檔名是 `~/.claude/CLAUDE.md.md`（副檔名重複），從未被載入【已確認：`ls -la ~/.claude/`】 | 存於 `.out-of-scope/ablated-2026-08-31/` |
| `thinking-boundary.md` 速通／深思 | 意圖 | — | 保留（擋過度前置治理） |
| `thinking-boundary.md` 預算 | 補丁 | **未登記** | ⚠ 第一輪後重驗 |
| `register.md` 文件語域 | 意圖 | — | 保留 |
| `register.md` 對話語域 | 意圖 | — | 保留 |

**⚠ 未登記 = 下次消融的第一批刪除候選。**

## 已知的張力（不是缺陷，是刻意保留的仲裁點）

| 張力 | 仲裁在哪 |
|---|---|
| `se-focus` 要 `file:line`，`register.md` 要「用動作講機制」 | `register.md`「何時不可以白話」第一條：使用者要定位時不白話 |
| `se-minimal-change` 要最短 diff，`core-rules` 4 要驗證證據 | 階梯本身：非平凡邏輯必須留一個可跑的檢查 |
| `dispatch.md` 要用滿並行，鎖規則要序列化 | 鎖優先。用滿的是**無衝突**的部分 |
| `thinking-boundary` 預算 vs `core-rules` 4 以證據宣告完成 | 預算用完不等於完成。停下來報告，不降低完成標準 |
| `se-ml-lifecycle` 的 Gate vs `thinking-boundary` 雛型期走 happy path | ML 的 Gate 是**驗證可信度**的閘，不是治理的閘。雛型可以省文件，不能省 split 正確性 |

## 沿革

| 日期 | 動作 | 結果 |
|---|---|---|
| 2026-08-14 | 建立基線。六條常駐規則、十六個 Skill、九個 Agent | 常駐面 339 行，尚未實測消融 |
| 2026-08-31 | 第一輪：三條規則機械化為 hook（guard-branch／guard-critical／check-router）、修正 `/se-bootstrap` 斷鏈、刪除「body 按需寫」、建立 `docs/eval/` 觸發案例集 | 常駐面 341 行（與本輪前持平：刪 1 條、hook 註記 0 新增行、契約 #1 註記 +1 行）；「未登記」由 4 條降為 2 條；**實測消融尚未執行**，排在 hook warn 期滿之後 |
| 2026-09-02 | 跑出第一個有效的 skill 觸發 baseline：A 組（4 個相鄰入口）**4/4、8 次全對、零誤觸發**。原本要改的四份 description **決定不動**——重疊是事實，誤觸發不是 | 前兩次量測作廢（案例不自足、答案外洩），見 `docs/lessons/0003` |
