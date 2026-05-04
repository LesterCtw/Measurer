# Measurer 脈絡

Measurer 協助工程師量測 STEM ZC 影像中的 MOM 結構尺寸。這份文件固定影像特徵、量測目標，以及工程師如何解讀這些目標的用語。

## 用語

**STEM ZC Image**:
一種 grayscale microscopy image，其中 MOM metal 會呈現亮色，LK 會呈現暗色。
_避免使用_: photo, picture

**Metal Island**:
一個連續的明亮 MOM metal 特徵，可產生一筆 TCD、一筆 BCD 與一筆 Height 量測。
_避免使用_: blob, object, component

**LK**:
Metal Islands 之間的暗色 low-k 區域。
_避免使用_: background, gap material

**Analysis Region**:
影像中會被納入自動 metal 偵測與量測的區域。
_避免使用_: output unit, result group

**ROI**:
使用者繪製、用來限制 Analysis Region 的區域；ROI 本身不是報告統計單位。
_避免使用_: sample, measurement group

**ROI Shape**:
一個已完成的使用者繪製 rectangle 或 polygon，會把像素加入 ROI Union。
_避免使用_: result shape, report unit

**ROI Union**:
單張 STEM ZC Image 上所有已完成 ROI Shapes 的像素聯集。尚未完成的 polygon drawing 不屬於 ROI Union。
_避免使用_: separate ROI results, shape list

**Refined Boundary**:
正式量測使用的最終有序閉合邊界；它來自局部影像亮度轉換，不直接使用 Otsu contour。
_避免使用_: Otsu boundary, mask contour

**Rough Boundary Fallback**:
當 refined boundary point 無法可靠找到時，使用 rough boundary 上的局部替代點。
_避免使用_: final Otsu boundary

**TCD**:
Metal Island 頂部 20% 高度範圍內的最大水平寬度。
_避免使用_: top width

**BCD**:
Metal Island 底部 5% 高度範圍內的最大水平寬度。
_避免使用_: bottom width

**Height**:
Metal Island Refined Boundary 內的最大垂直 chord length。
_避免使用_: bounding-box height

**Horizontal Space**:
同一 row 中相鄰 Metal Islands 的左右間距，使用兩者 Refined Boundary 的水平範圍量測。
_避免使用_: Space scan

**Vertical Space**:
同一 column 中相鄰 Metal Islands 的上下間距，使用 shared x-range 內最小的垂直 boundary-to-boundary gap。
_避免使用_: vertical bounding-box gap

**Measurement Line**:
最終線段，其長度會成為一筆報告量測值。
_避免使用_: raw scan line

**Measurement Status**:
最終量測是否產生可報告的值；此狀態獨立於診斷品質指標。
_避免使用_: quality score, confidence

**Result View**:
GUI 中顯示原圖、最終 Measurement Lines 與數值的畫面。
_避免使用_: overlay

**Result Image**:
匯出的報告用圖片，顯示原圖、最終 Measurement Lines 與數值。
_避免使用_: annotated image

**Debug View**:
GUI 中用來檢查 segmentation、boundaries、grouping 與 rejected candidates 的畫面。
_避免使用_: result view

**P-Chart**:
GUI 中用常態機率尺度顯示 Group 量測分布的 normal probability plot view。
_避免使用_: proportion control chart

**Debug Image**:
匯出的診斷圖片，用來檢查演算法行為。
_避免使用_: result image

**Trace Sheet**:
Excel 中儲存次要追溯資料的 sheet，可把量測追回 pixel、scale、ROI 與 failure reason。
_避免使用_: details sheet

**Group**:
使用者指定的分類，用來比較不同圖片集合的分布。
_避免使用_: tag, class, folder

## 關係

- 一張 **STEM ZC Image** 包含零個或多個 **Metal Islands**。
- **Analysis Region** 不是完整 **STEM ZC Image**，就是 **ROI Union** 內部。
- **ROI Shape** 是一個已完成的 rectangle 或 polygon。
- **ROI Union** 包含一個或多個已完成 **ROI Shapes** 選取的像素。
- **ROI** 只限制分析範圍，本身不建立獨立 Summary。
- 一個 **Metal Island** 有一個 **Refined Boundary**。
- 當局部 refinement 不可靠時，**Refined Boundary** 可能包含 **Rough Boundary Fallback** points。
- 一個 **Metal Island** 可以產生一筆 **TCD**、一筆 **BCD** 與一筆 **Height**。
- 同一 row 中相鄰的 **Metal Islands** 可以產生 **Horizontal Space**。
- 同一 column 中相鄰的 **Metal Islands** 可以產生 **Vertical Space**。
- 一條 **Measurement Line** 代表一筆最終 TCD、BCD、Height、Horizontal Space 或 Vertical Space 數值。
- **Measurement Status** 回報量測值是否存在；fallback ratio 與其他 diagnostics 放在 **Trace Sheet**。
- **Result View** 與 **Result Image** 顯示正式量測，不顯示 ROI 或 debug internals。
- **P-Chart** 依 **Group** 與量測類型比較 successful final measurements 的常態機率分布。
- **Debug View** 與 **Debug Image** 顯示演算法內部資訊，也可以顯示 ROI。
- **Trace Sheet** 儲存不適合放在主 Measurements sheet 的次要量測脈絡。
- 一個 **Group** 包含一張或多張圖片，每張圖片剛好屬於一個 **Group**。

## 對話範例

> **Dev:** 「如果使用者畫了兩個 ROI，Summary 是否要讓同一張圖顯示兩列？」
> **Domain expert:** 「不用。ROI 只定義 Analysis Region。報告中的量測仍然屬於該圖片與它的 Group。」

> **Dev:** 「可以把 Otsu contour 當成 metal edge 嗎？」
> **Domain expert:** 「不行。Otsu 只提供 rough mask。正式 TCD、BCD、Height 與 Space 量測必須使用 Refined Boundary。」

## 已標記的模糊處

- 「Space」可能指 **Horizontal Space** 或 **Vertical Space**。決議：討論量測邏輯時使用明確名稱，因為兩者刻意使用不同規則。
- 「Height」不能代表 bounding-box y-extent。決議：**Height** 是 Refined Boundary 內的最大垂直 chord length。
- 「ROI result」容易誤導。決議：**ROI** 只限制 **Analysis Region**；輸出依 image 與 Group 組織。
- 「Overlay」、「Annotated Image」與「Details」作為 UI/export 名稱太模糊。決議：使用 **Result View**、**Result Image** 與 **Trace Sheet**。
- 「success」可能代表可報告值，也可能代表診斷品質高。決議：**Measurement Status** `success` 代表有可報告值；即使 boundary 大量使用 fallback 仍是 `success`，diagnostics 放在 **Trace Sheet**。
- 「P-Chart」在一般統計中可能指 proportion control chart。決議：Measurer 中的 **P-Chart** 固定代表 normal probability plot view。
