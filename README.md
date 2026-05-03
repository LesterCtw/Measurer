# Measurer

專案狀態：MVS 規格已整理，目前已完成 PySide6 app shell、TIFF Add Images / Original preview、guided queue 的 Group / per-image scale / rectangle ROI state slice、Metal Island candidate filtering、Rough Boundary Fallback / trace-ready refinement diagnostics、多 Metal Islands 的 TCD / BCD / Height / Horizontal Space / Vertical Space measurement tracer bullet、Result View polish、GUI Box Plot preview，以及 single-source folder Export MVS。這份 README 是目前專案狀態與設計共識的 source of truth。

Measurer 是一個 PySide6 desktop GUI tool，用來量測半導體 MOM 結構 STEM ZC 影像中的 metal 尺寸與 spacing。工具定位是給工程師逐張檢查 ROI、執行量測、確認 Result View，最後批次匯出結果。

Domain language 記錄在 `CONTEXT.md`，用來固定工程師與開發之間對 Metal Island、ROI、Refined Boundary、TCD、BCD、Height、Horizontal Space、Vertical Space 等詞彙的定義。

## 目前已實作

- `uv` Python project scaffold。
- PySide6 desktop app shell。
- `measurer` command 可啟動 GUI。
- 左側 File Queue / control panel 與右側 Original preview workspace。
- Add Images 支援 single 2D TIFF。
- 8-bit / 16-bit grayscale TIFF 可加入 queue。
- RGB/RGBA TIFF 直接轉 grayscale，不顯示 warning。
- multi-page TIFF / 3D stack / unreadable TIFF 在 Add Images 時 skip，不加入 queue。
- Add Images batch summary 顯示 added / skipped 與原因數量。
- duplicate absolute file path 直接忽略，不重設既有 row。
- file queue 支援選取一列或多列後用 Set Group 套用 group name。
- Group name 會 trim 前後空白，trim 後空字串會被拒絕；中間空白與大小寫差異會保留。
- `nm / pixel` 是每張圖片各自的 scale state；metadata scale 優先且不可手動覆寫，沒有 metadata 時可輸入 manual scale，空白時使用 px。
- manual `nm / pixel` 只接受正數與小數；`0`、負數、非數字會顯示 inline error 並保留上一個 valid scale state。
- selected image 支援一個 rectangle ROI，拖拉新 ROI 會取代舊 ROI。
- Clear ROI 會回到 Full image。
- ROI geometry 會 clamp 在 image bounds 內。
- ROI 改變或 Clear ROI 會刪除 stale measurement results，Measure 回到 `Pending`，Export 回到 `Not exported`。
- Measure Current 支援 clean synthetic STEM ZC Image 中多個 bright Metal Islands on dark LK 的 tracer bullet。
- Measure Current 只量測目前選取圖片，不自動切下一張，也不直接寫 output files。
- 沒有 ROI 時，Measure Current 使用 full image 作為 Analysis Region；有 Custom ROI 時，只分析 ROI 內像素。
- Measure Current 會在 Analysis Region 內用 Otsu rough mask 做 connected component detection。
- candidate filtering 已支援 `HARD_MIN_COMPONENT_AREA_PX = 100`、median-area relative threshold default `MIN_AREA_RATIO_TO_MEDIAN = 0.03`，以及 bbox 距離 Analysis Region boundary <= 1 px 的 boundary-touch exclusion。
- `MIN_AREA_RATIO_TO_MEDIAN` 可透過 measurement config 覆寫；GUI 調整欄位尚未實作。
- 如果 filtering 後沒有 Metal Island candidate，Measure 變成 `Failed`，workspace 停在 Original View，status card 顯示 `No metal candidates`。
- 每顆通過 filtering 的 Metal Island 會產生 ordered closed Refined Boundary，並計算 TCD、BCD、Height。
- 多顆 Metal Islands 會依 top-to-bottom、row 內 left-to-right 指派 `M001`、`M002`、`M003` 這類 stable Metal ID。
- Row / column grouping 使用 refined bbox center 與 median-size tolerance。
- 同 row adjacent pair 通過 y-overlap criteria 時，會用 refined bbox horizontal gap 產生 Horizontal Space。
- 同 column adjacent pair 通過 x-overlap criteria 時，會用 shared x-range 上的 minimum vertical boundary-to-boundary gap 產生 Vertical Space。
- missing pair candidates 或 invalid overlap pairs 不會產生 missing Space rows，也不會讓 image 變成 `Failed`。
- valid pair 通過 overlap criteria 但 pair calculation 失敗時，會保留 failed final measurement 與 reason；Result View 不顯示 failed measurement line。
- Refined Boundary 會對 rough boundary point 取 normal-direction brightness profile，可靠的 local half maximum crossing 標記為 `refined`。
- 如果 profile sample 不足、找不到 crossing、contrast 不足、或 bright/dark direction 不合理，該 boundary point 會使用 `fallback_rough`，不讓 Metal Island measurement 失敗。
- 即使 fallback ratio 很高，只要 TCD / BCD / Height 可產生 reportable value，Measure status 仍為 `Measured` / measurement result status 仍為 `success`。
- refinement diagnostics 已提供 `refined_point_count`、`fallback_point_count`、`fallback_ratio`，供 Debug View 與未來 Trace Sheet 使用。
- TCD 使用 top 20% height region 內的最大 horizontal width。
- BCD 使用 bottom 10% height region 內的最大 horizontal width。
- Height 使用 Refined Boundary 內的最大 vertical chord length。
- 成功 Measure Current 後，該圖 Measure 變成 `Measured`，Export 維持 `Not exported`，workspace 切到 Result View。
- Result View 會顯示原圖加上成功的 TCD / BCD / Height / Horizontal Space / Vertical Space Measurement Lines 與一位小數值，不顯示 ROI 或 debug internals。
- Result View 使用固定 measurement type 顏色：TCD cyan、BCD orange、Height yellow、Horizontal Space magenta、Vertical Space lime。
- Result View 數值文字顯示在線段中心附近，使用白字加 dark outline，會 clamp 在 image bounds 內，並用固定上下偏移減少局部碰撞；若仍重疊，不讓 rendering failed。
- manual scale 改變後，Result View 會用現有 px geometry 重新換算顯示值與單位，不需要重測。
- Box Plot preview 已可從 GUI 切換，會依 Group 與 measurement type 彙整 successful final measurements，顯示 raw points with jitter 與 summary/status panel。
- Group 或 manual scale 改變後，Box Plot preview 會重新聚合現有 measurement results，不需要重測。
- Box Plot preview 不混合 nm 與 px；同時存在 nm 與 px measurement results 時，顯示 warning 而不畫 mixed-unit plot。
- Debug View 已有最小 diagnostics：rough mask、kept candidates、excluded small components、excluded boundary-touch components、rejected Space pair count、refined points、fallback points、fallback ratio。
- Export button 已支援 single-source folder MVS：只輸出 Measured 圖片，Pending / Failed 不輸出圖片也不寫入 Excel。
- 如果沒有 Measured 圖片，Export 會被阻止，不建立 output folders/files，status card 顯示 `No measured images to export.`。
- single-source Export 會在原圖資料夾下建立 `measured_image/` 與 `debug_image/`。
- Result Images 會輸出到 `measured_image/`，顯示原圖、official Measurement Lines 與 values，不顯示 ROI/debug internals。
- Debug Images 會輸出到 `debug_image/`，使用 MVS 2x2 diagnostic panel。
- `measurements.xlsx` 會輸出到 `measured_image/`，包含 Summary、Measurements、Trace sheets。
- Excel Summary 依 Group、measurement type、unit 彙整 successful measurements，不混合 nm 與 px。
- Excel Measurements / Trace 只包含 Measured 圖片內產生的 final measurements，並使用 export 當下的 scale state。
- file queue row 預設顯示：
  - Group = `Default`
  - ROI = `Full image`
  - Measure = `Pending`
  - Export = `Not exported`

目前尚未實作 multi-source Export output folder picker、Export overwrite confirmation、完整 export-grade Debug Image diagnostics、`.dm3` input、metadata scale parser、Excel 內嵌 box plot，以及真實 STEM ZC 樣本 validation。

## 開發指令

安裝 / 同步環境：

```bash
uv sync
```

執行 GUI：

```bash
uv run measurer
```

執行測試：

```bash
uv run pytest
```

## 目前 MVS 目標

MVS 的目標不是一次做完完整產品，而是先建立可用的半自動量測流程，驗證 refined boundary 與量測定義是否可靠。

MVS 會包含：

- PySide6 GUI。
- Windows 11 first release target。
- Python 3.12.8 runtime/build target。
- 批量載入 `.tif`、`.tiff`、`.dm3`。
- 2D grayscale 影像量測。
- 8-bit / 16-bit TIFF。
- `.dm3` 讀取先採用 `rosettasciio`。
- RGB/RGBA 直接轉 grayscale，不顯示 warning。
- multi-page TIFF / 3D stack 先拒絕。
- 每張圖片最多一個矩形 ROI。
- 沒有 ROI 時直接分析全圖。
- Otsu rough mask。
- connected component metal candidate detection。
- 面積過濾與邊界截斷排除。
- refined boundary，不使用 Otsu contour 當正式量測邊界。
- 自動量測 TCD、BCD、Height、Horizontal Space、Vertical Space。
- Original / Result / Box Plot / Debug preview。
- GUI box plot 顯示 group 分布。
- Export 時依圖片來源輸出到 `measured_image/` 與 `debug_image/`。
- 匯出 Result Images、Debug Images、xlsx。

MVS 暫不包含：

- `.dm4`。
- 多 ROI。
- polygon ROI。
- 手動拉線 brightness profile。
- Excel 內嵌 box plot / probability chart。
- 複雜 QC score。
- 複雜 spline fitting。
- 影像旋轉校正。
- project/session save。

## 測試策略

在沒有公司實際影像的開發階段，MVS 先使用 synthetic images 建立 regression tests。

Synthetic image generator 需要產生：

- 1024 x 1024 grayscale image。
- bright metal islands。
- dark LK background。
- 可控 TCD / BCD / Height / Horizontal Space / Vertical Space。
- 可控 row / column arrangement。
- noise。
- small bright contamination components。
- ROI boundary-touch cases。
- scale conversion cases。

用途：

- 驗證 Otsu / component filtering。
- 驗證 touching-boundary exclusion。
- 驗證 refined boundary pipeline 不會破壞基本幾何。
- 驗證 TCD / BCD / Height / Horizontal Space / Vertical Space 的 final measurement logic。
- 驗證 Excel Summary / Measurements / Trace Sheet 的資料一致性。

限制：

- synthetic images 不能取代真實 STEM ZC validation。
- `.dm3` metadata scale 仍需要公司實際樣本校正。

## 已知限制與未驗證項目

- Development 可以在 macOS 進行，但第一版 release target 是 Windows 11。
- 開發電腦目前沒有實際公司 `.dm3` 樣本。
- `.dm3` image data 需要嘗試讀取，metadata scale 先做 best effort。
- `.dm3` metadata scale 尚未用實際公司樣本驗證。
- `.dm3` parser 先使用 `rosettasciio`，之後依公司實際樣本校正 metadata scale。
- 如果 `.dm3` metadata scale 讀不到，仍可量測，結果用 px。
- `.dm3` 讀得到 image data 但讀不到 metadata scale 時，不跳 warning，不阻止 Measure / Export；Result View / Excel 顯示單位 `px`，Trace Sheet 記錄 `scale_source = px`。
- GUI Box Plot 不允許混合 nm 與 px。
- Excel Summary 不混合 nm 與 px；若同一次 Export 同時有 nm 與 px，依 `unit` 分開統計。
- Scale 以每張圖片各自判斷：metadata scale 優先且不可手動覆寫；沒有 metadata scale 時才允許使用者輸入 manual nm/pixel；沒有 metadata scale 且使用者未輸入時，該圖使用 px。

## GUI 風格與佈局

GUI 風格參考 `/Users/lesterc/Project/Denoiser` 的深色現代桌面 UI，但只借鑑風格，不借功能流程。

視窗行為：

- 啟動後預設最大化。
- 不使用 slider / splitter bar 作為核心互動。
- 深色主題。
- 左側 file queue / control panel。
- 右側 image workspace。
- 8 px radius。
- Primary action 使用藍色。
- 狀態資訊放在左側底部 status card。

主要 layout：

```text
左側 File Queue Panel:
- Add Images
- Set Group
- nm / pixel
- min area ratio (%)
- Measure Current
- Export
- file table
- status card

右側 Image Workspace:
- view mode controls
- image preview / result / box plot / debug
```

File table 使用 modern data grid 形式，不做傳統 spreadsheet 感的表格。

建議欄位：

```text
[select] | File | Group | ROI | Measure | Export
```

狀態建議：

- ROI：Full image / Custom ROI。
- Measure：Pending / Measured / Failed。
- Export：Not exported / Exported。

Measure 狀態定義：

- `Pending`：尚未成功執行 Measure Current，或 ROI 改變 / Clear ROI 後舊結果已刪除。
- `Measured`：至少有一筆 successful final measurement。
- `Failed`：Measure Current 已執行，但沒有任何 successful final measurement。

## 使用流程

Measurer 的實際流程是 single-image guided batch，不是無人值守的一鍵全批次量測。

流程：

```text
1. 批量載入圖片
2. 選取一張圖片
3. 顯示 Original
4. 可選擇畫 ROI；若不畫 ROI，分析全圖
5. 按 Measure Current
6. 只量測目前圖片
7. 結果暫存在 app state
8. 顯示 Result View
9. 使用者自行點選下一張圖片，重複 ROI / Measure
10. 最後按 Export，批次匯出所有 Measured 圖片
```

Measure Current：

- 只量目前選取圖片。
- 不自動切下一張。
- 不提示下一張。
- 量測結果只暫存在 app memory / app state。
- 不直接寫入資料夾。

Add Images：

- Add Images 時檢查 image shape。
- multi-page TIFF / 3D stack 載入時直接拒絕，不加入 file queue。
- `.dm3` / TIFF image data 讀取失敗時直接拒絕，不加入 file queue。
- 顯示簡短訊息：`Unsupported image shape: only single 2D images are supported.`
- 讀取失敗時顯示簡短訊息：`Failed to read image data.`
- 批量載入時，其他合法圖片仍正常加入。
- Add Images 完成後，左側 status card 顯示 batch summary，例如 `Added 47 images. Skipped 3 files.`。
- 如果有 skipped files，summary 顯示原因類型與數量，例如 `2 unsupported image shape, 1 failed to read image data`。
- MVS 不需要列出每個 skipped file 的完整路徑。
- 用 absolute file path 判斷重複檔案。
- 已在 file queue 的同一路徑再次加入時，直接忽略，不顯示 warning / dialog。
- 重複加入不重設原本 row 的 ROI、group、measurement result、status，也不改變 row 位置。
- 不同資料夾但同檔名視為不同圖片，允許加入。

Export：

- 批次匯出所有 Measured 圖片。
- Pending / Failed 圖片不輸出圖片，也不寫入 Excel。
- 如果沒有任何 Measured 圖片，阻止 Export 並顯示 `No measured images to export.`。
- Export 完成後，左側 status card 顯示 exported / skipped summary，例如 `Exported 8 measured images. Skipped 2 pending, 1 failed.`。
- 如果所有圖片來自同一個資料夾，輸出到該原圖資料夾。
- 如果圖片來自多個資料夾，Export 時必須由使用者指定共同 output folder。
- 若目標檔案已存在，預設覆蓋，但必須先跳確認 dialog。

## Group / Category

每張圖片只能屬於一個 group。

新載入圖片預設：

```text
group = Default
```

互動方式：

```text
1. 使用者在 file table 批量選取圖片
2. 按 Set Group
3. dialog 中輸入新 group 或選擇既有 group
4. 套用到選取圖片
```

Group 改變：

- 不需要重測。
- 只影響 box plot 與 Excel group 欄位。
- Box plot 需要即時刷新。

Group name 規則：

- group name 前後空白自動 trim。
- trim 後空字串不允許。
- 中間空白允許，例如 `Process A`。
- 中文 / 英文 / 數字都允許。
- 大小寫視為不同 group，例如 `A` 和 `a` 是兩個 group。
- 新載入圖片預設 group = `Default`。
- `Default` 是預設 group；如果沒有圖片屬於 `Default`，Box Plot / Summary 自然不顯示它。

## Scale / Unit

GUI 左側提供一個欄位：

```text
nm / pixel: [        ]
```

Scale 每張圖片各自判斷。GUI 左側的 `nm / pixel` 欄位顯示目前選取圖片的 scale 狀態；切換圖片時，欄位跟著目前選取圖片更新。

Scale 優先順序：

```text
1. metadata nm/pixel per image
2. manual nm/pixel for this image
3. px
```

規則：

- 圖片有 metadata scale 時，直接採用 metadata scale，欄位顯示該值並設為不可編輯。
- 圖片沒有 metadata scale 時，欄位保持可編輯，讓使用者可自行輸入 manual nm/pixel。
- 圖片沒有 metadata scale 且使用者未輸入 manual nm/pixel 時，該圖仍可量測，輸出 px。
- 使用者清空 manual nm/pixel 後，已量測結果不丟失，該圖顯示值回到 px。
- 量測結果內部永遠保存 value_px 與線段座標 px。
- 顯示、box plot、Excel export 時再依每張圖片當下 scale 轉成 nm 或維持 px。
- 改 manual nm/pixel 不改 measurement geometry。
- 改 manual nm/pixel 不需要重新 Measure，也不把圖片狀態改成 Needs remeasure。
- Result View 數值、Box Plot、Export 都使用每張圖片當下最新 scale。
- Trace Sheet 記錄 export 當下使用的 `scale_source` / `scale_nm_per_px`。

GUI 需要顯示目前選取圖片使用的 scale value 與欄位是否可編輯。Trace Sheet 記錄 scale source 方便追查。

Manual `nm / pixel` 輸入驗證：

- 只有圖片沒有 metadata scale 時才允許輸入 manual scale。
- 空白代表不使用 manual scale，該圖使用 px。
- 只接受正數。
- `0`、負數、非數字不允許。
- 可以輸入小數，例如 `0.25`。
- invalid input 不套用新值，保留上一個 valid scale 狀態。
- invalid input 顯示 inline error，不跳 dialog。

顯示精度：

- Result View 顯示 1 位小數。
- Excel Summary / Measurements 的主要 value 顯示 1 位小數。
- 內部計算仍保存 float。
- Trace Sheet 的 `value_px` 可保留較高精度供追溯。
- Trace Sheet 記錄 refined boundary summary diagnostic：`refined_point_count`、`fallback_point_count`、`fallback_ratio`。

## ROI

MVS ROI 規則：

- 每張圖最多一個矩形 ROI。
- 沒有 ROI 時，Measure Current 直接分析全圖。
- 有 ROI 時，只分析 ROI 內。
- ROI 可重新畫，新 ROI 取代舊 ROI。
- 可 Clear ROI。
- ROI rectangle 必須 clamp 在影像範圍內，不能超出影像。
- ROI 太小時，Measure Current 不執行。
- ROI 太小不改成 Failed，因為這不是 algorithm failure。
- ROI 太小時，Measure 狀態維持 Pending，左側 status card 顯示 `ROI is too small.`。
- 已量測圖片若 ROI 改變或 Clear ROI，直接刪除舊 measurement result。
- 刪除舊 result 後，Measure 狀態回到 Pending，Export 狀態回到 Not exported。

ROI 顯示規則：

- Original / ROI editing state 可以顯示 ROI rectangle。
- Result View 不顯示 ROI。
- exported Result Image 不顯示 ROI。
- Debug View 可以顯示 ROI。

TODO：

- 多 ROI。
- polygon ROI。
- 可點選 touching-boundary metal，決定是否保留。

## 影像處理流程

每張圖片的 MVS 流程：

```text
讀取影像
→ 取得 scale：metadata / manual / px
→ 建立 analysis mask：ROI 或 full image
→ 在 analysis mask 內計算 Otsu threshold
→ Otsu rough metal mask
→ connected component
→ hard area filter
→ relative area filter
→ 排除 touching analysis boundary 的 component
→ rough boundary extraction
→ local half maximum refined boundary
→ ordered closed polyline boundary
→ 自動量測 TCD / BCD / Height / Horizontal Space / Vertical Space
→ 產生 Result / Debug / Excel data
```

ROI 外完全忽略：

- 不參與 Otsu。
- 不參與 mask。
- 不參與 component labeling。
- 不參與 boundary refinement。
- 不參與 pair grouping。
- 不參與 measurement。

## Otsu 與 Area Filtering

STEM ZC 中：

```text
metal = bright / white
LK = dark / black
```

Otsu：

- 有 ROI：只用 ROI 內 pixel 計算 threshold。
- 沒 ROI：用全圖 pixel 計算 threshold。
- threshold 以上是 metal candidate。

Area filtering：

```text
1. Exclude components with area < HARD_MIN_COMPONENT_AREA_PX
2. HARD_MIN_COMPONENT_AREA_PX = 100
3. Compute median area from remaining components
4. Exclude components with area < median_area * MIN_AREA_RATIO_TO_MEDIAN
5. MIN_AREA_RATIO_TO_MEDIAN default = 0.03
```

目前實作：

- `MIN_AREA_RATIO_TO_MEDIAN` 可透過 measurement config 覆寫，default = `0.03`。
- GUI 調整欄位尚未實作。

後台 config 控制：

- `HARD_MIN_COMPONENT_AREA_PX = 100`

如果任一 filtering stage 後沒有 metal candidate：

- Measure status = Failed。
- reason = No metal candidates。
- Result View 不畫量測線。
- Debug View 顯示 Otsu mask / excluded components。
- GUI 停在 Original，不自動切到 Debug View。
- 左側 status card 顯示 failure reason。

Metal candidate 數量超過 100：

- 不阻止。
- 不顯示 warning。
- 正常量測。

## Boundary-Touch Exclusion

如果 component 接觸 analysis boundary，MVS 先排除不量。

規則：

```text
component bbox 距離 analysis boundary <= 1 px
```

就視為 touching boundary。

有 ROI 時：

- analysis boundary = ROI boundary。

沒有 ROI 時：

- analysis boundary = image boundary。

如果 boundary-touch exclusion 後沒有 metal：

- GUI reason = No metal candidates。
- Debug View / status card 可記錄 all candidates touched analysis boundary。
- GUI 停在 Original，不自動切到 Debug View。
- 左側 status card 顯示 failure reason。

Debug View 需要顯示：

- kept metal candidates。
- excluded small components。
- excluded boundary-touch components。

## Refined Boundary

正式量測不可使用 Otsu contour 直接當邊界。

Otsu 只用來取得 rough mask / rough boundary。正式量測使用 refined boundary。

Refined boundary 方法：

```text
rough contour point
→ 估計法線方向
→ 沿法線方向取 brightness profile
→ 用 local half maximum crossing 找 boundary point
→ 形成 refined boundary points
→ 依 rough contour 順序形成 ordered closed polyline
```

MVS refined boundary 參數：

```text
Boundary profile half-length = 12 px
Boundary profile total length = 24 px
Boundary profile averaging width = 5 px
Profile statistic = median
Boundary point = local half maximum crossing
Refinement sampling step = 2 px
```

Local half maximum crossing 定義：

```text
dark_level = outside LK side robust median
bright_level = inside metal side robust median
threshold = dark_level + 0.5 * (bright_level - dark_level)
boundary = profile crossing threshold
```

為什麼使用 half maximum：

- 對應工程上「亮暗半高」的邊界理解。
- 比 Otsu contour 更貼近局部 intensity transition。
- 比二次微分反曲點更穩定。
- 比 max gradient 更直觀。

Refined point status：

```text
refined:
  找到可靠 local half maximum crossing

fallback_rough:
  local half maximum crossing 不可靠，使用 rough boundary point 補值

invalid:
  保留作為內部診斷狀態，但 MVS 不因 refined point invalid 而放棄 boundary
```

Profile 超出 image / ROI 不一定失敗。只要 inside / outside 兩側仍有足夠 sample，就可以用截短 profile 繼續計算。

MVS 預設：

```text
inside samples >= 4
outside samples >= 4
```

如果不符合，該 boundary point 使用 rough boundary fallback。

若 half maximum 不可靠，例如找不到 crossing、contrast 不足、或亮暗方向不合理：

```text
status = fallback_rough
boundary point = rough boundary point
```

`fallback_rough` 不算 boundary failure。MVS 不使用 `boundary_refinement_failed` 排除 Metal Island。

只要 Metal Island candidate 已通過 area filtering 與 boundary-touch exclusion，就必須產生可量測 boundary：

```text
成功 refined 的點 → 使用 refined point
refinement 不可靠的點 → 使用 rough boundary fallback
```

即使 fallback ratio 很高，也保留該 Metal Island 並進行量測。Debug View 顯示 fallback points，Trace Sheet 記錄 fallback ratio，讓工程師判斷結果可信度。

Measurement status 規則：

- 即使某顆 Metal Island 幾乎 100% 都使用 rough boundary fallback，只要 final measurement value 有產生，Measurements 主表的 `status` 仍然是 `success`。
- `success` 只代表「有可報告的 measurement value」，不代表 refined boundary 品質良好。
- fallback ratio 與 refinement diagnostic 放在 Trace Sheet，不放進 Measurements 主表的 `status`。

Boundary shape MVS 規則：

- rough boundary points 依 contour 順序排列。
- refined / fallback point 保留同一個順序。
- 最後一點接回第一點，形成 ordered closed polyline。
- 不做 boundary smoothing。
- 不做 spline fitting。
- 不做 boundary outlier repair。

## Metal ID 與 Grouping

Metal island ID：

```text
M001, M002, M003...
```

排序規則：

```text
先依 row 由上到下
同一 row 內由左到右
```

Row / column grouping 使用 refined bounding box center：

```text
center_x = (bbox_x_min + bbox_x_max) / 2
center_y = (bbox_y_min + bbox_y_max) / 2
```

Tolerance：

```text
row_tolerance = median refined bbox height * 0.5
column_tolerance = median refined bbox width * 0.5
```

這些 tolerance 先放後台 config，不放主 GUI。

## Measurement Types

正式 measurement types：

- TCD
- BCD
- Height
- Horizontal Space
- Vertical Space

所有產生的 final measurements 需要依狀態進入：

- successful final measurement：進 Result View、GUI Box Plot、Excel Summary、Excel Measurements、Trace Sheet。
- failed final measurement：進 Excel Measurements、Trace Sheet；不進 Result View、GUI Box Plot、Excel Summary。
- 沒有產生 final measurement：不補 row、不提醒、不進任何輸出。

MVS measurement scan 規則：

- 不做額外 robust outlier exclusion。
- TCD / BCD / Height 仍依定義從可計算的 scan line 中取 max。
- Vertical Space 仍依定義從可計算的 scan line 中取 min。
- 如果 scan line 幾何上無法取得必要交點，該 scan line 不能產生候選值；但不再額外用「看起來異常」的規則排除候選值。

### TCD

定義：

```text
metal island top 20% height region 內的水平最大寬度
```

流程：

```text
1. 取得 refined boundary bounding box
2. 定義 top 20% 高度範圍
3. 每 1 px 做水平 scan line
4. scan line 與 refined boundary 相交
5. 取得左右交點
6. width = right_x - left_x
7. TCD = max width
```

每顆 metal island 輸出一筆 TCD。

### BCD

定義：

```text
metal island bottom 10% height region 內的水平最大寬度
```

流程：

```text
1. 取得 refined boundary bounding box
2. 定義 bottom 10% 高度範圍
3. 每 1 px 做水平 scan line
4. scan line 與 refined boundary 相交
5. 取得左右交點
6. width = right_x - left_x
7. BCD = max width
```

每顆 metal island 輸出一筆 BCD。

### Height

定義：

```text
metal island refined boundary 內的最大垂直 chord length
```

流程：

```text
1. 取得 refined boundary 的 x 範圍
2. 每 1 px 做垂直 scan line
3. scan line 與 refined boundary 相交
4. 取得 top / bottom 交點
5. height(x) = bottom_y - top_y
6. Height = max height(x)
```

不可使用單純：

```text
y_max - y_min
```

原因是左上最高、右下最低時，`y_max - y_min` 會產生不存在的斜對角高度。

每顆 metal island 輸出一筆 Height。

### Horizontal Space

Horizontal Space 與 Vertical Space 故意使用不同邏輯，這是 domain rule，不是疏漏。

原因：

- 實務上 metal 會因 LK 收縮而上下移動。
- Horizontal Space 用 refined boundary bounding box gap 比較符合工程判讀。

有效條件：

```text
row grouping 找同 row 相鄰 pair
overlap_y_length > min(height_A, height_B) * 0.3
```

最終值：

```text
Horizontal Space = right_refined_bbox.x_min - left_refined_bbox.x_max
```

注意：

- 使用 refined boundary 的 bounding box。
- 使用 absolute min/max。
- 不使用 rough mask / Otsu bbox。
- 不做 horizontal scan。

每組有效 horizontal pair 輸出一筆 Horizontal Space。

### Vertical Space

有效條件：

```text
column grouping 找同 column 相鄰 pair
overlap_x_length > min(width_A, width_B) * 0.3
```

流程：

```text
1. 取得上下 metal refined bbox 的 x-overlap
2. 在 x-overlap 範圍內每 1 px 做垂直 scan
3. 每條 scan line 與上方 metal refined boundary、下方 metal refined boundary 相交
4. 取上方 metal bottom boundary y
5. 取下方 metal top boundary y
6. gap(x) = lower_top_y - upper_bottom_y
7. Vertical Space = min gap(x)
```

Bounding box 只用來決定掃描範圍與有效 overlap。最終距離必須用 refined boundary 之間的垂直距離。

每組有效 vertical pair 輸出一筆 Vertical Space。

## Pair Candidate 與 Failed Measurement

Pair candidate 若 overlap 條件不通過：

- 不列入 Measurements。
- 可在 Debug View 顯示 rejected reason。
- 沒有 valid pair 不算 failure；只是沒有該類 Space measurement。
- 沒有 pair candidate 或沒有 valid pair 時，不產生 missing Space row，也不提醒使用者。

Pair 通過條件但計算失敗：

- 列入 Measurements，status = failed。
- 不進 Summary 統計。
- reason 放 Trace Sheet。

Metal-level measurement 各 type 獨立：

```text
M001 TCD failed
M001 BCD success
M001 Height success
```

其中成功的仍保留。

Image-level Measure 狀態：

- 只要至少有一筆 successful final measurement，圖片狀態就是 Measured。
- 如果沒有任何 successful final measurement，圖片狀態就是 Failed。

## Output Terms

為了避免名詞混亂，Measurer 固定使用以下名稱：

- **Result View**：GUI 中的原圖加量測線與數值。
- **Result Image**：Export 後給報告使用的量測圖，放在 `measured_image/`。
- **Debug View**：GUI 中的演算法檢查畫面。
- **Debug Image**：Export 後給工程師排錯用的圖，放在 `debug_image/`。
- **Trace Sheet**：Excel 中放次要追溯資料的 sheet。

不要混用：

- 不再使用 `Overlay` 當正式名稱。
- 不再使用 `Annotated Image` 當正式名稱。
- 不再使用 `Details` 當 Excel sheet 名稱。

## Result View / Result Image

Result View 定義：

```text
原圖 + final measurement lines + values
```

不顯示：

- ROI。
- ROI ID。
- Otsu mask。
- component ID。
- Debug boundary。
- raw scan lines。
- 統計表。

線段顏色：

```text
TCD: cyan
BCD: orange
Height: yellow
Horizontal Space: magenta
Vertical Space: lime
Text: white with dark outline
```

規則：

- 每一條 final measurement line 都畫。
- 每一條 final measurement line 都顯示短數值，例如 `35.2 nm`。
- 不在每條線上寫完整 type label。
- 可加小 legend。

文字避讓 MVS 規則：

- 數值文字預設放在線段中心附近。
- 文字加 dark outline。
- 若文字超出影像邊界，往影像內 clamp。
- 若同一小區域已有文字，依序往上 / 下偏移幾個固定距離。
- 若仍重疊，允許重疊，不因此讓 export failed。

## Preview Modes

主要 preview modes：

- Original
- Result
- Box Plot

次要：

- Debug

Debug 功能要稍微藏起來，不破壞主 UI 簡潔性。

建議：

- Original / Result / Box Plot 是主要切換。
- Debug 用右上角小按鈕或 Advanced / More 區域。

行為：

- 載入圖片後預設顯示 Original。
- 量測完成後自動切換 Result View。
- 不自動切下一張。

## Debug View / Debug Image

Debug View 是工程師排錯用，不是報告用。

目前 GUI Debug View 已實作最小 diagnostics：

- rough mask 以藍色 tint 顯示。
- kept candidates 以綠色 bbox 顯示。
- excluded small components 以黃色 bbox 顯示。
- excluded boundary-touch components 以紅色 bbox 顯示。
- refined boundary points 以青色點顯示。
- fallback boundary points 以粉紅色點顯示。
- 下方文字顯示 kept / excluded 類別數量，以及 refined point count / fallback point count / fallback ratio。

Debug Image export 已有 MVS 2x2 panel。完整 export-grade diagnostics 尚未實作。

MVS Debug Image 使用 2x2 panel：

```text
1. Original + refined boundary + metal ID
2. Otsu / rough mask
3. Component map + excluded small components + excluded boundary-touch components
4. Original + all measurement lines + pair/group hints
```

Debug 可包含：

- ROI。
- Otsu mask。
- rough mask。
- connected component 結果。
- excluded small components。
- excluded boundary-touch components。
- metal island ID。
- refined complete boundary。
- row / column grouping。
- horizontal / vertical pair 判斷。
- rejected pair reason。
- measurement lines。

## Box Plot

GUI Box Plot preview 已有 MVS 版本。Excel MVS 暫不內嵌 box plot 圖片。

Box Plot 目前從 app state 中的 successful final measurements 產生，不重新執行 Measure Current。它使用每張圖片當下的 Group 與 scale resolution，把 px geometry 轉成目前顯示單位後再聚合。

目前行為：

- 依 Group 與 measurement type 彙整。
- 顯示 TCD、BCD、Height、Horizontal Space、Vertical Space 中目前有 successful final measurements 的項目。
- 顯示 raw points with jitter。
- 顯示 summary/status panel，包含 measurement count、unit、Groups、measurement types，或 empty/mixed-unit warning。
- Group 改變後會直接刷新，不需要重測。
- manual scale 改變後會直接刷新，不需要重測。
- 如果同一個 Box Plot preview 會混合 nm 與 px，顯示 warning，不畫 mixed-unit plot。

Group filter 尚未實作：

- 未來可用 checkbox / chips 選擇要顯示哪些 group。
- Default 是一般 group，預設顯示。
- 可勾選 / 取消任何 group。

Box plot layout：

```text
2 x 3 grid

TCD | BCD | Height
Horizontal Space | Vertical Space | summary/status panel
```

每張 plot：

- 顯示 box plot。
- 顯示 raw points。
- raw points = 每一筆 final measurement。
- raw points 使用 x-axis jitter，避免點重疊。

Unit 規則：

- 不允許混合 nm 與 px。
- selected groups 若混到 nm 和 px，不畫圖並顯示 warning。

## Excel Export

MVS Excel 輸出一個 `.xlsx`：

單一來源資料夾：

```text
原圖資料夾/
  measured_image/
    measurements.xlsx
```

多來源資料夾：

```text
使用者指定 output folder/
  measured_image/
    measurements.xlsx
```

Sheets：

```text
1. Summary
2. Measurements
3. Trace
```

### Summary

Summary 是 group-level 統計。

欄位：

```text
group
measurement type
count
mean
median
min
max
std
unit
```

規則：

- 包含 Default group。
- 不默默排除任何已量測資料。
- 只統計 successful measurements。
- 不混合 nm 與 px；若同一次 Export 同時有 nm 與 px，依 `group + measurement type + unit` 分開統計。
- Measurements / Trace 仍輸出所有已量測資料，不因 mixed unit 讓 Export failed。

### Measurements

Measurements 是每一條 final measurement 的簡潔明細表。

欄位：

```text
file
group
measurement type
target ID
status
value
unit
```

規則：

- 成功與失敗 final measurement 都列出。
- 失敗 value 留空。
- reason、座標、value_px、scale、ROI 放 Trace Sheet。
- 只包含 Measured 圖片內的 final measurements。
- Pending / Failed 圖片不寫入 Measurements。

### Trace

Trace Sheet 放次要與追溯資料。

Trace 只包含 Measured 圖片內的 final measurements。Pending / Failed 圖片不寫入 Trace。

欄位：

```text
file
group
measurement type
target ID
status
reason
value_px
x1_px
y1_px
x2_px
y2_px
scale_nm_per_px
scale_source
roi_type
roi_x_px
roi_y_px
roi_width_px
roi_height_px
refined_point_count
fallback_point_count
fallback_ratio
```

Refinement summary 欄位規則：

- Metal-level measurement（TCD / BCD / Height）使用該 Metal Island 的 refined / fallback point 統計。
- Space measurement（Horizontal Space / Vertical Space）使用 pair 兩顆 Metal Island 的 refined / fallback point 加總。
- `fallback_ratio = fallback_point_count / (refined_point_count + fallback_point_count)`。
- 若 denominator 為 0，`fallback_ratio` 留空。

ROI 欄位規則：

沒有自訂 ROI、分析全圖：

```text
roi_type = full_image
roi_x_px = 0
roi_y_px = 0
roi_width_px = image_width
roi_height_px = image_height
```

有矩形 ROI：

```text
roi_type = rectangle
roi_x_px = left
roi_y_px = top
roi_width_px = width
roi_height_px = height
```

## File Export

使用者按 Export 後，程式依圖片來源決定輸出位置。

Export 範圍：

- 只輸出 Measured 圖片。
- Pending / Failed 圖片不輸出 Result Image。
- Pending / Failed 圖片不輸出 Debug Image。
- Pending / Failed 圖片不寫入 Excel。
- 如果沒有任何 Measured 圖片，阻止 Export，不建立資料夾，不建立空 Excel，Export 狀態不改變。

若所有圖片來自同一個資料夾，輸出到原圖資料夾：

```text
原圖資料夾/
  measured_image/
    image_001_result.png
    measurements.xlsx
  debug_image/
    image_001_debug.png
```

若圖片來自多個資料夾，Export 時必須由使用者指定共同 output folder：

```text
使用者指定 output folder/
  measured_image/
    image_001_result.png
    measurements.xlsx
  debug_image/
    image_001_debug.png
```

如果目標檔案已有舊結果，設計上要先確認；目前實作尚未加入 overwrite confirmation，會直接覆蓋既有檔案：

- 預設覆蓋。
- overwrite confirmation 尚未實作。
- 多來源資料夾若有同名圖片，Result Image / Debug Image 同名檔案會覆蓋。

覆蓋確認 dialog MVS 規則：

- 只有偵測到既有檔案時才顯示。
- 只提供整批 `Cancel` / `Overwrite`，不提供 rename、skip existing、overwrite selected。
- `Overwrite` 是 primary action，但預設 focus 放 `Cancel`。
- Dialog 需要顯示 output folder。
- Dialog 需要顯示將被覆蓋的檔案類型與數量，例如 `measurements.xlsx`、Result Images 數量、Debug Images 數量。
- 如果使用者按 `Cancel`，整次 Export 取消。
- 如果使用者按 `Overwrite`，整批輸出繼續。

Result Image：

- 原圖。
- final measurement lines。
- values。
- 不顯示 ROI / Debug 資訊。

Debug Image：

- 2x2 debug panel。
- 顯示 segmentation / boundary / component / pair / measurement debug 資訊。

## 訪談紀錄：2026-05-01

本次 grill-me / grill-with-docs 已定案：

- 第一版 release target 是 Windows 11。
- Python runtime/build target 是 Python 3.12.8。
- `.dm3` 讀取先採用 `rosettasciio`。
- 沒有公司實際影像時，先由程式生成 synthetic images 做 regression tests。
- Result View 與 Excel 主要 value 都顯示 1 位小數。
- Export 名詞與輸出位置已統一：
  - `Result View`：GUI 中原圖 + 量測線 + 數值。
  - `Result Image`：報告用匯出圖，放 `measured_image/`。
  - `Debug View`：GUI 中演算法檢查畫面。
  - `Debug Image`：排錯用匯出圖，放 `debug_image/`。
  - `Trace Sheet`：Excel 追溯資料 sheet。
- 單一來源資料夾時，Export 輸出到原圖資料夾。
- 多來源資料夾時，Export 必須由使用者指定共同 output folder。
- 多來源資料夾若有同名圖片，Result Image / Debug Image 同名檔案會覆蓋。
- Refined Boundary 不允許因 local refinement 失敗而讓 metal 失敗。
- 只要 Metal Island candidate 通過 area filtering 與 boundary-touch exclusion，就必須產生可量測 boundary。
- Half maximum refinement 成功時使用 refined point。
- Half maximum refinement 不可靠、sample 不足、或其他局部問題時，使用 rough boundary fallback。
- `fallback_rough` 不算 failure。
- 不使用 `boundary_refinement_failed` 排除 Metal Island。
- 即使 fallback ratio 很高，也保留該 Metal Island 並進行量測。
- Debug View 顯示 fallback points。
- Trace Sheet 記錄 fallback ratio。
- 即使某顆 Metal Island 幾乎 100% 都使用 rough boundary fallback，只要 final measurement value 有產生，Measurements 主表的 `status` 仍然是 `success`。
- `success` 不代表 refined boundary 品質良好；fallback ratio 與 refinement diagnostic 放在 Trace Sheet。
- Trace Sheet 的 MVS refinement summary 欄位為 `refined_point_count`、`fallback_point_count`、`fallback_ratio`。
- Result Image / Result View 的文字避讓採 MVS 固定規則：線段中心附近、dark outline、出界 clamp、局部固定偏移；若仍重疊，允許重疊且不讓 export failed。
- MVS 不做 measurement scan outlier guard；TCD / BCD / Height 取可計算 scan line 的 max，Vertical Space 取可計算 scan line 的 min，不額外排除「看起來異常」的候選值。
- Refined Boundary 的 MVS shape 是 ordered closed polyline：保留 rough contour 順序，refined / fallback point 接成閉合折線；不做 smoothing、spline fitting、boundary outlier repair。
- Export overwrite confirmation 只做整批確認：偵測到既有檔案時，顯示 output folder 與將被覆蓋的檔案類型 / 數量，使用者只能 `Cancel` 或 `Overwrite`。
- Excel Export 遇到 mixed unit 時不失敗；Measurements / Trace 全部輸出，Summary 依 `group + measurement type + unit` 分開統計。
- 改 manual nm/pixel 不需要重測；Result View、Box Plot、Export 都用該圖片當下最新 scale 轉換，Trace Sheet 記錄 export 當下的 scale。
- ROI 改變或 Clear ROI 後直接刪除舊 measurement result，Measure 狀態回到 Pending，Export 狀態回到 Not exported。
- Export 只包含 Measured 圖片；Pending / Failed 圖片不輸出 Result Image、Debug Image，也不寫入 Excel。
- 沒有任何 Measured 圖片時阻止 Export，顯示 `No measured images to export.`，不建立資料夾或空 Excel。
- 圖片狀態判定：至少有一筆 successful final measurement 就是 Measured；沒有任何 successful final measurement 才是 Failed。沒有 valid Space pair 不算 failure。
- 沒有 pair candidate 或沒有 valid pair 時，不產生 missing Space row，也不提醒使用者。
- RGB/RGBA input 直接轉 grayscale，不顯示 warning，不阻止 Measure / Export。
- multi-page TIFF / 3D stack 在 Add Images 時直接拒絕，不加入 file queue；其他合法圖片仍正常加入。
- `.dm3` 讀得到 image data 但讀不到 metadata scale 時，不提示也不阻止流程；結果用 `px`，Trace Sheet 記錄 `scale_source = px`。
- `.dm3` / TIFF image data 讀取失敗時，在 Add Images 直接拒絕，不加入 file queue；其他合法圖片仍正常加入。
- Add Images 以 absolute file path 去重；同一路徑重複加入直接忽略，不重設既有 row， 不同資料夾同檔名允許加入。
- Group name 前後空白自動 trim，trim 後不可為空；中間空白、中文、英文、數字允許，大小寫視為不同 group。
- Manual `nm / pixel` 只在圖片沒有 metadata scale 時可編輯；空白代表該圖使用 px；只接受正數，可輸入小數；`0`、負數、非數字不套用並顯示 inline error。
- ROI rectangle 必須 clamp 在影像範圍內；ROI 太小時 Measure Current 不執行，且不把圖片狀態改成 Failed。
- Measure Current 若失敗，GUI 停在 Original，不自動切 Debug View；file table 顯示 Failed，左側 status card 顯示 failure reason。
- Failed 圖片不寫入 Trace Sheet；failure reason 只保留在 GUI status card / Debug View。
- 只有產生的 final measurements 會進輸出；沒有 pair candidate 或沒有 valid pair 時，不補 missing Space row，也不進任何輸出。
- Trace Sheet 的 refinement summary 對 TCD / BCD / Height 使用單顆 Metal Island 統計；對 Horizontal Space / Vertical Space 使用 pair 兩顆 Metal Island 的合併統計。
- ROI 太小時 Measure Current 不執行，Measure 狀態維持 Pending，status card 顯示 `ROI is too small.`；若 ROI 已改變，舊 result 仍依規則刪除。
- Add Images 完成後 status card 顯示 added / skipped summary；skipped files 顯示原因類型與數量，不逐檔跳 dialog。
- Export 完成後 status card 顯示 exported / skipped summary；若沒有 skipped files，只顯示 exported measured image count。

## 後續 TODO

- 多 ROI。
- polygon ROI。
- 可點選 touching-boundary metal 並手動保留。
- 手動拉線 brightness profile。
- 人工線段顯示 profile plot。
- Excel 內嵌 box plot / probability chart。
- Group Summary 之外的額外統計 sheet，如有需要再加。
- Export selected。
- Measure selected。
- Auto advance after measure preference。
- project/session save。
- `.dm3` metadata parser 根據公司實際樣本校正。
- `.dm4` optional support，如未來真的需要。
- page selector for multi-page TIFF。
- 手動 threshold 或更進階 threshold mode。
- robust extent / outlier repair，如果 refined boundary outlier 實測明顯。
- 更完整的 boundary smoothing / continuous boundary refinement。
- 影像旋轉校正。
