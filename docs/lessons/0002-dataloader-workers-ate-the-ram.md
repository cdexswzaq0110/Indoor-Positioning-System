---
id: L0002
date: 2026-09-03
outcome: useful
tags: [訓練, windows, 記憶體, ultralytics, 背景工作]
anchors:
  - ml/train.py
  - CLAUDE.md
supersedes:
hits: 0
---

# 訓練炸掉時先問「是哪一種記憶體」——這次是 RAM，不是 VRAM

## 觸發情境

在 Windows、16GB RAM 的機器上跑 ultralytics 訓練，跑完第一個 epoch 之後死在第二個。

## 領悟

錯誤訊息是：

```
RuntimeError: Caught MemoryError in DataLoader worker process 2.
numpy._core._exceptions._ArrayMemoryError:
  Unable to allocate 1.17 MiB for an array with shape (640, 640, 3) and data type uint8
```

**「訓練跑到一半炸掉」的直覺是 CUDA OOM，但這次連 1.17 MiB 都配不到——
那個數字太小了，小到不可能是顯卡的問題。** GPU 當時只用了 2.67G / 12G。
配不到 1 MiB 的是**系統 RAM**。

原因是 ultralytics 的 `workers` 預設 8。在 Linux 上 fork 出來的 worker 共享 page，
成本低；**Windows 用 spawn，每個 worker 都是一個完整的 Python + torch 行程**，
各自約 1GB RSS。8 個就是 8GB，加上主行程、mosaic 增強要開的 640×640 畫布、
再加上使用者本來就開著的瀏覽器與其他 app——16GB 的機器直接見底。
【已確認：2026-09-03 實測，失敗當下 `Get-CimInstance Win32_OperatingSystem` 顯示
free 4.6GB、commit charge 30.6GB / 49.7GB limit】

為什麼撐過了第一個 epoch 才死：記憶體是**慢慢被吃到臨界**的，不是一開始就爆。
所以「跑起來了」不等於「跑得完」——長時間背景工作的驗收條件是跑完，不是啟動成功。

## 為什麼會撞到

因為 preflight 查了 GPU、查了磁碟、查了 CLI，**沒查 RAM**。
查 GPU 是因為知道要訓練；但「訓練」在腦中對應到的資源是 VRAM，不是 RAM。
dataloader 是 CPU 側的東西，它不在「訓練 = GPU」這個直覺的視野裡。

## 下一輪怎麼用

- **在這台機器上跑任何 ultralytics 訓練，`workers` 不要超過 4。** 已經寫成
  `ml/train.py --workers` 的預設值，並在旁邊註明症狀，免得下次又從 CUDA OOM 開始找。
- preflight 要查的不只是「有沒有 GPU」，還有**同時有多少 free RAM**——
  而且要在使用者平常開著的東西都開著的狀態下查，不是在乾淨機器上查。
- 長時間背景工作要掛**涵蓋失敗訊號的監看**，不能只 grep 進度。
  這次是靠 exit code 1 才發現，中間空等了一段。監看的 filter 要包含
  `MemoryError|CUDA out of memory|Traceback|Killed`，不是只有 `^ +all +[0-9]`。
