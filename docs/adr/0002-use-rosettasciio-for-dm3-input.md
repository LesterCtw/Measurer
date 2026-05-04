# 使用 RosettaSciIO 讀取 DM3

Measurer 會先使用 `rosettasciio` 作為 `.dm3` 影像輸入 library。這符合現有 Denoiser 專案方向，也避免自行撰寫 DigitalMicrograph parser；取捨是公司 `.dm3` metadata scale 處理在實際樣本檔測試前仍維持 best effort。
