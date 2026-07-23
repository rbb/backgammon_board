#!/usr/bin/env python3
"""Recreate ``backgammon_board_v2.svg`` using svgwrite."""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import argcomplete
import svgwrite

from build_hex_rosette import HexRosetteParams, add_hex_rosette, filled_band_path


DEFAULT_OUTPUT = Path("backgammon_board.svg")
SVG_SIZE = (600, 450)
DEFAULT_CHECKER_SIZE = 32.0
DEFAULT_TEMPLATE_MARGIN = 0.5
DEFAULT_TEMPLATE_ARC_RATIO = 1 / 6
DEFAULT_PIP_ENGRAVE_WIDTH = 2.0
DEFAULT_ROSETTE_ENGRAVE_WIDTH = 1.0
ROSETTE_SETS = 21
LINE_WIDTH = 0.301517
PIP_BASE_LEFT = 55.769252
PIP_BASE_TOP_Y = 117.47435
PIP_BASE_STEP_Y = 9.25007
PIP_BASE_RIGHT = 88.467736
PIP_FLAT_BASE_CENTER = (
    (PIP_BASE_LEFT + PIP_BASE_RIGHT) / 2,
    PIP_BASE_TOP_Y + PIP_BASE_STEP_Y,
)
PIP_BASE_TIP_DEPTH = 9.43924
PIP_INNER_TRANSFORM = "matrix(1.0255001,0,0,1.09107,-0.93079144,-13.422)"
# The five nested hexagons in every point, ordered from the board edge inward.
ETCH_PATHS = (
    (
        "m 84.750403,111.88095 -6.845439,11.85665 -13.690879,0 "
        "-6.845439,-11.85665 6.845439,-11.85665 13.690879,0 z",
        "rotate(90,67.748742,115.19174)",
        "0.264583",
    ),
    (
        "M 83.381315,89.353317 77.22042,100.0243 H 64.898629 "
        "L 58.737734,89.353317 64.898629,78.682333 H 77.22042 Z",
        "rotate(90,69.49126,90.921584)",
        "0.238125",
    ),
    (
        "m 82.149137,69.078445 -5.544806,9.603886 H 65.514719 "
        "l -5.544806,-9.603886 5.544806,-9.603885 h 11.089612 z",
        "rotate(90,71.059525,69.078447)",
        "0.214312",
    ),
    (
        "M 81.040175,50.831062 76.04985,59.47456 h -9.980651 "
        "l -4.990325,-8.643498 4.990325,-8.643497 9.980651,0 z",
        "rotate(90,72.470965,49.419624)",
        "0.192881",
    ),
    (
        "m 80.04211,34.408417 -4.491293,7.779147 -8.982585,0 "
        "-4.491293,-7.779147 4.491293,-7.779148 8.982585,0 z",
        "rotate(90,73.741261,31.726683)",
        "0.173593",
    ),
)
CUT_PATH = (
    "m 55.769252,117.47435 v 9.25007 l 16.349243,9.43924 "
    "16.349241,-9.43924 v -9.25007 M 61.214034,8.9758763 "
    "71.940767,2.7827927 82.667506,8.9758775 m -2e-6,-1.2e-6 "
    "5.800232,108.4984737 M 61.214034,8.9758763 55.769252,117.47435"
)
PIP_CUT_BOUNDS = (55.769252, 2.7827927, 88.467736, 136.16366)

TOP_PIP_TRANSFORMS = (
    "matrix(1,0,0,-1.2428528,-27.238635,199.40949)",
    "matrix(1,0,0,-1.2428528,5.9598539,199.40949)",
    "matrix(1,0,0,-1.2428528,39.158334,199.40949)",
    "matrix(1,0,0,-1.2428528,72.356829,199.40949)",
    "matrix(1,0,0,-1.2428528,105.55531,199.40949)",
    "matrix(1,0,0,-1.2428528,138.75378,199.40949)",
    "matrix(1,0,0,-1.2428528,203.9539,199.38146)",
    "matrix(1,0,0,-1.2428528,237.15239,199.38146)",
    "matrix(1,0,0,-1.2428528,270.35087,199.38146)",
    "matrix(1,0,0,-1.2428528,303.54936,199.38146)",
    "matrix(1,0,0,-1.2428528,336.74785,199.38146)",
    "matrix(1,0,0,-1.2428528,369.94631,199.38146)",
)
BOTTOM_BOARD_TRANSFORM = "matrix(1,0,0,-1,-291.27935,546.7251)"
BOTTOM_PIP_TRANSFORMS = (
    "matrix(1,0,0,-1.2428528,264.07377,317.57232)",
    "matrix(1,0,0,-1.2428528,297.27226,317.57232)",
    "matrix(1,0,0,-1.2428528,330.47074,317.57232)",
    "matrix(1,0,0,-1.2428528,363.66923,317.57232)",
    "matrix(1,0,0,-1.2428528,396.86771,317.57232)",
    "matrix(1,0,0,-1.2428528,430.06618,317.57232)",
    "matrix(1,0,0,-1.2428528,495.2663,317.54429)",
    "matrix(1,0,0,-1.2428528,528.46479,317.54429)",
    "matrix(1,0,0,-1.2428528,561.66328,317.54429)",
    "matrix(1,0,0,-1.2428528,594.86176,317.54429)",
    "matrix(1,0,0,-1.2428528,628.06025,317.54429)",
    "matrix(1,0,0,-1.2428528,661.25871,317.54429)",
)

# (board side, one-based position from the left, checker count)
#
# The nearest checker is tangent to the pip's flat base and sloped sides at
# the widest point; the rest are separated by exactly one checker diameter.
CHECKER_STACKS = (
    ("top", 1, 5),
    ("top", 4, 3),
    ("top", 7, 5),
    ("bottom", 12, 2),
    ("bottom", 1, 5),
    ("bottom", 4, 3),
    ("bottom", 7, 5),
    ("top", 12, 2),
)


def pip_number(side: str, position: int) -> int:
    """Return standard backgammon numbering for a left-to-right row position."""
    if side == "bottom":
        return 13 - position
    if side == "top":
        return 12 + position
    raise ValueError("side must be 'top' or 'bottom'")


def add_layer(drawing: svgwrite.Drawing, identifier: str, label: str) -> svgwrite.container.Group:
    """Create an Inkscape-compatible layer."""
    layer = drawing.g(id=identifier, style="display:inline")
    layer.attribs.update(
        {"inkscape:groupmode": "layer", "inkscape:label": label}
    )
    drawing.add(layer)
    return layer


def scale_factor(checker_size: float) -> float:
    """Return the scale relative to the original 32 mm checker design."""
    return checker_size / DEFAULT_CHECKER_SIZE


def board_height_expansion(checker_size: float, rosette_ratio: float) -> float:
    """Return the extra board height needed for the requested rosette diameter."""
    return max(0.0, checker_size * (rosette_ratio - 1.0))


def side_vertical_offset(
    side: str, checker_size: float, rosette_ratio: float
) -> float:
    """Move each board side away from the center by half the added height."""
    expansion = board_height_expansion(checker_size, rosette_ratio)
    return (-expansion / 2) if side == "top" else (expansion / 2)


def line_style(color: str = "#000000") -> str:
    return (
        f"fill:none;stroke:{color};stroke-width:{LINE_WIDTH:g};"
        "stroke-linecap:butt;stroke-linejoin:miter;stroke-opacity:1;"
        "vector-effect:non-scaling-stroke"
    )


def cut_style(color: str = "#000000") -> str:
    return line_style(color)


def checker_style(color: str = "#000000") -> str:
    return f"display:inline;{line_style(color)}"


def filled_engrave_style() -> str:
    return "fill:#ff0000;fill-opacity:1;stroke:none"


def alternating_pip_engrave_width(
    side: str,
    pip_index: int,
    pip_engrave_width: float,
) -> float:
    """Return thick/thin widths with opposing top/bottom parity."""
    if side not in ("top", "bottom"):
        raise ValueError("side must be 'top' or 'bottom'")
    thick = (pip_index % 2 == 0) if side == "top" else (pip_index % 2 == 1)
    return pip_engrave_width if thick else pip_engrave_width / 3


_PATH_TOKEN = re.compile(
    r"[MmLlHhVvZz]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
)


def _path_subpaths(
    path_data: str,
) -> tuple[tuple[tuple[tuple[float, float], ...], bool], ...]:
    """Parse the M/L/H/V/Z subset used by the board pip paths."""
    tokens = _PATH_TOKEN.findall(path_data)
    subpaths: list[tuple[tuple[float, float], ...]] = []
    closed: list[bool] = []
    points: list[tuple[float, float]] = []
    current = (0.0, 0.0)
    command = ""
    index = 0

    def finish(is_closed: bool = False) -> None:
        nonlocal points
        if points:
            subpaths.append(tuple(points))
            closed.append(is_closed)
            points = []

    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command in "Zz":
                finish(True)
                command = ""
                continue

        if command in "Mm":
            if points:
                finish()
            x, y = float(tokens[index]), float(tokens[index + 1])
            index += 2
            if command == "m":
                x += current[0]
                y += current[1]
            current = (x, y)
            points.append(current)
            command = "l" if command == "m" else "L"
        elif command in "Ll":
            x, y = float(tokens[index]), float(tokens[index + 1])
            index += 2
            if command == "l":
                x += current[0]
                y += current[1]
            current = (x, y)
            points.append(current)
        elif command in "Hh":
            x = float(tokens[index])
            index += 1
            if command == "h":
                x += current[0]
            current = (x, current[1])
            points.append(current)
        elif command in "Vv":
            y = float(tokens[index])
            index += 1
            if command == "v":
                y += current[1]
            current = (current[0], y)
            points.append(current)
        else:
            raise ValueError(f"Unsupported SVG path command in: {path_data}")

    finish()
    return tuple(zip(subpaths, closed))


def _transform_subpaths(
    path_data: str,
    matrix: tuple[float, float, float, float, float, float],
) -> tuple[tuple[tuple[tuple[float, float], ...], bool], ...]:
    return tuple(
        (tuple(_transform_point(matrix, point) for point in points), is_closed)
        for points, is_closed in _path_subpaths(path_data)
    )


def add_pip(
    etch_parent: svgwrite.container.Group,
    cut_parent: svgwrite.container.Group,
    identifier: str,
    matrix: tuple[float, float, float, float, float, float],
    pip_engrave_width: float,
    cut: bool,
) -> None:
    etch_pip = svgwrite.container.Group(id=identifier, debug=False)
    inner_matrix = _matrix(PIP_INNER_TRANSFORM)
    for path_index, (path_data, path_transform, _) in enumerate(ETCH_PATHS, start=1):
        path_matrix = _compose_matrices(
            matrix,
            _compose_matrices(inner_matrix, _rotation_matrix(path_transform)),
        )
        etch_pip.add(
            svgwrite.path.Path(
                id=f"path_{identifier}_engrave_{path_index}",
                d=filled_band_path(
                    _transform_subpaths(path_data, path_matrix),
                    pip_engrave_width,
                ),
                style=filled_engrave_style(),
                fill_rule="evenodd",
                debug=False,
            )
        )
    etch_parent.add(etch_pip)

    cut_pip = svgwrite.container.Group(id=f"{identifier}_cut", debug=False)
    if cut:
        cut_path = svgwrite.path.Path(
            id=f"path_{identifier}_cut",
            d=CUT_PATH,
            transform=_matrix_string(matrix),
            style=cut_style(),
            debug=False,
        )
    else:
        cut_path = svgwrite.path.Path(
            id=f"path_{identifier}_engrave_outline",
            d=filled_band_path(
                _transform_subpaths(CUT_PATH, matrix),
                pip_engrave_width,
            ),
            style=filled_engrave_style(),
            fill_rule="evenodd",
            debug=False,
        )
    cut_pip.add(cut_path)
    cut_parent.add(cut_pip)


def _matrix(transform: str) -> tuple[float, float, float, float, float, float]:
    values = tuple(float(value) for value in re.findall(r"[-+]?\d*\.?\d+", transform))
    if len(values) != 6:
        raise ValueError(f"Expected a six-value SVG matrix: {transform}")
    return values  # type: ignore[return-value]


def _rotation_matrix(
    transform: str,
) -> tuple[float, float, float, float, float, float]:
    values = tuple(
        float(value)
        for value in re.findall(
            r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?",
            transform,
        )
    )
    if not transform.strip().startswith("rotate(") or len(values) not in (1, 3):
        raise ValueError(f"Expected an SVG rotate transform: {transform}")
    angle = math.radians(values[0])
    cosine, sine = math.cos(angle), math.sin(angle)
    center_x, center_y = values[1:] if len(values) == 3 else (0.0, 0.0)
    return (
        cosine,
        sine,
        -sine,
        cosine,
        center_x - cosine * center_x + sine * center_y,
        center_y - sine * center_x - cosine * center_y,
    )


def _compose_matrices(
    outer: tuple[float, float, float, float, float, float],
    inner: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    a, b, c, d, e, f = outer
    g, h, i, j, k, l = inner
    return (
        a * g + c * h,
        b * g + d * h,
        a * i + c * j,
        b * i + d * j,
        a * k + c * l + e,
        b * k + d * l + f,
    )


def _transform_point(
    matrix: tuple[float, float, float, float, float, float],
    point: tuple[float, float],
) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


def _matrix_string(matrix: tuple[float, float, float, float, float, float]) -> str:
    return "matrix(" + ",".join(f"{value:g}" for value in matrix) + ")"


def _pip_matrix(
    side: str,
    pip_index: int,
    checker_size: float,
    rosette_ratio: float = 1.0,
) -> tuple[float, float, float, float, float, float]:
    """Return a pip transform scaled in board space around the origin."""
    transforms = TOP_PIP_TRANSFORMS if side == "top" else BOTTOM_PIP_TRANSFORMS
    matrix = _matrix(transforms[pip_index - 1])
    if side == "bottom":
        matrix = _compose_matrices(_matrix(BOTTOM_BOARD_TRANSFORM), matrix)
    scale = scale_factor(checker_size)
    return _compose_matrices(
        (
            scale,
            0,
            0,
            scale,
            0,
            side_vertical_offset(side, checker_size, rosette_ratio),
        ),
        matrix,
    )


def pip_cut_bounds(
    side: str,
    pip_index: int,
    checker_size: float = DEFAULT_CHECKER_SIZE,
    rosette_ratio: float = 1.0,
) -> tuple[float, float, float, float]:
    """Return the board-space bounding box of a pip's cut path."""
    matrix = _pip_matrix(side, pip_index, checker_size, rosette_ratio)
    left, top, right, bottom = PIP_CUT_BOUNDS
    corners = (
        _transform_point(matrix, (left, top)),
        _transform_point(matrix, (left, bottom)),
        _transform_point(matrix, (right, top)),
        _transform_point(matrix, (right, bottom)),
    )
    xs, ys = zip(*corners)
    return min(xs), min(ys), max(xs), max(ys)


def pip_group_cut_bounds(
    pip_indices: range,
    checker_size: float = DEFAULT_CHECKER_SIZE,
    rosette_ratio: float = 1.0,
) -> tuple[float, float, float, float]:
    """Return the board-space bounding box enclosing a six-pip group."""
    bounds = tuple(
        pip_cut_bounds(side, index, checker_size, rosette_ratio)
        for side in ("top", "bottom")
        for index in pip_indices
    )
    return (
        min(bound[0] for bound in bounds),
        min(bound[1] for bound in bounds),
        max(bound[2] for bound in bounds),
        max(bound[3] for bound in bounds),
    )


def border_rectangles(
    checker_size: float,
    rosette_ratio: float = 1.0,
) -> tuple[tuple[float, float, float, float], ...]:
    """Return inner rectangles followed by their touching outer frames."""
    inner_clearance = checker_size / 4
    outer_clearance = checker_size / 2
    inner_rectangles = []
    for pip_indices in (range(1, 7), range(7, 13)):
        left, top, right, bottom = pip_group_cut_bounds(
            pip_indices, checker_size, rosette_ratio
        )
        left -= inner_clearance
        top -= inner_clearance
        right += inner_clearance
        bottom += inner_clearance
        inner_rectangles.append((left, top, right - left, bottom - top))

    left_inner, right_inner = inner_rectangles
    outer_rectangles = tuple(
        (
            x - outer_clearance,
            y - outer_clearance,
            width + 2 * outer_clearance,
            height + 2 * outer_clearance,
        )
        for x, y, width, height in (right_inner, left_inner)
    )
    right_outer, left_outer = outer_rectangles
    right_offset = left_outer[0] + left_outer[2] - right_outer[0]

    def translate(
        rectangle: tuple[float, float, float, float], offset: float
    ) -> tuple[float, float, float, float]:
        x, y, width, height = rectangle
        return x + offset, y, width, height

    return (
        left_inner,
        translate(right_inner, right_offset),
        translate(right_outer, right_offset),
        left_outer,
    )


def pip_group_horizontal_offset(
    pip_index: int, checker_size: float, rosette_ratio: float = 1.0
) -> float:
    """Keep the left group fixed and move the right group to touch it."""
    if pip_index <= 6:
        return 0.0
    _, right_inner, _, _ = border_rectangles(checker_size, rosette_ratio)
    right_group_left, _, _, _ = pip_group_cut_bounds(
        range(7, 13), checker_size, rosette_ratio
    )
    return right_inner[0] - right_group_left + checker_size / 4


def canvas_bounds(
    checker_size: float, rosette_ratio: float = 1.0
) -> tuple[float, float, float, float]:
    """Return a canvas that includes both outer frames and the base SVG area."""
    _, _, right_outer, left_outer = border_rectangles(checker_size, rosette_ratio)
    outer_rectangles = (left_outer, right_outer)
    scale = scale_factor(checker_size)
    expansion = board_height_expansion(checker_size, rosette_ratio)
    stroke_margin = LINE_WIDTH / 2
    left = min(
        0.0, *(rectangle[0] - stroke_margin for rectangle in outer_rectangles)
    )
    expanded_top = -expansion / 2 if expansion else 0.0
    top = min(
        expanded_top,
        *(rectangle[1] - stroke_margin for rectangle in outer_rectangles),
    )
    right = max(
        SVG_SIZE[0] * scale,
        *(
            rectangle[0] + rectangle[2] + stroke_margin
            for rectangle in outer_rectangles
        ),
    )
    bottom = max(
        SVG_SIZE[1] * scale + expansion / 2,
        *(
            rectangle[1] + rectangle[3] + stroke_margin
            for rectangle in outer_rectangles
        ),
    )
    return left, top, right - left, bottom - top


def half_canvas_bounds(
    checker_size: float, rosette_ratio: float = 1.0
) -> tuple[float, float, float, float]:
    """Return the left half's outer-frame bounds."""
    _, _, _, left_outer = border_rectangles(checker_size, rosette_ratio)
    x, y, width, height = left_outer
    margin = LINE_WIDTH / 2
    return x - margin, y - margin, width + 2 * margin, height + 2 * margin


def half_centers(
    checker_size: float, rosette_ratio: float = 1.0
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return the centers of the left and right inner playing halves."""
    left_inner, right_inner, _, _ = border_rectangles(checker_size, rosette_ratio)
    return tuple(
        (x + width / 2, y + height / 2)
        for x, y, width, height in (left_inner, right_inner)
    )


def pip_anchor(
    side: str,
    pip_index: int,
    horizontal_offset: float = 0.0,
    checker_size: float = DEFAULT_CHECKER_SIZE,
    rosette_ratio: float = 1.0,
) -> tuple[float, float]:
    """Return the board-space center of a pip's flat base line."""
    matrix = _pip_matrix(side, pip_index, checker_size, rosette_ratio)
    x, y = _transform_point(matrix, PIP_FLAT_BASE_CENTER)
    return x + horizontal_offset, y


def checker_stack_translation(
    side: str,
    pip_index: int,
    checker_size: float,
    rosette_ratio: float = 1.0,
) -> float:
    """Return the shift that makes the nearest checker tangent to a pip's V base."""
    matrix = _pip_matrix(side, pip_index, checker_size, rosette_ratio)
    direction = 1 if side == "top" else -1
    endpoint = _transform_point(matrix, PIP_FLAT_BASE_CENTER)
    tip = _transform_point(
        matrix,
        (PIP_FLAT_BASE_CENTER[0], PIP_FLAT_BASE_CENTER[1] + PIP_BASE_TIP_DEPTH),
    )
    right_endpoint = _transform_point(
        matrix,
        (PIP_BASE_RIGHT, PIP_FLAT_BASE_CENTER[1]),
    )
    side_length = math.dist(tip, right_endpoint)
    half_width = abs(right_endpoint[0] - tip[0])
    tangent_center_y = tip[1] + direction * (checker_size / 2) * side_length / half_width
    return tangent_center_y - (endpoint[1] + direction * checker_size / 2)


def bottom_checker_stack_translation(
    pip_index: int, checker_size: float, rosette_ratio: float = 1.0
) -> float:
    """Return the downward shift that makes a checker tangent to the pip's V base."""
    return checker_stack_translation("bottom", pip_index, checker_size, rosette_ratio)


def checker_centers(
    side: str,
    pip_index: int,
    count: int,
    checker_size: float,
    horizontal_offset: float = 0.0,
    rosette_ratio: float = 1.0,
) -> tuple[tuple[float, float], ...]:
    """Place a stack from the pip's flat base inward at one-diameter intervals."""
    anchor_x, anchor_y = pip_anchor(
        side,
        pip_index,
        horizontal_offset=horizontal_offset,
        checker_size=checker_size,
        rosette_ratio=rosette_ratio,
    )
    direction = 1 if side == "top" else -1
    radius = checker_size / 2
    return tuple(
        (anchor_x, anchor_y + direction * (radius + index * checker_size))
        for index in range(count)
    )


def checker_template_outline(
    centers: tuple[tuple[float, float], ...],
    checker_size: float,
    template_margin: float,
    template_arc_ratio: float,
) -> str:
    """Return a closed, expanded outline around a vertically stacked checker set."""
    if not centers:
        raise ValueError("checker template requires at least one checker")

    center_x = centers[0][0]
    if any(abs(x - center_x) > 1e-9 for x, _ in centers):
        raise ValueError("checker template centers must share a horizontal center")

    if template_margin < 0:
        raise ValueError("template_margin must not be negative")
    if template_arc_ratio <= 0:
        raise ValueError("template_arc_ratio must be greater than zero")
    radius = checker_size / 2 + template_margin
    arc_inset = checker_size * template_arc_ratio
    if arc_inset >= radius:
        raise ValueError(
            "template_arc_ratio must keep arc endpoints inside the expanded checker radius"
        )
    arc_height = math.sqrt(radius**2 - arc_inset**2)
    ordered_centers = tuple(sorted(centers, key=lambda center: center[1]))

    def point(x: float, y: float) -> str:
        return f"{x:.12g},{y:.12g}"

    first_y = ordered_centers[0][1]
    path = [f"M {point(center_x - arc_inset, first_y - arc_height)}"]
    path.append(
        f"A {radius:.12g},{radius:.12g} 0 0,1 "
        f"{point(center_x + arc_inset, first_y - arc_height)}"
    )

    for index, (_, center_y) in enumerate(ordered_centers):
        path.append(
            f"A {radius:.12g},{radius:.12g} 0 0,1 "
            f"{point(center_x + arc_inset, center_y + arc_height)}"
        )
        if index < len(ordered_centers) - 1:
            next_y = ordered_centers[index + 1][1]
            path.append(f"L {point(center_x + arc_inset, next_y - arc_height)}")

    last_y = ordered_centers[-1][1]
    path.append(
        f"A {radius:.12g},{radius:.12g} 0 0,1 "
        f"{point(center_x - arc_inset, last_y + arc_height)}"
    )

    for index in range(len(ordered_centers) - 1, -1, -1):
        center_y = ordered_centers[index][1]
        path.append(
            f"A {radius:.12g},{radius:.12g} 0 0,1 "
            f"{point(center_x - arc_inset, center_y - arc_height)}"
        )
        if index:
            previous_y = ordered_centers[index - 1][1]
            path.append(f"L {point(center_x - arc_inset, previous_y + arc_height)}")

    return " ".join(path) + " Z"


def template_output_path(output: Path) -> Path:
    """Return the checker-template SVG path derived from the main output."""
    return output.with_stem(f"{output.stem}_template")


def _new_drawing(
    output: Path,
    canvas_x: float,
    canvas_y: float,
    canvas_width: float,
    canvas_height: float,
) -> svgwrite.Drawing:
    drawing = svgwrite.Drawing(
        str(output),
        size=(f"{canvas_width:g}mm", f"{canvas_height:g}mm"),
        viewBox=f"{canvas_x:g} {canvas_y:g} {canvas_width:g} {canvas_height:g}",
        profile="full",
        debug=False,
    )
    drawing.attribs.update(
        {
            "id": "svg8",
            "xmlns:inkscape": "http://www.inkscape.org/namespaces/inkscape",
        }
    )
    return drawing


def verify_checker_layout(checker_size: float, rosette_ratio: float = 1.0) -> None:
    """Assert base tangency and one-diameter spacing for every stack."""
    radius = checker_size / 2
    for side, pip_index, count in CHECKER_STACKS:
        anchor_x, anchor_y = pip_anchor(
            side, pip_index, checker_size=checker_size, rosette_ratio=rosette_ratio
        )
        centers = checker_centers(
            side, pip_index, count, checker_size, rosette_ratio=rosette_ratio
        )
        direction = 1 if side == "top" else -1
        translation = checker_stack_translation(
            side, pip_index, checker_size, rosette_ratio
        )
        translated_centers = tuple((x, y + translation) for x, y in centers)
        first_x, first_y = translated_centers[0]
        assert abs(first_x - anchor_x) < 1e-9
        expected_first_y = anchor_y + direction * radius + translation
        assert abs(first_y - expected_first_y) < 1e-9
        for (_, previous_y), (_, current_y) in zip(
            translated_centers, translated_centers[1:]
        ):
            assert abs(current_y - previous_y - direction * checker_size) < 1e-9


def build_board(
    output: Path = DEFAULT_OUTPUT,
    checker_size: float = DEFAULT_CHECKER_SIZE,
    template_margin: float = DEFAULT_TEMPLATE_MARGIN,
    template_arc_ratio: float = DEFAULT_TEMPLATE_ARC_RATIO,
    rosette: bool = False,
    rosette_ratio: float = 1.0,
    half: bool = False,
    cut: bool = True,
    checkers: bool = True,
    separate_template: bool = False,
    pip_engrave_width: float | None = None,
    rosette_engrave_width: float | None = None,
    alternate_pips: bool = True,
) -> Path | None:
    if checker_size <= 0:
        raise ValueError("checker_size must be greater than zero")
    if template_margin < 0:
        raise ValueError("template_margin must not be negative")
    if template_arc_ratio <= 0:
        raise ValueError("template_arc_ratio must be greater than zero")
    if rosette_ratio <= 0:
        raise ValueError("rosette_ratio must be greater than zero")
    if pip_engrave_width is not None and pip_engrave_width <= 0:
        raise ValueError("pip_engrave_width must be greater than zero")
    if rosette_engrave_width is not None and rosette_engrave_width <= 0:
        raise ValueError("rosette_engrave_width must be greater than zero")
    layout_rosette_ratio = rosette_ratio if rosette else 1.0
    verify_checker_layout(checker_size, layout_rosette_ratio)
    scale = scale_factor(checker_size)
    resolved_pip_engrave_width = (
        DEFAULT_PIP_ENGRAVE_WIDTH * scale
        if pip_engrave_width is None
        else pip_engrave_width
    )
    resolved_rosette_engrave_width = (
        DEFAULT_ROSETTE_ENGRAVE_WIDTH * scale
        if rosette_engrave_width is None
        else rosette_engrave_width
    )
    scaled_template_margin = template_margin * scale_factor(checker_size)
    bounds_function = half_canvas_bounds if half else canvas_bounds
    canvas_x, canvas_y, canvas_width, canvas_height = bounds_function(
        checker_size, layout_rosette_ratio
    )
    drawing = _new_drawing(
        output, canvas_x, canvas_y, canvas_width, canvas_height
    )
    template_output: Path | None = None
    if separate_template:
        template_output = template_output_path(output)
        template_drawing = _new_drawing(
            template_output, canvas_x, canvas_y, canvas_width, canvas_height
        )
        template_target = template_drawing
    else:
        template_target = drawing
    pip_etch_layer = add_layer(drawing, "layer1", "Pip Etch")
    pip_cut_layer = add_layer(drawing, "layer3", "Pip Cut")
    pip_count = 6 if half else len(TOP_PIP_TRANSFORMS)
    for index in range(pip_count):
        pip_index = index + 1
        horizontal_offset = pip_group_horizontal_offset(
            pip_index, checker_size, layout_rosette_ratio
        )
        engrave_width = (
            alternating_pip_engrave_width(
                "top", pip_index, resolved_pip_engrave_width
            )
            if alternate_pips
            else resolved_pip_engrave_width
        )
        add_pip(
            pip_etch_layer,
            pip_cut_layer,
            f"pip_{pip_number('top', pip_index)}",
            _compose_matrices(
                (1, 0, 0, 1, horizontal_offset, 0),
                _pip_matrix(
                    "top", pip_index, checker_size, layout_rosette_ratio
                ),
            ),
            engrave_width,
            cut,
        )

    for index in range(pip_count):
        pip_index = index + 1
        horizontal_offset = pip_group_horizontal_offset(
            pip_index, checker_size, layout_rosette_ratio
        )
        engrave_width = (
            alternating_pip_engrave_width(
                "bottom", pip_index, resolved_pip_engrave_width
            )
            if alternate_pips
            else resolved_pip_engrave_width
        )
        add_pip(
            pip_etch_layer,
            pip_cut_layer,
            f"pip_{pip_number('bottom', pip_index)}",
            _compose_matrices(
                (1, 0, 0, 1, horizontal_offset, 0),
                _pip_matrix(
                    "bottom", pip_index, checker_size, layout_rosette_ratio
                ),
            ),
            engrave_width,
            cut,
        )

    if rosette:
        rosette_layer = add_layer(drawing, "layer7", "Rosette")
        centers = half_centers(checker_size, layout_rosette_ratio)
        if half:
            centers = centers[:1]
        for index, (center_x, center_y) in enumerate(centers, start=1):
            group = svgwrite.container.Group(id=f"rosette_{index}", debug=False)
            add_hex_rosette(
                group,
                HexRosetteParams(
                    diameter=checker_size * rosette_ratio,
                    sets=ROSETTE_SETS,
                    center_x=center_x,
                    center_y=center_y,
                    filled_engraving=True,
                    engrave_width=resolved_rosette_engrave_width,
                    cut=cut,
                    draw_fills=False,
                ),
            )
            rosette_layer.add(group)

    if checkers:
        checkers_layer = add_layer(drawing, "layer4", "Checkers")
        for group_index, (side, pip_index, count) in enumerate(
            CHECKER_STACKS, start=1
        ):
            if half and pip_index > 6:
                continue
            checker_group = svgwrite.container.Group(
                id=f"checker_stack_{group_index}", debug=False
            )
            checker_group.attribs["transform"] = (
                f"translate(0,{checker_stack_translation(side, pip_index, checker_size, layout_rosette_ratio):g})"
            )
            for checker_index, center in enumerate(
                checker_centers(
                    side,
                    pip_index,
                    count,
                    checker_size,
                    pip_group_horizontal_offset(
                        pip_index, checker_size, layout_rosette_ratio
                    ),
                    layout_rosette_ratio,
                ),
                start=1,
            ):
                checker_group.add(
                    drawing.circle(
                        center=center,
                        r=checker_size / 2,
                        id=f"checker_{group_index}_{checker_index}",
                        style=checker_style("#000000" if cut else "#ff0000"),
                    )
                )
            checkers_layer.add(checker_group)

    checker_templates = add_layer(
        template_target, "layer6", "Checker Template"
    )
    rectangles = border_rectangles(checker_size, layout_rosette_ratio)
    inner_rectangles = ((1, rectangles[0]),) if half else tuple(
        enumerate(rectangles[:2], start=1)
    )
    for border_index, (x, y, width, height) in inner_rectangles:
        inset_width = width - 2 * scaled_template_margin
        inset_height = height - 2 * scaled_template_margin
        if inset_width <= 0 or inset_height <= 0:
            raise ValueError("template_margin is too large for the inner borders")
        checker_templates.add(
            template_target.rect(
                insert=(x + scaled_template_margin, y + scaled_template_margin),
                size=(inset_width, inset_height),
                id=f"checker_template_border_{border_index}",
                style=cut_style("#000000" if cut else "#ff0000"),
            )
        )

    for group_index, (side, pip_index, count) in enumerate(CHECKER_STACKS, start=1):
        if half and pip_index > 6:
            continue
        centers = checker_centers(
            side,
            pip_index,
            count,
            checker_size,
            pip_group_horizontal_offset(
                pip_index, checker_size, layout_rosette_ratio
            ),
            layout_rosette_ratio,
        )
        checker_templates.add(
            svgwrite.path.Path(
                id=f"checker_template_stack_{group_index}",
                d=checker_template_outline(
                    centers,
                    checker_size,
                    scaled_template_margin,
                    template_arc_ratio,
                ),
                transform=(
                    f"translate(0,{checker_stack_translation(side, pip_index, checker_size, layout_rosette_ratio):g})"
                ),
                style=cut_style("#000000" if cut else "#ff0000"),
                debug=False,
            )
        )

    border_layer = add_layer(drawing, "layer5", "Border")
    indexed_rectangles = (
        ((1, rectangles[0]), (4, rectangles[3]))
        if half
        else tuple(enumerate(rectangles, start=1))
    )
    for index, (x, y, width, height) in indexed_rectangles:
        is_outer = index in (3, 4)
        color = "#000000" if cut or is_outer else "#ff0000"
        border_layer.add(
            drawing.rect(
                insert=(x, y),
                size=(width, height),
                id=f"border_{index}",
                style=line_style(color),
            )
        )

    drawing.save(pretty=True)
    if separate_template:
        assert template_output is not None
        template_drawing.save(pretty=True)
        return template_output
    return None


def get_parser() -> argparse.ArgumentParser:
    def positive_size(value: str) -> float:
        size = float(value)
        if size <= 0:
            raise argparse.ArgumentTypeError("must be greater than zero")
        return size

    def nonnegative_size(value: str) -> float:
        size = float(value)
        if size < 0:
            raise argparse.ArgumentTypeError("must not be negative")
        return size

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        metavar="PATH",
        help=f"output SVG path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--checker-size",
        type=positive_size,
        default=DEFAULT_CHECKER_SIZE,
        metavar="MM",
        help=f"checker diameter in millimeters (default: {DEFAULT_CHECKER_SIZE:g})",
    )
    parser.add_argument(
        "--template-margin",
        type=nonnegative_size,
        default=DEFAULT_TEMPLATE_MARGIN,
        metavar="MM",
        help=(
            "checker template expansion at the default checker scale "
            f"(default: {DEFAULT_TEMPLATE_MARGIN:g}mm)"
        ),
    )
    parser.add_argument(
        "--template-arc-ratio",
        type=positive_size,
        default=DEFAULT_TEMPLATE_ARC_RATIO,
        metavar="RATIO",
        help=(
            "horizontal arc endpoint distance as a checker-size ratio "
            f"(default: {DEFAULT_TEMPLATE_ARC_RATIO:g})"
        ),
    )
    parser.add_argument(
        "--rosette",
        action="store_true",
        help=(
            "add a hex rosette centered in each board half "
            f"(sets={ROSETTE_SETS})"
        ),
    )
    parser.add_argument(
        "--rosette-ratio",
        type=positive_size,
        default=1.0,
        metavar="RATIO",
        help=(
            "with --rosette, set diameter as a checker-size ratio; values "
            "above 1 expand board height by the excess diameter (default: 1)"
        ),
    )
    parser.add_argument(
        "--half",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="generate only the tightly cropped left playing half (default: off)",
    )
    parser.add_argument(
        "--cut",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="preserve black cut lines; --no-cut makes all but outer borders red",
    )
    parser.add_argument(
        "--checkers",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="include the checker reference layer (default: on)",
    )
    parser.add_argument(
        "--separate-template",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "write the checker template layer to a separate _template.svg "
            "(default: include it in the main output)"
        ),
    )
    parser.add_argument(
        "--pip-engrave-width",
        type=positive_size,
        default=None,
        metavar="MM",
        help=(
            "filled pip engraving width in millimeters "
            f"(default: {DEFAULT_PIP_ENGRAVE_WIDTH:g}mm scaled with checker size)"
        ),
    )
    parser.add_argument(
        "--alternate-pips",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "alternate thick and one-third-width pip engraving, with opposing "
            "top/bottom parity (default: on)"
        ),
    )
    parser.add_argument(
        "--rosette-engrave-width",
        type=positive_size,
        default=None,
        metavar="MM",
        help=(
            "filled rosette engraving width in millimeters "
            f"(default: {DEFAULT_ROSETTE_ENGRAVE_WIDTH:g}mm scaled with checker size)"
        ),
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = get_parser()
    argcomplete.autocomplete(parser)
    return parser.parse_args(argv)


def main() -> None:
    arguments = parse_args()
    template_output = build_board(
        output=arguments.out,
        checker_size=arguments.checker_size,
        template_margin=arguments.template_margin,
        template_arc_ratio=arguments.template_arc_ratio,
        rosette=arguments.rosette,
        rosette_ratio=arguments.rosette_ratio,
        half=arguments.half,
        cut=arguments.cut,
        checkers=arguments.checkers,
        separate_template=arguments.separate_template,
        pip_engrave_width=arguments.pip_engrave_width,
        rosette_engrave_width=arguments.rosette_engrave_width,
        alternate_pips=arguments.alternate_pips,
    )
    print(f"Wrote {arguments.out}")
    if template_output is not None:
        print(f"Wrote {template_output}")


if __name__ == "__main__":
    main()
