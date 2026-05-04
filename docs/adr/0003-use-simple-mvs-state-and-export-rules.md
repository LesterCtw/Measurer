# 使用簡單的 MVS 狀態與 Export 規則

Measurer 的 MVS 會刻意讓 image state、measurement status 與 export 行為保持簡單：只有至少有一筆 successful final measurement 的圖片才是 `Measured`；ROI 改變時直接刪除舊 measurement results，不保留 stale results；Export 只輸出 `Measured` 圖片。Pending 與 Failed 圖片仍會留在 GUI 中，但不產生 Result Images、Debug Images 或 Excel rows；fallback ratio 這類 diagnostic quality indicators 則放在已產生 final measurements 的 Trace Sheet。

這個做法優先選擇可預期的 guided workflow，而不是複雜的 recovery、stale-result handling 或 partial export management。取捨是 failed image reasons 不會保存在匯出的 Excel，skipped files 也只透過 GUI summaries 回報，不會輸出詳細 logs；好處是 export artifacts 保持乾淨，工程師比較容易解讀。
