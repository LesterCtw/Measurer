from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_project_file(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_documents_roi_editing_limits_for_mvs():
    readme = _read_project_file("README.md")

    assert "不支援移動或調整既有 ROI Shapes" in readme
    assert "不支援任意刪除單一 shape" in readme
    assert "不支援 vertex editing" in readme
    assert "不支援 subtractive ROI" in readme


def test_readme_preserves_stable_rectangle_roi_baseline_context():
    readme = _read_project_file("README.md")

    assert "穩定 rectangle ROI workflow" in readme
    assert "後續擴充" in readme


def test_context_documents_roi_union_domain_language():
    context = _read_project_file("CONTEXT.md")

    assert "**ROI Shape**:\n一個已完成的使用者繪製 rectangle 或 polygon" in context
    assert "**ROI Union**:\n單張 STEM ZC Image 上所有已完成 ROI Shapes 的像素聯集" in context
    assert (
        "**Analysis Region** 不是完整 **STEM ZC Image**，"
        "就是 **ROI Union** 內部。"
    ) in context
    assert "**ROI** 只限制分析範圍，本身不建立獨立 Summary。" in context


def test_readme_documents_roi_union_reporting_display_and_trace_behavior():
    readme = _read_project_file("README.md")

    assert "沒有 ROI 時，Measure Current 直接分析全圖" in readme
    assert "ROI 只限制 Analysis Region，不是報告統計單位" in readme
    assert "不依 ROI Shape 拆分" in readme
    assert "roi_type = full_image" in readme
    assert "roi_shape_count = 0" in readme
    assert "roi_type = union" in readme
    assert "ROI Union bounding box" in readme
    assert "Original / ROI 編輯狀態會顯示所有 rectangle / polygon ROI Shapes" in readme
    assert "Result View 不顯示 ROI" in readme
    assert "匯出的 Result Image 不顯示 ROI" in readme
    assert "Debug View 可以顯示 ROI" in readme
