# Measurer Context

Measurer supports engineers measuring MOM structure dimensions in STEM ZC images. The context language is about the image features, measurement targets, and how those targets are interpreted by engineers.

## Language

**STEM ZC Image**:
A grayscale microscopy image where MOM metal appears bright and LK appears dark.
_Avoid_: photo, picture

**Metal Island**:
A connected bright MOM metal feature that can produce one TCD, one BCD, and one Height measurement.
_Avoid_: blob, object, component

**LK**:
The dark low-k region between metal islands.
_Avoid_: background, gap material

**Analysis Region**:
The part of an image considered for automatic metal detection and measurement.
_Avoid_: output unit, result group

**ROI**:
A user-drawn region that limits the Analysis Region but is not itself a reporting unit.
_Avoid_: sample, measurement group

**ROI Shape**:
One completed user-drawn rectangle or polygon that contributes pixels to the ROI Union.
_Avoid_: result shape, report unit

**ROI Union**:
The pixel union of all completed ROI Shapes on one STEM ZC Image. Incomplete polygon drawing is not part of the ROI Union.
_Avoid_: separate ROI results, shape list

**Refined Boundary**:
The final ordered closed boundary used for official measurements, derived from local image intensity transition rather than directly from the Otsu contour.
_Avoid_: Otsu boundary, mask contour

**Rough Boundary Fallback**:
A local substitute point from the rough boundary used when a refined boundary point cannot be reliably found.
_Avoid_: final Otsu boundary

**TCD**:
The maximum horizontal width of a Metal Island within its top 20% height region.
_Avoid_: top width

**BCD**:
The maximum horizontal width of a Metal Island within its bottom 5% height region.
_Avoid_: bottom width

**Height**:
The maximum vertical chord length inside a Metal Island Refined Boundary.
_Avoid_: bounding-box height

**Horizontal Space**:
The left-right spacing between adjacent Metal Islands in the same row, measured from their Refined Boundary horizontal extents.
_Avoid_: Space scan

**Vertical Space**:
The up-down spacing between adjacent Metal Islands in the same column, measured as the minimum vertical boundary-to-boundary gap over their shared x-range.
_Avoid_: vertical bounding-box gap

**Measurement Line**:
The final line segment whose length becomes one reported measurement value.
_Avoid_: raw scan line

**Measurement Status**:
Whether a final measurement produced a reportable value, independent of diagnostic quality indicators.
_Avoid_: quality score, confidence

**Result View**:
The GUI view that shows the original image with final Measurement Lines and values.
_Avoid_: overlay

**Result Image**:
The exported report image that shows the original image with final Measurement Lines and values.
_Avoid_: annotated image

**Debug View**:
The GUI view used to inspect segmentation, boundaries, grouping, and rejected candidates.
_Avoid_: result view

**Debug Image**:
The exported diagnostic image used to inspect algorithm behavior.
_Avoid_: result image

**Trace Sheet**:
The Excel sheet that stores secondary data needed to trace a measurement back to pixels, scale, ROI, and failure reason.
_Avoid_: details sheet

**Group**:
A user-assigned category used to compare distributions across images.
_Avoid_: tag, class, folder

## Relationships

- A **STEM ZC Image** contains zero or more **Metal Islands**.
- An **Analysis Region** is either the full **STEM ZC Image** or the inside of the **ROI Union**.
- A **ROI Shape** is one completed rectangle or polygon.
- A **ROI Union** contains the pixels selected by one or more completed **ROI Shapes**.
- A **ROI** limits analysis but does not create separate summaries by itself.
- A **Metal Island** has one **Refined Boundary**.
- A **Refined Boundary** may contain **Rough Boundary Fallback** points when local refinement is unreliable.
- A **Metal Island** can produce one **TCD**, one **BCD**, and one **Height**.
- Adjacent **Metal Islands** in the same row can produce **Horizontal Space**.
- Adjacent **Metal Islands** in the same column can produce **Vertical Space**.
- A **Measurement Line** represents one final TCD, BCD, Height, Horizontal Space, or Vertical Space value.
- A **Measurement Status** reports value availability; fallback ratio and other diagnostics belong to the **Trace Sheet**.
- A **Result View** and **Result Image** show official measurements without ROI or debug internals.
- A **Debug View** and **Debug Image** show algorithm internals and may show ROI.
- A **Trace Sheet** stores secondary measurement context that does not belong in the main Measurements sheet.
- A **Group** contains one or more images, and each image belongs to exactly one **Group**.

## Example dialogue

> **Dev:** "If the user draws two ROIs, should Summary show two rows for the same image?"
> **Domain expert:** "No. ROI only defines the Analysis Region. The reported measurements still belong to the image and its Group."

> **Dev:** "Can we use the Otsu contour as the metal edge?"
> **Domain expert:** "No. Otsu only gives the rough mask. Official TCD, BCD, Height, and Space measurements must use the Refined Boundary."

## Flagged ambiguities

- "Space" can mean either **Horizontal Space** or **Vertical Space**. Resolved: use the explicit terms when discussing measurement logic, because they intentionally use different rules.
- "Height" must not mean bounding-box y-extent. Resolved: **Height** is the maximum vertical chord length inside the Refined Boundary.
- "ROI result" is misleading. Resolved: **ROI** only limits the **Analysis Region**; output is organized by image and Group.
- "Overlay", "Annotated Image", and "Details" were ambiguous UI/export names. Resolved: use **Result View**, **Result Image**, and **Trace Sheet**.
- "success" could mean either reportable value or high diagnostic quality. Resolved: **Measurement Status** `success` means a reportable value exists; fallback-heavy boundaries are still `success` and diagnostics go in the **Trace Sheet**.
