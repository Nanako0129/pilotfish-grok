# pilotfish-grok

> Grok Build 原生的多模型編排層，靈感來自
> [pilotfish](https://github.com/Nanako0129/pilotfish)。

**pilotfish-grok** 是 Pilotfish 編排在 Grok Build 上的獨立適配線。它保留機器設定、角色綁定、無模型名政策的三層分離，並把 lifecycle 與能力邊界翻成 Grok 原生 agents / roles。品質靠明確批准閘與 fresh-context 驗證，而不是每一步都用最強模型。

全部安裝在全域 `~/.grok/`：設定一次，所有專案生效。

原始架構歸功於 [@Nanako0129](https://github.com/Nanako0129) 的 pilotfish。七角色宿主移植形態參考 [pilotfish-codex](https://github.com/miyago9267/pilotfish-codex)。

[English](./README.md)

## 為什麼

coding session 的 token 多半花在搜尋、機械編輯、測試與文件，不是架構判斷。Pilotfish 把大量工作丟給 leaf 角色，主 session 保留規劃、批准與最終判斷。

在目前的 Grok Build 上，帳號可能只有單一 frontier 模型。此時 pilotfish-grok 仍然有用：

- 保護主 session context（偵察與 bulk 工作在 child session）
- 依角色分層 **reasoning effort**
- 對命名角色強制 **capability mode**（`read-only` / `execute` / `all`）
- 非平凡結果要求 fresh `verifier`

之後若目錄出現較便宜模型，只需在 `[subagents.models]` 釘選，不必改政策文字。

## 運作方式

三層，都在 `~/.grok/`：

| 層 | 檔案 | 職責 |
|---|---|---|
| **機器** | `config.toml` | 啟用 subagents；可選 model pin；主模型仍由你控制 |
| **角色** | `agents/*.md` + `roles/*.toml` | 七個契約 + capability + effort |
| **政策** | `rules/pilotfish-grok.md` | 何時委派、委派給誰 |

### 七個 Grok 角色

| 角色 | Capability | Effort | 時機 |
|---|---|---|---|
| `scout` | read-only | low | 廣或窄的唯讀 discovery |
| `plan-verifier` | read-only | medium | Plan 就緒；`READY` / `REVISE` |
| `security-reviewer` | read-only | high | 批准前資安證據 |
| `mech-executor` | all | low | 完整規格的機械工作 |
| `executor` | all | medium | 需要判斷的功能與修復 |
| `verifier` | execute | medium | 結果挑戰；`CONFIRMED` / `REFUTED` |
| `security-executor` | all | high | 已批准的資安實作 |

> **不安裝 Claude 專用的 `Explore` 覆寫。** Pilotfish 用該名 shadow Claude Code 內建 agent；Grok 不需要。discovery 由 `scout` 負責。內建 `explore` 仍可用。

## 安裝

> 需要 Grok Build **0.2.106 或更新**。

建議先 clone 再在該目錄啟動 Grok：

```sh
git clone https://github.com/Nanako0129/pilotfish-grok.git
cd pilotfish-grok
grok
```

貼上：

```text
Read the local file install/AGENT-INSTALL.md in the current checkout and follow it to install pilotfish-grok into my global Grok Build configuration.
Show me the full plan of changes and get my approval before writing anything.
```

Agent 會先 preflight、出示合併計畫，等你批准才寫入。安裝可重跑（冪等升級）。

## 會寫入什麼

| 目標 | 變更 |
|---|---|
| `~/.grok/config.toml` | 確保 subagents 啟用；預設不改主模型 |
| `~/.grok/agents/` | 七個 markdown agent |
| `~/.grok/roles/` | 七個 TOML role（capability + effort） |
| `~/.grok/rules/pilotfish-grok.md` | `pilotfish-grok` 標記區塊內的編排政策 |

**不會改 `~/.claude/`。** 若已裝 Claude pilotfish，installer 會警告 Grok Claude 相容層可能雙載入。

## 限制（v1.0）

- 測的是靜態模板契約，尚未自動化 live spawn e2e
- 父 session plan mode 不擋子代理寫入——唯讀靠 role capability
- 單一模型目錄沒有多模型價差套利；effort 與 context 節省仍成立

## 授權

MIT。見 [LICENSE](./LICENSE)。
