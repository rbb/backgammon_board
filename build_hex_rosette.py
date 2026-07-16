#!/usr/bin/env python3
"""Generate a hex rosette SVG by rotating and shrinking concentric hexagon sets."""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import svgwrite

DEFAULT_OUTPUT = Path("hex_rosette.svg")
DEFAULT_DIAMETER = 100.0
DEFAULT_HEXAGONS_PER_SET = 3
DEFAULT_ROTATIONS = (0.0, 30.0, 45.0)
DEFAULT_SETS = 23
DEFAULT_SET_ROTATION = 17.0
DEFAULT_STROKE_WIDTH = 0.05
DEFAULT_FILL_COLOR = "white"

STROKE_OUTER = "black"
STROKE_INNER = "red"

# Tip-up in SVG (Y-down) using cos/sin: angle -90°. Visual CCW subtracts from this.
TIP_UP_DEG = -90.0
_EPS = 1e-9

Point = tuple[float, float]
Segment = tuple[Point, Point]


@dataclass
class HexRosetteParams:
    """Parameters for concentric rotating/shrinking hexagon rosette generation."""

    diameter: float = DEFAULT_DIAMETER
    output: Path = field(default_factory=lambda: DEFAULT_OUTPUT)
    hexagons_per_set: int = DEFAULT_HEXAGONS_PER_SET
    rotations: tuple[float, ...] = DEFAULT_ROTATIONS
    sets: int = DEFAULT_SETS
    set_rotation: float = DEFAULT_SET_ROTATION
    shrink: float | None = None
    draw_outer_circle: bool = False
    fill_last_set: bool = True
    stroke_width: float = DEFAULT_STROKE_WIDTH
    fill_color: str = DEFAULT_FILL_COLOR
    center_x: float | None = None
    center_y: float | None = None

    @property
    def center(self) -> Point:
        half = self.diameter / 2
        return (
            half if self.center_x is None else self.center_x,
            half if self.center_y is None else self.center_y,
        )

    @property
    def outer_radius(self) -> float:
        return self.diameter / 2


def paint_color(value: str) -> str:
    """Normalize a color CLI value; ``none`` means transparent SVG paint."""
    return "none" if value.strip().lower() == "none" else value


def hex_vertices(
    center_x: float,
    center_y: float,
    radius: float,
    rotation_deg: float,
) -> list[Point]:
    """Pointy-top hexagon; ``rotation_deg`` is visual CCW from tip-up."""
    start = TIP_UP_DEG - rotation_deg
    return [
        (
            center_x + radius * math.cos(math.radians(start + 60 * index)),
            center_y + radius * math.sin(math.radians(start + 60 * index)),
        )
        for index in range(6)
    ]


def hex_edges(
    center_x: float,
    center_y: float,
    radius: float,
    rotation_deg: float,
) -> list[Segment]:
    vertices = hex_vertices(center_x, center_y, radius, rotation_deg)
    return [(vertices[i], vertices[(i + 1) % 6]) for i in range(6)]


def ray_segment_intersection_t(
    origin: Point,
    direction: Point,
    a: Point,
    b: Point,
) -> float | None:
    """Return ray parameter ``t >= 0`` if the ray hits segment ``a``–``b``."""
    ox, oy = origin
    dx, dy = direction
    ax, ay = a
    bx, by = b
    ex, ey = bx - ax, by - ay

    denom = dx * ey - dy * ex
    if abs(denom) < _EPS:
        return None

    apx, apy = ax - ox, ay - oy
    t = (apx * ey - apy * ex) / denom
    u = (apx * dy - apy * dx) / denom
    if t < -_EPS or u < -_EPS or u > 1 + _EPS:
        return None
    return t


def set_offset(params: HexRosetteParams, set_index: int) -> float:
    """Visual-CCW degrees added to every hex in ``set_index`` (0 = outer)."""
    return set_index * params.set_rotation


def rotations_for_set(
    params: HexRosetteParams, set_index: int
) -> tuple[float, ...]:
    offset = set_offset(params, set_index)
    return tuple(rotation + offset for rotation in params.rotations)


def tip_direction(rotation_deg: float) -> Point:
    """Unit direction of a hex tip at ``rotation_deg`` visual CCW from tip-up."""
    radians = math.radians(rotation_deg)
    return (-math.sin(radians), -math.cos(radians))


def ray_hits_for_set(
    center: Point,
    radius: float,
    rotations: tuple[float, ...],
    ray_rotation_deg: float,
) -> list[float]:
    """Intersection radii along a tip ray with edges of the given hex set."""
    cx, cy = center
    direction = tip_direction(ray_rotation_deg)
    hits: list[float] = []
    for rotation_deg in rotations:
        for a, b in hex_edges(cx, cy, radius, rotation_deg):
            t = ray_segment_intersection_t(center, direction, a, b)
            if t is not None and _EPS < t < radius - _EPS:
                hits.append(t)
    return hits


def next_radius(
    center: Point,
    radius: float,
    previous_rotations: tuple[float, ...],
    next_first_rotation: float,
    shrink: float | None,
) -> float:
    """Next set circumradius from shrink override or first-hex tip ray."""
    if shrink is not None:
        return radius * shrink

    hits = ray_hits_for_set(
        center, radius, previous_rotations, next_first_rotation
    )
    if not hits:
        raise ValueError(
            "auto-shrink failed: next-set tip ray does not meet any "
            "previous-set edge; provide --shrink or change --rotations / "
            "--set-rotation"
        )
    return max(hits)


def set_radii(params: HexRosetteParams) -> list[float]:
    """Circumradii for each set, outer first."""
    radii = [params.outer_radius]
    center = params.center
    for set_index in range(params.sets - 1):
        previous = rotations_for_set(params, set_index)
        next_first = rotations_for_set(params, set_index + 1)[0]
        radii.append(
            next_radius(
                center,
                radii[-1],
                previous,
                next_first,
                params.shrink,
            )
        )
    return radii


def point_in_hex(
    point: Point,
    center: Point,
    radius: float,
    rotation_deg: float,
    *,
    strict: bool = False,
) -> bool:
    """True if ``point`` lies inside a hex (strictly inside when ``strict``)."""
    cx, cy = center
    px, py = point[0] - cx, point[1] - cy
    apothem = radius * math.cos(math.radians(30.0))
    limit = apothem - _EPS if strict else apothem + _EPS
    for index in range(6):
        angle = math.radians(TIP_UP_DEG - rotation_deg + 30.0 + 60 * index)
        if px * math.cos(angle) + py * math.sin(angle) > limit:
            return False
    return True


def point_in_any_hex(
    point: Point,
    center: Point,
    radius: float,
    rotations: tuple[float, ...],
    *,
    strict: bool = False,
) -> bool:
    return any(
        point_in_hex(point, center, radius, rotation, strict=strict)
        for rotation in rotations
    )


def lerp(a: Point, b: Point, t: float) -> Point:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def segment_length(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def segment_intersection_param(a: Point, b: Point, c: Point, d: Point) -> float | None:
    """Parameter ``t`` on segment ``a``–``b`` at intersection with ``c``–``d``."""
    ax, ay = a
    bx, by = b
    cx, cy = c
    dx, dy = d
    ex, ey = bx - ax, by - ay
    fx, fy = dx - cx, dy - cy
    denom = ex * fy - ey * fx
    if abs(denom) < _EPS:
        return None
    t = ((cx - ax) * fy - (cy - ay) * fx) / denom
    u = ((cx - ax) * ey - (cy - ay) * ex) / denom
    if t < -_EPS or t > 1 + _EPS or u < -_EPS or u > 1 + _EPS:
        return None
    return min(1.0, max(0.0, t))


def edge_outward_normal(a: Point, b: Point, center: Point) -> Point:
    """Unit normal of chord ``a``–``b`` pointing away from ``center``."""
    mx, my = (a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5
    nx, ny = mx - center[0], my - center[1]
    length = math.hypot(nx, ny)
    if length < _EPS:
        return (0.0, -1.0)
    return (nx / length, ny / length)


def is_outer_edge_piece(
    a: Point,
    b: Point,
    center: Point,
    radius: float,
    rotations: tuple[float, ...],
) -> bool:
    """True if the segment lies on the outer silhouette of the hex union."""
    if segment_length(a, b) < _EPS:
        return False
    mid = lerp(a, b, 0.5)
    if point_in_any_hex(mid, center, radius, rotations, strict=True):
        return False
    normal = edge_outward_normal(a, b, center)
    probe_eps = max(radius * 1e-6, 1e-6)
    probe = (mid[0] + normal[0] * probe_eps, mid[1] + normal[1] * probe_eps)
    return not point_in_any_hex(probe, center, radius, rotations, strict=False)


def split_params_for_edge(
    edge: Segment,
    other_edges: list[Segment],
) -> list[float]:
    params = [0.0, 1.0]
    a, b = edge
    for c, d in other_edges:
        t = segment_intersection_param(a, b, c, d)
        if t is not None and _EPS < t < 1.0 - _EPS:
            params.append(t)
    return sorted(set(params))


def color_hex_edges(
    center: Point,
    radius: float,
    rotation_deg: float,
    set_rotations: tuple[float, ...],
    *,
    all_outer: bool,
) -> list[tuple[Point, Point, str]]:
    """Edge pieces for one hex; split/color against the outer set when needed."""
    edges = hex_edges(center[0], center[1], radius, rotation_deg)
    if all_outer:
        return [(a, b, STROKE_INNER) for a, b in edges]

    other_edges: list[Segment] = []
    for other_rotation in set_rotations:
        other_edges.extend(
            hex_edges(center[0], center[1], radius, other_rotation)
        )

    colored: list[tuple[Point, Point, str]] = []
    for edge in edges:
        # Split against every outer-set edge, including this hex's other edges.
        params = split_params_for_edge(edge, other_edges)
        a, b = edge
        for left, right in zip(params, params[1:]):
            if right - left < _EPS:
                continue
            p0 = lerp(a, b, left)
            p1 = lerp(a, b, right)
            color = (
                STROKE_OUTER
                if is_outer_edge_piece(p0, p1, center, radius, set_rotations)
                else STROKE_INNER
            )
            colored.append((p0, p1, color))
    return colored


def add_line(
    parent: svgwrite.base.BaseElement,
    a: Point,
    b: Point,
    *,
    stroke: str,
    stroke_width: float,
) -> None:
    if segment_length(a, b) < _EPS:
        return
    parent.add(
        svgwrite.shapes.Line(
            start=a,
            end=b,
            stroke=stroke,
            stroke_width=stroke_width,
            stroke_linecap="round",
        )
    )


def add_filled_hex(
    parent: svgwrite.base.BaseElement,
    center: Point,
    radius: float,
    rotation_deg: float,
    fill: str,
) -> None:
    parent.add(
        svgwrite.shapes.Polygon(
            points=hex_vertices(center[0], center[1], radius, rotation_deg),
            fill=fill,
            stroke="none",
        )
    )


def add_hex_rosette(
    parent: svgwrite.base.BaseElement,
    params: HexRosetteParams,
) -> None:
    """Draw the hex rosette into ``parent`` at ``params.center``."""
    center = params.center
    fill = paint_color(params.fill_color)
    radii = set_radii(params)
    outer_rotations = rotations_for_set(params, 0)

    # Painter's algorithm: per hex, fill then strokes so later fills hide
    # underlying line segments that fall inside them.
    for set_index, radius in enumerate(radii):
        rotations = rotations_for_set(params, set_index)
        split_outer = set_index == 0 and not params.draw_outer_circle
        is_last_set = set_index == len(radii) - 1
        draw_fill = params.fill_last_set or not is_last_set
        for rotation_deg in rotations:
            if draw_fill:
                add_filled_hex(parent, center, radius, rotation_deg, fill)
            for a, b, color in color_hex_edges(
                center,
                radius,
                rotation_deg,
                outer_rotations if split_outer else rotations,
                all_outer=not split_outer,
            ):
                add_line(
                    parent,
                    a,
                    b,
                    stroke=color,
                    stroke_width=params.stroke_width,
                )

    if params.draw_outer_circle:
        parent.add(
            svgwrite.shapes.Circle(
                center=center,
                r=params.outer_radius,
                fill="none",
                stroke=STROKE_OUTER,
                stroke_width=params.stroke_width,
            )
        )


def write_svg(params: HexRosetteParams) -> Path:
    """Write a standalone SVG whose canvas matches ``params.diameter``."""
    size = params.diameter
    drawing = svgwrite.Drawing(
        str(params.output),
        size=(f"{size}mm", f"{size}mm"),
        viewBox=f"0 0 {size} {size}",
    )
    add_hex_rosette(drawing, params)
    drawing.save()
    return params.output


def positive_size(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def shrink_factor(value: str) -> float:
    number = float(value)
    if not 0.0 < number < 1.0:
        raise argparse.ArgumentTypeError("must be between 0 and 1 (exclusive)")
    return number


def parse_rotations(value: str) -> tuple[float, ...]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("must list at least one angle")
    try:
        return tuple(float(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "must be a comma-separated list of numbers"
        ) from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    geometry = parser.add_argument_group("geometry")
    output = parser.add_argument_group("output")
    style = parser.add_argument_group("style")

    geometry.add_argument(
        "--hexagons-per-set",
        type=positive_int,
        default=DEFAULT_HEXAGONS_PER_SET,
        help=f"hexagons drawn in each set (default: {DEFAULT_HEXAGONS_PER_SET})",
    )
    geometry.add_argument(
        "--rotations",
        type=parse_rotations,
        default=DEFAULT_ROTATIONS,
        metavar="DEG,...",
        help=(
            "absolute visual-CCW degrees from tip-up for each hex in a set "
            f"(default: {','.join(str(int(a) if a == int(a) else a) for a in DEFAULT_ROTATIONS)})"
        ),
    )
    geometry.add_argument(
        "--sets",
        type=positive_int,
        default=DEFAULT_SETS,
        help=f"number of concentric sets, outer to inner (default: {DEFAULT_SETS})",
    )
    geometry.add_argument(
        "--set-rotation",
        type=float,
        default=DEFAULT_SET_ROTATION,
        metavar="DEG",
        help=(
            "visual-CCW degrees added to each successive set "
            f"(default: {DEFAULT_SET_ROTATION:g})"
        ),
    )
    geometry.add_argument(
        "--shrink",
        type=shrink_factor,
        default=None,
        metavar="FACTOR",
        help="constant shrink factor per set (default: auto from tip ray)",
    )
    geometry.add_argument(
        "--diameter",
        type=positive_size,
        default=DEFAULT_DIAMETER,
        metavar="MM",
        help=f"outermost circumdiameter in millimeters (default: {DEFAULT_DIAMETER:g})",
    )
    geometry.add_argument(
        "--center-x",
        type=float,
        default=None,
        metavar="MM",
        help="rosette center X in millimeters (default: diameter / 2)",
    )
    geometry.add_argument(
        "--center-y",
        type=float,
        default=None,
        metavar="MM",
        help="rosette center Y in millimeters (default: diameter / 2)",
    )
    geometry.add_argument(
        "--outer-circle",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="draw the enclosing circle (default: off)",
    )
    geometry.add_argument(
        "--fill-last-set",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="fill the innermost set with borderless hexagons (default: on)",
    )

    output.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output SVG path (default: {DEFAULT_OUTPUT})",
    )

    style.add_argument(
        "--stroke-width",
        type=positive_size,
        default=DEFAULT_STROKE_WIDTH,
        metavar="MM",
        help=f"line weight (default: {DEFAULT_STROKE_WIDTH:g})",
    )
    style.add_argument(
        "--fill-color",
        default=DEFAULT_FILL_COLOR,
        help=f'fill color, or "none" for transparent (default: {DEFAULT_FILL_COLOR})',
    )

    return parser.parse_args(argv)


def params_from_args(arguments: argparse.Namespace) -> HexRosetteParams:
    if len(arguments.rotations) != arguments.hexagons_per_set:
        print(
            f"error: --hexagons-per-set ({arguments.hexagons_per_set}) must equal "
            f"the number of --rotations ({len(arguments.rotations)})",
            file=sys.stderr,
        )
        sys.exit(1)

    return HexRosetteParams(
        diameter=arguments.diameter,
        output=arguments.output,
        hexagons_per_set=arguments.hexagons_per_set,
        rotations=tuple(arguments.rotations),
        sets=arguments.sets,
        set_rotation=arguments.set_rotation,
        shrink=arguments.shrink,
        draw_outer_circle=arguments.outer_circle,
        fill_last_set=arguments.fill_last_set,
        stroke_width=arguments.stroke_width,
        fill_color=arguments.fill_color,
        center_x=arguments.center_x,
        center_y=arguments.center_y,
    )


def main(argv: list[str] | None = None) -> None:
    arguments = parse_args(argv)
    params = params_from_args(arguments)
    try:
        path = write_svg(params)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(path)


if __name__ == "__main__":
    main()
