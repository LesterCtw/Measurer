from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_project_file(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_documents_roi_editing_limits_for_mvs():
    readme = _read_project_file("README.md")

    assert "no moving/resizing" in readme
    assert "no arbitrary shape deletion" in readme
    assert "no vertex editing" in readme
    assert "no subtractive ROI" in readme


def test_readme_preserves_stable_rectangle_roi_baseline_context():
    readme = _read_project_file("README.md")

    assert "stable rectangle ROI workflow" in readme
    assert "layered on top" in readme


def test_context_documents_roi_union_domain_language():
    context = _read_project_file("CONTEXT.md")

    assert "**ROI Shape**:\nOne completed user-drawn rectangle or polygon" in context
    assert "**ROI Union**:\nThe pixel union of all completed ROI Shapes" in context
    assert (
        "An **Analysis Region** is either the full **STEM ZC Image** "
        "or the inside of the **ROI Union**."
    ) in context
    assert "A **ROI** limits analysis but does not create separate summaries by itself." in context


def test_readme_documents_roi_union_reporting_display_and_trace_behavior():
    readme = _read_project_file("README.md")

    assert "沒有 ROI 時，Measure Current 直接分析全圖" in readme
    assert "ROI 只限制 Analysis Region，不是 reporting unit" in readme
    assert "不依 ROI Shape 拆分" in readme
    assert "roi_type = full_image" in readme
    assert "roi_shape_count = 0" in readme
    assert "roi_type = union" in readme
    assert "ROI Union bounding box" in readme
    assert "Original / ROI editing state 會顯示所有 rectangle / polygon ROI Shapes" in readme
    assert "Result View 不顯示 ROI" in readme
    assert "exported Result Image 不顯示 ROI" in readme
    assert "Debug View 可以顯示 ROI" in readme
