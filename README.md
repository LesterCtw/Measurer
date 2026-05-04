# Measurer

專案狀態：MVS 規格已整理，目前已完成 PySide6 app shell、TIFF / `.dm3` Add Images / fit-to-window Original preview、guided queue 的 Group / batch default scale / per-image scale override / rectangle + polygon ROI Union editing、Metal Island candidate filtering、Rough Boundary Fallback / trace-ready refinement diagnostics、多 Metal Islands 的 TCD / BCD / Height / Horizontal Space / Vertical Space measurement tracer bullet、Result View polish、GUI Box Plot preview、Denoiser-inspired 深色 UI，以及 Export MVS 的 single-source / multi-source output 與 overwrite confirmation。這份 README 是目前專案狀態與設計共識的唯一可信來源。

Measurer 是一個 PySide6 desktop GUI tool，用來量測半導體 MOM 結構 STEM ZC 影像中的 metal 尺寸與 spacing。工具定位是讓工程師逐張檢查 ROI、執行量測、確認 Result View，最後批次匯出結果。

Domain language 記錄在 `CONTEXT.md`，用來固定工程師與開發之間對 Metal Island、ROI、Refined Boundary、TCD、BCD、Height、Horizontal Space、Vertical Space 等詞彙的定義。

## 品牌與打包 Icon

本程式的正式品牌名稱是 `Measurer`。

打包成 Windows app 時必須使用專案內的 Measurer icon：

```text
assets/icons/measurer.ico
```

`assets/icons/measurer.png` 是同一個 icon 的 PNG 版本，方便 README、installer 或其他包裝流程預覽使用。這個 icon 使用 Aligner / Denoiser / Measurer 共用的深色圓角 icon 風格，僅保留置中的產品首字母，不放底部 wordmark。Windows 打包流程必須把 icon 參數指向 `assets/icons/measurer.ico`，確保打包後的 exe / shortcut 顯示 Measurer 品牌 icon。

## 目前已實作

- `pip` / `venv` Python project scaffold，可在 Windows 11 + Python 3.12.8 環境安裝。
- PySide6 desktop app shell。
- `measurer` command 可啟動 GUI。
- 左側 File Queue / control panel 與右側 fit-to-window image workspace。
- Add Images 支援 single 2D TIFF 與 `rosettasciio` 可讀取的 single 2D `.dm3`。
- 8-bit / 16-bit grayscale TIFF 可加入 queue。
- TIFF 若有一致的 X/Y resolution metadata，會換算成 metadata `nm / pixel`。
- RGB/RGBA TIFF 直接轉 grayscale，不顯示 warning。
- multi-page TIFF / unsupported `.dm3` shape / 3D stack / unreadable image data 在 Add Images 時 skip，不加入 queue。
- TIFF / `.dm3` 讀取、grayscale conversion 與 metadata `nm / pixel` parsing 已集中在 `image_input.py`；`image_queue.py` 只負責 File Queue state、Group、scale、ROI 與 Measure / Export status。
- Add Images batch summary 顯示 added / skipped 與原因數量。
- 重複的 absolute file path 會直接忽略，不重設既有 row。
- file queue 支援一般點選單列；需要多列 Set Group 時可用 Shift / Cmd / Ctrl 這類系統標準多選手勢。File Queue 不允許直接 double-click 編輯欄位，Group 只能透過 Set Group 控制修改。
- File Queue 的 Set Group 控制放在檔案列表正上方；列表每列是一張圖片，單一可見 `Image` 欄以上下兩段顯示 file name / group badge 與 status / export，同 group 使用相同 badge 顏色，避免長檔名被 Group 欄壓縮到難以辨識。
- Group name 會 trim 前後空白，trim 後空字串會被拒絕；中間空白與大小寫差異會保留。
- `nm / pixel` 使用 batch default scale 搭配 per-image override；metadata scale 優先且不可手動覆寫，沒有 metadata 時先使用 batch manual default，單張另行輸入不同值時使用該圖 override，完全沒有 manual 時才使用 px。
- manual `nm / pixel` 只接受正數與小數；`0`、負數、非數字會顯示 inline error，並保留上一個 valid scale state。
- selected image 支援多個 rectangle / polygon ROI Shapes；拖拉 rectangle 或完成 polygon 會加入 ROI Union，不會取代舊 ROI。
- ROI editing UI 支援 Rectangle / Polygon mode；Rectangle 用拖拉建立，Polygon 用 left-click 加 vertices、double-click 完成。
- 尚未完成的 polygon drawing 不會加入 ROI Union，也不會影響 Measure Current。
- Original / Debug workspace 會顯示既有 ROI；拖選 rectangle 或繪製 polygon 時會顯示 cyan outline，不用實心色塊蓋住影像。
- Image workspace 會等比例 fit 影像，不讓大型原始影像的 pixmap size 撐壞視窗比例。
- Original preview、Result Image、Debug View 與 Debug Image 共用同一套 grayscale display normalization，避免 GUI 預覽與匯出圖片亮度轉換規則分歧。
- Undo ROI 會移除最近完成的 ROI Shape，不論是 rectangle 或 polygon；Undo 到沒有 ROI Shapes 時回到 Full image。
- Clear ROI 會回到 Full image。
- ROI geometry 會 clamp 在 image bounds 內。
- ROI Union 幾何規則集中在獨立 module，Image Queue、Measure Current、Result / Debug display 與 Export 共用同一套 rectangle / polygon ROI Shape clamp、bounding box、mask 與 area 計算。
- ROI 改變、Undo ROI 或 Clear ROI 會刪除 stale measurement results，Measure 回到 `Pending`，Export 回到 `Not exported`。
- Measure Current 支援 clean synthetic STEM ZC Image 中多個 bright Metal Islands on dark LK 的 tracer bullet。
- Measure Current 只量測目前選取圖片，不自動切下一張，也不直接寫 output files。
- 沒有 ROI 時，Measure Current 使用 full image 作為 Analysis Region；有 Custom ROI 時，只分析 rectangle / polygon ROI Union 內像素。
- Measure Current 會在 Analysis Region 內用 Otsu rough mask 做 connected component detection。
- candidate filtering 已支援 `HARD_MIN_COMPONENT_AREA_PX = 100`、median-area relative threshold default `MIN_AREA_RATIO_TO_MEDIAN = 0.03`，以及距離 effective Analysis Region boundary <= 1 px 的 boundary-touch exclusion；Full image 用 image boundary，rectangle ROI / ROI Union 用實際 selected mask edge。
- `MIN_AREA_RATIO_TO_MEDIAN` 可透過 measurement config 覆寫；GUI 調整欄位尚未實作。
- 如果 filtering 後沒有 Metal Island candidate，Measure 變成 `Failed`，workspace 停在 Original View，status card 顯示 `No metal candidates`。
- 每顆通過 filtering 的 Metal Island 會產生 ordered closed Refined Boundary，並計算 TCD、BCD、Height。
- 多顆 Metal Islands 會依 top-to-bottom、row 內 left-to-right 指派 `M001`、`M002`、`M003` 這類 stable Metal ID。
- Row / column grouping 使用 refined bbox center 與 median-size tolerance。
- 同 row adjacent pair 通過 y-overlap criteria 時，會用 refined bbox horizontal gap 產生 Horizontal Space，Measurement Line 畫在 pair 的 refined boundary 與互相面對 bbox side 的交點之間。
- 同 column adjacent pair 通過 x-overlap criteria 時，會用 shared x-range 上的 minimum vertical LK gap 產生 Vertical Space；Measurement Line 端點會落在 LK gap 內，不壓到上下 metal pixel。
- missing pair candidates 或 invalid overlap pairs 不會產生 missing Space rows，也不會讓 image 變成 `Failed`。
- valid pair 通過 overlap criteria 但 pair calculation 失敗時，會保留 failed final measurement 與 reason；Result View 不顯示 failed measurement line。
- Refined Boundary 會對 rough boundary point 取 normal-direction brightness profile，可靠的 local half maximum crossing 標記為 `refined`。
- 如果 profile sample 不足、找不到 crossing、contrast 不足、或 bright/dark direction 不合理，該 boundary point 會使用 `fallback_rough`，不讓 Metal Island measurement 失敗。
- 即使 fallback ratio 很高，只要 TCD / BCD / Height 可產生可報告值，Measure status 仍為 `Measured` / measurement result status 仍為 `success`。
- refinement diagnostics 已提供 `refined_point_count`、`fallback_point_count`、`fallback_ratio`，供 Debug View 與未來 Trace Sheet 使用。
- TCD 使用 top 20% height region 內的最大 horizontal width。
- BCD 使用 bottom 5% height region 內的最大 horizontal width。
- Height 使用 Refined Boundary 內的最大 vertical chord length。
- 成功 Measure Current 後，該圖 Measure 變成 `Measured`，Export 維持 `Not exported`，workspace 切到 Result View。
- Result View 會顯示原圖加上成功的 TCD / BCD / Height / Horizontal Space / Vertical Space Measurement Lines 與一位小數值，不顯示 ROI 或 debug internals。
- Result View 的 Measurement Lines / values 由 canvas 依目前顯示尺寸繪製，不把文字先畫進原始影像 pixmap 再放大。
- Result View 下方 summary 依 measurement type 彙整 value range 與 count，避免多 Metal Islands 時把每一筆完整名稱串成難讀長句。
- Result View 使用固定 measurement type 顏色：TCD cyan、BCD orange、Height yellow、Horizontal Space magenta、Vertical Space lime。
- Result View、Box Plot preview 與 Export 目前共用同一組 measurement type 順序、target ID 解析、scale label、summary 與顏色定義，避免 GUI 與匯出結果對 TCD / BCD / Height / Horizontal Space / Vertical Space 的呈現規則分歧。
- Exported Result Image rendering 已集中在 `result_render.py`；之後若要調整 official Measurement Lines 與 value label 的 QImage rendering，優先改這個 module。
- Result View 數值文字顯示在線段中心附近，使用白字加 dark outline，會 clamp 在 image bounds 內，並用固定上下偏移減少局部碰撞；若仍重疊，不讓 rendering failed。
- batch manual default 或單張 manual override 改變後，Result View 會用現有 px geometry 重新換算顯示值與單位，不需要重測。
- Box Plot preview 已可從 GUI 切換，會依 Group 與 measurement type 彙整 successful final measurements，使用 canvas 依目前顯示尺寸繪製 raw points with jitter、左側 y-axis 刻度與 summary/status panel；x-axis 先依 measurement type 分群，再在群內並排各 Group 方便比較。
- Box Plot preview 的資料點整理、unit 混用檢查、bucket 排序、摘要文字與 percentile/tick 計算集中在獨立 module；GUI 只負責依這些結果繪製畫面。
- Box Plot preview 提供 All 與 TCD / BCD / Height / Horizontal Space / Vertical Space checkbox，可只顯示勾選的 measurement types；切換 checkbox 會用現有 results 立即刷新，不需要重測。
- Group、batch manual default 或單張 manual override 改變後，Box Plot preview 會重新聚合現有 measurement results，不需要重測。
- Box Plot preview 不混合 nm 與 px；同時存在 nm 與 px measurement results 時，顯示 warning 而不畫 mixed-unit plot。
- Debug View 已有最小 diagnostics：rough mask、kept candidates、excluded small components、excluded boundary-touch components、rejected Space pair count、refined points、fallback points、fallback ratio。
- Debug View / Debug Image 的 rough mask、candidate boxes 與 Refined Boundary diagnostic rendering 已集中在 `debug_render.py`，避免 GUI 與匯出圖各自維護一套 diagnostic drawing rules。
- Export button 已支援 single-source / multi-source folder MVS：只輸出 Measured 圖片，Pending / Failed 不輸出圖片也不寫入 Excel。
- 如果沒有 Measured 圖片，Export 會被阻止，不建立 output folders/files，status card 顯示 `No measured images to export.`。
- single-source Export 會在原圖資料夾下建立 `measured_image/` 與 `debug_image/`。
- multi-source Export 會要求使用者選擇共同 output folder，並在該資料夾下建立 `measured_image/` 與 `debug_image/`。
- Export 偵測到既有 output targets 時，會顯示一個整批 overwrite confirmation dialog，只提供 `Cancel` / `Overwrite`。
- Result Images 會輸出到 `measured_image/`，顯示原圖、official Measurement Lines 與 values，不顯示 ROI/debug internals。
- Debug Images 會輸出到 `debug_image/`，使用 MVS 2x2 diagnostic panel。
- `measurements.xlsx` 會輸出到 `measured_image/`，包含 Summary、Measurements、Trace sheets。
- Excel Summary 依 Group、measurement type、unit 彙整 successful measurements，不混合 nm 與 px。
- Excel Measurements / Trace 只包含 Measured 圖片內產生的 final measurements，並使用 export 當下的 scale state。
- Excel Trace Sheet 記錄 ROI metadata：Full image 使用 `roi_type = full_image` 與 `roi_shape_count = 0`；一個或多個 ROI Shapes 使用 `roi_type = union`、ROI Union bounding box、以及 completed ROI Shape 數量。
- Trace Sheet header、ROI Union metadata、scale source 與 Refined Boundary refined/fallback summary 已集中在 `trace_sheet.py`；`export.py` 只負責 workbook / file output orchestration。
- file queue row 預設顯示：
  - Group = `Default`
  - ROI = `Full image`
  - Measure = `Pending`
  - Export = `Not exported`

目前尚未實作完整 export-grade Debug Image diagnostics、Excel 內嵌 box plot，以及真實 STEM ZC / 公司 `.dm3` metadata scale validation。

## Windows 11 pip-only 安裝、測試與打包流程

以下流程以 Windows 11 PowerShell + Python 3.12.8 為準。這個專案在 Windows 上只使用 `pip install` 安裝套件，不使用 `uv`、Poetry、Conda 或其他 dependency manager。

### 1. 環境檢查

確認 Windows 可以找到 Python 3.12：

```powershell
py -3.12 --version
```

預期看到 `Python 3.12.x`。本專案第一版 runtime/build target 是 Python 3.12.8；如果看到其他 major/minor 版本，請先安裝 Python 3.12。

### 2. 建立 virtual environment

```powershell
py -3.12 -m venv .venv
```

啟用 virtual environment：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 擋下啟用 script，先在同一個 PowerShell 視窗執行一次：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. 安裝開發環境

所有安裝都透過 `python -m pip install` 執行：

```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
```

這會以 editable mode 安裝 Measurer，並安裝測試需要的 `pytest`。使用 editable mode 的原因是開發時修改 `src/` 內程式後，不需要重裝 package；取捨是這不是最乾淨的 end-user 安裝方式，只適合開發與測試。

### 4. 啟動 GUI

```powershell
measurer
```

如果 `measurer` command 沒有被 PowerShell 找到，可改用：

```powershell
python -m measurer.app
```

### 5. 執行自動測試

```powershell
python -m pytest
```

測試通過代表目前 synthetic image regression、GUI shell、image queue、measurement、export、documentation 行為符合專案目前規格。這不能取代真實 STEM ZC / 公司 `.dm3` validation；真實資料仍需要人工驗收。

### 6. 手動安裝 smoke test

在 Windows 11 開發機完成安裝後，至少跑一次這個 smoke test：

1. 執行 `measurer`，確認 GUI 可以開啟且視窗標題是 `Measurer`。
2. 執行 `python scripts\generate_ab_group_test_images.py`，產生測試 TIFF 到 Desktop 的 `ab_group_tif_test_images`。
3. 在 GUI 按 Add Images，加入剛產生的 TIFF。
4. 選一張圖，確認 Original preview 正常顯示。
5. 畫一個 rectangle ROI，再切到 Polygon mode 畫一個 polygon ROI。
6. 按 Measure Current，確認狀態變成 `Measured` 且切到 Result View。
7. 切到 Debug View，確認有 diagnostics。
8. 按 Export，確認原圖資料夾下產生 `measured_image/`、`debug_image/` 與 `measurements.xlsx`。
9. 打開 `measurements.xlsx`，確認有 Summary、Measurements、Trace sheets。

### 7. Windows 打包成 exe

目前沒有 committed packaging script；Windows 打包先使用 PyInstaller 手動流程。這樣做的原因是 MVS 先保留最少工具鏈，等 Windows 實機驗證後再把穩定指令固化成 script；取捨是第一次打包需要人工照步驟執行。

請在乾淨的 Windows 11 PowerShell 中執行：

```powershell
py -3.12 -m venv .venv-build
.\.venv-build\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
python -m pip install pyinstaller
Remove-Item -Recurse -Force build, dist, Measurer.spec -ErrorAction SilentlyContinue
python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name Measurer `
  --icon assets\icons\measurer.ico `
  --paths src `
  --collect-all PySide6 `
  --collect-all rsciio `
  --hidden-import rsciio.digitalmicrograph `
  src\measurer\app.py
```

打包完成後，預期輸出：

```text
dist\Measurer\Measurer.exe
```

`--windowed` 會讓 app 以 GUI 方式啟動，不顯示 console 視窗。`--collect-all rsciio` 與 `--hidden-import rsciio.digitalmicrograph` 是為了讓 `.dm3` reader 在 frozen app 中仍可被 PyInstaller 收進去；取捨是 build 可能比較大，之後如果 Windows release 驗證穩定，可以再縮小 collect 範圍。

### 8. 打包後安裝測試流程

在同一台 Windows build machine 上先測一次：

```powershell
.\dist\Measurer\Measurer.exe
```

接著把整個 `dist\Measurer\` 資料夾複製到另一台乾淨 Windows 11 電腦，或至少複製到沒有啟用 `.venv-build` 的位置，再跑一次：

1. 雙擊 `Measurer.exe`，確認 GUI 可以開啟。
2. 確認 exe / shortcut icon 是 Measurer icon。
3. 用 Add Images 加入 8-bit 或 16-bit grayscale TIFF。
4. 測 Full image Measure Current，確認可進 Result View。
5. 測 rectangle / polygon ROI Union 後 Measure Current。
6. 測 Export，確認輸出 Result Images、Debug Images、`measurements.xlsx`。
7. 如果有公司 `.dm3` 樣本，加入 `.dm3` 並確認 image data 可讀；metadata scale 目前仍是 best effort。

打包驗收通過的最低標準：GUI 可開、TIFF 可加入、Measure Current 可成功、Export 可產生 `measured_image/`、`debug_image/`、`measurements.xlsx`。`.dm3` metadata scale 尚未用公司實際樣本驗證，所以不能把 `.dm3` scale correctness 視為 v1.1 打包完成條件。

## 目前 MVS 目標

MVS 的目標不是一次做完完整產品，而是先建立可用的半自動量測流程，驗證 refined boundary 與量測定義是否可靠。

MVS 會包含：

- PySide6 GUI。
- 第一版 release target 是 Windows 11。
- Runtime / build target 是 Python 3.12.8。
- 批量載入 `.tif`、`.tiff`、`.dm3`。
- 2D grayscale 影像量測。
- 8-bit / 16-bit TIFF。
- `.dm3` 讀取先採用 `rosettasciio`。
- RGB/RGBA 直接轉 grayscale，不顯示 warning。
- multi-page TIFF / 3D stack 先拒絕。
- 每張圖片可有多個 rectangle / polygon ROI Shapes；Analysis Region 使用這些 ROI Shapes 的聯集。
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
- 驗證不相連 ROI Shapes 仍作為單一 ROI Union 產生 Horizontal Space / Vertical Space。
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
- TIFF resolution metadata 可讀取時會作為 metadata scale；若 X/Y resolution 不一致或缺少 resolution unit，仍可量測並依一般 scale fallback 規則處理。
- GUI Box Plot 不允許混合 nm 與 px。
- Excel Summary 不混合 nm 與 px；若同一次 Export 同時有 nm 與 px，依 `unit` 分開統計。
- Scale 優先序為 metadata scale、per-image manual override、batch manual default、px；metadata scale 不可手動覆寫。

## GUI 風格與佈局

GUI 風格參考 `/Users/lesterc/Project/Denoiser` 的深色現代桌面 UI，但只借鑑風格，不借功能流程。目前已套用 Denoiser-like 深色 sidebar、深色 preview workspace、8 px radius、藍色 primary action、status card、modern data grid 風格。

視窗行為：

- 啟動後預設最大化。
- 不使用 slider / splitter bar 作為核心互動。
- 深色主題。
- 左側 file queue / control panel。
- 右側 image workspace。
- Image workspace 使用固定 size hint 與 keep-aspect-ratio drawing，切換 Original / Result / Debug 不應改變視窗比例。
- Result View overlay 使用 display-resolution drawing，避免線條與文字被影像縮放放大到模糊。
- Box Plot 使用 display-resolution drawing，避免固定 pixmap 放大造成字體模糊；左側 y-axis 顯示數值刻度與 horizontal grid lines，x-axis 以兩層 label 顯示，Group label 對齊各 bucket，measurement type label 對齊該 type 的 group cluster 中央。
- 8 px radius。
- Primary action 使用藍色。
- 狀態資訊放在左側底部 status card。

主要 layout：

```text
左側 File Queue Panel:
- Add Images
- nm / pixel
- min area ratio (%)
- Measure Current
- Export
- Group input / Set Group
- file table
- status card

右側 Image Workspace:
- view mode controls
- image preview / result / box plot / debug
```

File table 使用 modern data grid 形式，不做傳統 spreadsheet 感的表格。

可見欄位：

```text
Image
```

Image cell 上下兩段顯示：

```text
01_single_metal_island.tif
Default
Custom ROI · Measured
Not exported
```

使用者直接點 row 進行單選；需要批量 Set Group 時使用 Shift / Cmd / Ctrl 多選。File table 不允許直接編輯 cell。

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
- multi-page TIFF / unsupported `.dm3` shape / 3D stack 載入時直接拒絕，不加入 file queue。
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
2. 在 file table 上方的 Group input 輸入 group name
3. 按 Set Group
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

Scale 先以 batch default manual scale 覆蓋同一批沒有 metadata 的圖片；需要時可對單張圖片輸入不同 manual scale 當 override。GUI 左側的 `nm / pixel` 欄位顯示目前選取圖片實際使用的 scale 狀態；切換圖片時，欄位跟著目前選取圖片更新。

Scale 優先順序：

```text
1. metadata nm/pixel per image
2. manual nm/pixel override for this image
3. batch manual nm/pixel default
4. px
```

規則：

- 圖片有 metadata scale 時，直接採用 metadata scale，欄位顯示該值並設為不可編輯。
- 圖片沒有 metadata scale 時，欄位保持可編輯。
- 第一個有效 manual nm/pixel 會成為 batch manual default，套用到所有沒有 metadata、也沒有單張 override 的圖片。
- batch manual default 已存在後，若對某張圖片輸入不同值，該圖使用 per-image manual override。
- 使用者清空欄位後，會清除該圖的 per-image override；如果 batch manual default 存在，該圖回到 batch default，否則回到 px。
- 圖片沒有 metadata scale、也沒有 batch manual default 或 per-image override 時，該圖仍可量測，輸出 px。
- 量測結果內部永遠保存 value_px 與線段座標 px。
- 顯示、box plot、Excel export 時再依每張圖片當下 scale 轉成 nm 或維持 px。
- 改 batch manual default 或單張 manual override 不改 measurement geometry。
- 改 batch manual default 或單張 manual override 不需要重新 Measure，也不把圖片狀態改成 Needs remeasure。
- Result View 數值、Box Plot、Export 都使用每張圖片當下最新 scale。
- Trace Sheet 記錄 export 當下使用的 `scale_source` / `scale_nm_per_px`。

GUI 需要顯示目前選取圖片使用的 scale value 與欄位是否可編輯。Trace Sheet 記錄 scale source 方便追查。

Manual `nm / pixel` 輸入驗證：

- 只有圖片沒有 metadata scale 時才允許輸入 manual scale。
- 空白代表清除該圖的 per-image override；若沒有 batch manual default，該圖使用 px。
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

歷史脈絡：multi-shape ROI Union 是建立在穩定 rectangle ROI workflow 之上的後續擴充。這代表目前文件保留先前穩定的 rectangle ROI baseline，同時記錄後續新增的 polygon ROI Shape 與多 ROI Shape union 能力；不是把歷史改寫成 multi-shape ROI 一開始就存在。

- 每張圖可有多個 rectangle / polygon ROI Shapes。
- 沒有 ROI 時，Measure Current 直接分析全圖。
- 有 ROI 時，只分析 ROI Union 內。
- Rectangle mode 用拖拉建立 rectangle ROI Shape；Polygon mode 用 left-click 加 vertices、double-click 完成 polygon ROI Shape。
- incomplete polygon drawing 不會加入 ROI Union，也不會影響 Measure Current。
- 拖拉新 rectangle ROI 或完成 polygon ROI 會加入 ROI Union，不取代既有 ROI Shape。
- 可 Undo ROI，移除最近完成的 ROI Shape，不論是 rectangle 或 polygon。
- 可 Clear ROI，清除全部 ROI Shapes。
- ROI geometry 必須 clamp 在影像範圍內，不能超出影像。
- ROI 太小時，Measure Current 不執行。
- ROI 太小不改成 Failed，因為這不是 algorithm failure。
- ROI 太小時，Measure 狀態維持 Pending，左側 status card 顯示 `ROI is too small.`。
- 已量測圖片若 ROI 改變、Undo ROI 或 Clear ROI，直接刪除舊 measurement result。
- 刪除舊 result 後，Measure 狀態回到 Pending，Export 狀態回到 Not exported。

MVS ROI 編輯限制：

- 不支援移動或調整既有 ROI Shapes：已完成的 ROI Shape 不能移動或調整大小。
- 不支援任意刪除單一 shape：不能任意刪除指定的單一 ROI Shape，只能用 Undo ROI 移除最近完成的 ROI Shape，或用 Clear ROI 清除全部 ROI Shapes。
- 不支援 vertex editing：polygon ROI Shape 完成後不能編輯 vertex。
- 不支援 subtractive ROI：ROI Union 只支援加入 ROI Shape，不支援扣除區域。

ROI 顯示規則：

- Original / ROI 編輯狀態會顯示所有 rectangle / polygon ROI Shapes；拖拉 rectangle 中會顯示即時 ROI preview，polygon 繪製中會顯示目前 polyline。ROI 只畫輪廓，不用填色遮住影像內容。
- Result View 不顯示 ROI。
- 匯出的 Result Image 不顯示 ROI。
- Debug View 可以顯示 ROI。

TODO：

- 可點選 touching-boundary metal，決定是否保留。

## 影像處理流程

每張圖片的 MVS 流程：

```text
讀取影像
→ 取得 scale：metadata / manual override / manual default / px
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
1. 排除 area < HARD_MIN_COMPONENT_AREA_PX 的 components
2. HARD_MIN_COMPONENT_AREA_PX = 100
3. 從剩餘 components 計算 median area
4. 排除 area < median_area * MIN_AREA_RATIO_TO_MEDIAN 的 components
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

## Boundary-Touch 排除規則

如果 component 接觸 analysis boundary，MVS 先排除不量。

規則：

```text
component 接觸或距離 effective analysis boundary <= 1 px
```

就視為 touching boundary。

有 ROI 時：

- analysis boundary = 實際 selected ROI mask edge。
- 多個 rectangle / polygon ROI Shapes 時，ROI Union 內每個 selected mask edge 都會視為 boundary。

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

## 量測類型

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
metal island bottom 5% height region 內的水平最大寬度
```

流程：

```text
1. 取得 refined boundary bounding box
2. 定義 bottom 5% 高度範圍
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

顯示線：

```text
left endpoint.x  = left_refined_bbox.x_max
right endpoint.x = right_refined_bbox.x_min
y                = pair 的兩條 TCD blue Measurement Lines 中間 y
```

這讓 Result View 的 Horizontal Space 線段維持在 pair 的兩條 TCD blue Measurement Lines 之間，避免 tapered Metal Island 的 bbox 最寬處把粉紅線拉到中段或下段。reported value 仍使用 refined bbox horizontal gap；顯示線只借用 TCD 的 y 位置，不借用 TCD 的 x 端點。

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

## 輸出名詞

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

## 預覽模式

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

Debug View / Debug Image 的 diagnostic drawing rules 由 `debug_render.py` 共用；匯出 Result Image 的 official Measurement Lines rendering 由 `result_render.py` 共用。這樣做的原因是 GUI diagnostic display 與 Export artifact 需要一致；取捨是 PySide6 QImage rendering 相關邏輯會集中在這兩個 module，而不是全部留在 `app.py` 或 `export.py`。

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
- x-axis 排序為 measurement type 優先、Group 次之，例如 `EF TCD` 後面接 `LF TCD`，再接 `EF BCD` / `LF BCD`。
- 顯示 TCD、BCD、Height、Horizontal Space、Vertical Space 中目前有 successful final measurements 且 checkbox 已勾選的項目。
- All checkbox 與 TCD、BCD、Height、Horizontal Space、Vertical Space checkbox 預設全選；取消勾選只影響 GUI Box Plot preview，不影響 Result View / Export / Excel。
- 顯示 raw points with jitter。
- 左側 y-axis 顯示清楚數值刻度與 horizontal grid lines，不在 plot 左上角重複顯示 range 文字。
- 顯示 summary/status panel，包含 measurement count、unit、Groups、measurement types，或 empty/no-selected/mixed-unit warning。
- Group 改變後會直接刷新，不需要重測。
- batch manual default 或單張 manual override 改變後會直接刷新，不需要重測。
- 如果同一個 Box Plot preview 會混合 nm 與 px，顯示 warning，不畫 mixed-unit plot。

Group filter 尚未實作：

- 未來可用 checkbox / chips 選擇要顯示哪些 group。
- Default 是一般 group，預設顯示。
- 可勾選 / 取消任何 group。

Box plot layout：

```text
TCD cluster            BCD cluster            Height cluster ...
EF | LF                EF | LF                EF | LF
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
roi_shape_count
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
roi_shape_count = 0
```

有一個或多個 completed ROI Shapes：

```text
roi_type = union
roi_x_px = ROI Union bounding box left
roi_y_px = ROI Union bounding box top
roi_width_px = ROI Union bounding box width
roi_height_px = ROI Union bounding box height
roi_shape_count = completed ROI Shape count
```

Trace Sheet 不儲存完整 rectangle / polygon coordinates，避免把 Excel 變成 geometry serialization format。ROI 只限制 Analysis Region，不是報告統計單位；Summary / Measurements 仍依 image、Group、measurement type、target ID、unit 組織，不依 ROI Shape 拆分。

## 檔案匯出

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

如果目標檔案已有舊結果，Export 會先顯示一個整批 overwrite confirmation dialog：

- 偵測到既有檔案時，不會先寫入或覆蓋任何 artifact。
- 使用者按 `Cancel` 時，整次 Export 取消，Export 狀態不改變。
- 使用者按 `Overwrite` 時，整批輸出繼續並覆蓋既有 target files。
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
- 改 batch manual default 或單張 manual override 不需要重測；Result View、Box Plot、Export 都用該圖片當下最新 scale 轉換，Trace Sheet 記錄 export 當下的 scale。
- ROI 改變、Undo ROI 或 Clear ROI 後直接刪除舊 measurement result，Measure 狀態回到 Pending，Export 狀態回到 Not exported。
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
- Manual `nm / pixel` 只在圖片沒有 metadata scale 時可編輯；第一個有效 manual 值會成為 batch default，後續對單張輸入不同值會成為該圖 override；空白會清除該圖 override，若沒有 batch default 才回到 px；只接受正數，可輸入小數；`0`、負數、非數字不套用並顯示 inline error。
- ROI geometry 必須 clamp 在影像範圍內；ROI Union 太小時 Measure Current 不執行，且不把圖片狀態改成 Failed。
- Measure Current 若失敗，GUI 停在 Original，不自動切 Debug View；file table 顯示 Failed，左側 status card 顯示 failure reason。
- Failed 圖片不寫入 Trace Sheet；failure reason 只保留在 GUI status card / Debug View。
- 只有產生的 final measurements 會進輸出；沒有 pair candidate 或沒有 valid pair 時，不補 missing Space row，也不進任何輸出。
- Trace Sheet 的 refinement summary 對 TCD / BCD / Height 使用單顆 Metal Island 統計；對 Horizontal Space / Vertical Space 使用 pair 兩顆 Metal Island 的合併統計。
- ROI 太小時 Measure Current 不執行，Measure 狀態維持 Pending，status card 顯示 `ROI is too small.`；若 ROI 已改變，舊 result 仍依規則刪除。
- Add Images 完成後 status card 顯示 added / skipped summary；skipped files 顯示原因類型與數量，不逐檔跳 dialog。
- Export 完成後 status card 顯示 exported / skipped summary；若沒有 skipped files，只顯示 exported measured image count。

## 後續 TODO

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
