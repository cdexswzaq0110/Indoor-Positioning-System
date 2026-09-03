---
id: L0001
date: 2026-09-02
outcome: useful
tags: [preflight, 架構決策, windows, 雛型]
anchors:
  - CLAUDE.md
  - mobile/README.md
  - backend/app/config.py
supersedes:
hits: 0
---

# 前置檢查的價值不在「查有沒有」，在「查出來的東西會改架構」

## 觸發情境

新專案第一輪，還沒寫第一行程式碼。手上有一份使用者已經拍板的技術選擇。

## 領悟

`se-preflight` 很容易被當成裝機檢查——列一列有什麼 CLI、有沒有 GPU，然後就往下做。
這一輪的實際情況是：**兩個查出來的事實直接改掉了已經拍板的東西**，而且兩個都不是
「缺了裝一下就好」。

1. **Port 8000 已被別的程序佔用。**【已確認：`netstat -ano` 顯示 PID 52268 LISTENING】
   後端預設埠改成 8100。這件事本身很小，但它會擴散——手機端設定、前端連線、README、
   `admin/reload` 的範例指令全都要一致。**在寫 config 之前知道，跟在 debug 連不上時才知道，
   成本差一個量級。**

2. **這台機器沒有 Android SDK、沒有 adb、沒有 Flutter，只有 Java 17。**
   【已確認：`flutter`／`adb` command not found，`ANDROID_HOME` unset，`%LOCALAPPDATA%\Android\Sdk` 不存在】
   使用者選了「原生 App」。如果照字面直接開 `expo run:android`，會在建置階段才炸，
   而且炸在一個要裝好幾 GB SDK 才能解的地方。知道之後，路線改成
   **Expo Go 開發 + EAS 雲端建置出安裝檔**，本機完全不需要 Android SDK。
   使用者的選擇沒有被改，被改的是抵達那個選擇的路徑。

共同點：兩件事都**不是**「工具缺了，裝一下」。它們是**環境事實與計畫的衝突**，
而衝突只有在動工前發現才便宜。

## 為什麼會撞到

因為前置檢查跑在 Phase 3——在澄清之後、寫程式之前。順序是對的：
先問清楚要做什麼（所以知道要查手機工具鏈），再查環境（所以發現查不到）。

如果順序反過來，preflight 會變成漫無目的地列裝了什麼，
不會有人想到去查 `adb`——因為那時候還不知道要做原生 App。

## 下一輪怎麼用

- preflight 的產出要**寫進專案 `CLAUDE.md` 的「特有約束」段**，不要只留在對話裡。
  這一輪把 port 8100 與「沒有 Android SDK」兩條都寫進去了，因為它們違反模型預設行為
  （預設會用 8000、預設會假設能本機建置）。
- 查的項目要由**已澄清的需求**推出來，不是照通用清單抄。
