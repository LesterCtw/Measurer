# Measurer

專案狀態：MVS 規格整理中。這份 README 是目前專案狀態與設計共識的 source of truth。

Measurer 是一個 PySide6 desktop GUI tool，用來量測半導體 MOM 結構 STEM ZC 影像中的 metal 尺寸與 spacing。工具定位是給工程師逐張檢查 ROI、執行量測、確認 Result View，最後批次匯出結果。

Domain language 記錄在 `CONTEXT.md`，用來固定工程師與開發之間對 Metal Island、ROI、Refined Boundary、TCD、BCD、Height、Horizontal Space、Vertical Space 等詞彙的定義。

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
- RGB/RGBA 可轉 grayscale，但需要顯示 warning。
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
- 同一批結果不允許混合 nm 與 px 做 box plot 或 summary 統計。
- 使用者手動輸入 nm/pixel 時，會套用到所有圖片。

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
- Measure：Pending / Measured / Failed / Needs remeasure。
- Export：Not exported / Exported。

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
10. 最後按 Export，批次匯出所有已量測結果
```

Measure Current：

- 只量目前選取圖片。
- 不自動切下一張。
- 不提示下一張。
- 量測結果只暫存在 app memory / app state。
- 不直接寫入資料夾。

Export：

- 批次匯出所有已量測圖片。
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

## Scale / Unit

GUI 左側提供一個欄位：

```text
nm / pixel: [        ]
```

Scale 優先順序：

```text
1. manual nm/pixel
2. metadata nm/pixel per image
3. px
```

規則：

- 手動 nm/pixel 有填：所有圖片使用手動 scale，輸出 nm。
- 手動 nm/pixel 沒填：嘗試使用每張圖片 metadata scale。
- metadata scale 讀不到：該圖仍可量測，輸出 px。
- 手動 nm/pixel 清空後，已量測結果不丟失，顯示值回到 metadata scale 或 px。
- 量測結果內部永遠保存 value_px 與線段座標 px。
- 顯示、box plot、Excel export 時再依目前 scale 轉成 nm 或維持 px。

GUI 不需要顯示 scale source。Trace Sheet 可以記錄 scale source 方便追查。

顯示精度：

- Result View 顯示 1 位小數。
- Excel Summary / Measurements 的主要 value 顯示 1 位小數。
- 內部計算仍保存 float。
- Trace Sheet 的 `value_px` 可保留較高精度供追溯。

## ROI

MVS ROI 規則：

- 每張圖最多一個矩形 ROI。
- 沒有 ROI 時，Measure Current 直接分析全圖。
- 有 ROI 時，只分析 ROI 內。
- ROI 可重新畫，新 ROI 取代舊 ROI。
- 可 Clear ROI。
- 已量測圖片若 ROI 改變，狀態改為 Needs remeasure。

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
→ 取得 scale：manual / metadata / px
→ 建立 analysis mask：ROI 或 full image
→ 在 analysis mask 內計算 Otsu threshold
→ Otsu rough metal mask
→ connected component
→ hard area filter
→ relative area filter
→ 排除 touching analysis boundary 的 component
→ rough boundary extraction
→ local half maximum refined boundary
→ boundary smoothing / continuous boundary
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

GUI 可調：

- `MIN_AREA_RATIO_TO_MEDIAN`

後台 config 控制：

- `HARD_MIN_COMPONENT_AREA_PX = 100`

如果任一 filtering stage 後沒有 metal candidate：

- Measure status = Failed。
- reason = No metal candidates。
- Result View 不畫量測線。
- Debug View 顯示 Otsu mask / excluded components。

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
- Debug View / Trace Sheet 可記錄 all candidates touched analysis boundary。

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
→ 排序 / smoothing / continuous closed boundary
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

所有正式 measurement type 都需要進入：

- Result View
- GUI Box Plot
- Excel Summary
- Excel Measurements
- Trace Sheet

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

GUI 需要 box plot preview。Excel MVS 暫不內嵌 box plot 圖片。

Box plot 以 group 分組。

Group filter：

- 使用 checkbox / chips 選擇要顯示哪些 group。
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
- 不混合 nm 與 px。

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

### Trace

Trace Sheet 放次要與追溯資料。

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
```

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

如果目標檔案已有舊結果：

- 預設覆蓋。
- 覆蓋前必須跳確認 dialog。
- 多來源資料夾若有同名圖片，Result Image / Debug Image 同名檔案會覆蓋。

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

下次待續問題：

- 如果某顆 Metal Island 幾乎 100% 都使用 rough boundary fallback，Measurements 主表的 status 是否仍然固定為 `success`。
- Trace Sheet 需要哪些 fallback / refinement summary 欄位。
- Result Image 文字重疊時的避讓規則。
- Boundary smoothing / continuous boundary 的 MVS 最小實作方式。
- GUI Export 覆蓋確認 dialog 要如何呈現單一來源與多來源情境。

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
