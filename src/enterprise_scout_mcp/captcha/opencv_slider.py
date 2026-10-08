"""Optional OpenCV gap detection for slider captchas — architecture §OpenCV滑块定位."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SliderGapResult:
    ok: bool
    offset_px: int = 0
    message: str = ""


def opencv_available() -> bool:
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401

        return True
    except ImportError:
        return False


def detect_slider_gap(
    background: Path | bytes,
    *,
    template: Path | bytes | None = None,
) -> SliderGapResult:
    """
    Find horizontal offset of the slider puzzle gap.

    When OpenCV is not installed, returns ok=False with install hint.
    With OpenCV: template-match if template given, else Canny+contour heuristic on bg.
    """
    if not opencv_available():
        return SliderGapResult(
            ok=False,
            message="opencv not installed — pip install -e '.[captcha]'",
        )
    import cv2
    import numpy as np

    bg = _load_bgr(background)
    if bg is None:
        return SliderGapResult(ok=False, message="failed to decode background image")

    if template is not None:
        tpl = _load_bgr(template)
        if tpl is None:
            return SliderGapResult(ok=False, message="failed to decode template image")
        res = cv2.matchTemplate(bg, tpl, cv2.TM_CCOEFF_NORMED)
        _min_val, _max_val, _min_loc, max_loc = cv2.minMaxLoc(res)
        return SliderGapResult(ok=True, offset_px=int(max_loc[0]), message="template match")

    # Heuristic: leftmost bright gap edge in edge map (common for simple sliders)
    gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    cols = np.sum(edges, axis=0)
    if cols.size == 0:
        return SliderGapResult(ok=False, message="empty edge map")
    # Prefer columns in the left 70% with strong vertical energy
    limit = max(1, int(cols.size * 0.7))
    region = cols[:limit]
    offset = int(np.argmax(region))
    if region[offset] <= 0:
        return SliderGapResult(ok=False, message="no gap candidate")
    return SliderGapResult(ok=True, offset_px=offset, message="canny heuristic")


def _load_bgr(src: Path | bytes) -> Any:
    import cv2
    import numpy as np

    if isinstance(src, Path):
        data = np.fromfile(str(src), dtype=np.uint8)
    else:
        data = np.frombuffer(src, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)
