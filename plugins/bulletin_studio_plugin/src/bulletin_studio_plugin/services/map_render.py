"""
Server-side rendering of geomanager map elements to PNG.

Reuses the exact recipe of geomanager's RasterThumbnailView:
get_tile_source(path, options).getThumbnail(...) (django-large-image),
plus an optional admin-boundary overlay drawn with PIL.

v1 supports `raster_file` layers only.
"""
import hashlib
import io
import json
import logging
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

DEFAULT_WIDTH = 800
DEFAULT_HEIGHT = 600


class MapRenderError(Exception):
    """Raised when a map element cannot be rendered (no layer, no file...)."""


def get_layer(layer_id):
    from geomanager.models import RasterFileLayer
    layer = RasterFileLayer.objects.filter(pk=layer_id).first()
    if layer is None:
        raise MapRenderError(_("Layer %s does not exist (was it deleted?)") % layer_id)
    return layer


def resolve_raster_file(layer, element, issue):
    """Pick the LayerRasterFile matching the element's time strategy for this issue."""
    strategy = element.get("time_strategy") or {}
    mode = strategy.get("mode", "latest_at_period_end")
    override = (issue.content or {}).get(element.get("id"), {}).get("time") if issue else None

    files = layer.raster_files.order_by("-time")

    if override:
        raster_file = files.filter(time=override).first()
        if raster_file is None:
            raise MapRenderError(_("No file exactly at %s for this layer") % override)
        return raster_file

    if issue is None:
        return files.first()

    if mode == "latest_at_issue_date":
        anchor = issue.issue_date
    elif mode == "offset_days":
        anchor = issue.period_anchor + timedelta(days=int(strategy.get("offset_days", 0)))
    else:  # latest_at_period_end (default) / exact without override
        anchor = issue.period_anchor

    raster_file = files.filter(time__date__lte=anchor).first()
    if raster_file is None:
        raise MapRenderError(
            _("No file on or before %(date)s for layer '%(layer)s'")
            % {"date": anchor, "layer": layer.title}
        )
    return raster_file


def _style_for(layer, element):
    if element.get("use_layer_style", True) and getattr(layer, "style", None):
        return layer.style.get_style_as_json()
    return None


def get_legend_for_element(element):
    """Legend config dict ({"type": ..., "items": [{name, color}...]}) or None."""
    try:
        layer = get_layer(element.get("layer_id"))
    except MapRenderError:
        return None
    if not element.get("show_legend", True):
        return None
    style = getattr(layer, "style", None)
    if style is None:
        return None
    try:
        return style.get_legend_config()
    except Exception:
        logger.exception("Could not build legend config for layer %s", layer.pk)
        return None


def _render_png(raster_file, style, width, height):
    from geomanager.utils.raster_utils import get_tile_source

    options = {"encoding": "PNG", "projection": "EPSG:4326", "style": style}
    source = get_tile_source(path=raster_file.file, options=options)
    png_bytes, _mime = source.getThumbnail(encoding="PNG", width=width, height=height)

    bounds = None
    try:
        meta_bounds = source.getMetadata().get("bounds") or {}
        if all(k in meta_bounds for k in ("xmin", "xmax", "ymin", "ymax")):
            bounds = (meta_bounds["xmin"], meta_bounds["ymin"],
                      meta_bounds["xmax"], meta_bounds["ymax"])
    except Exception:
        logger.exception("Could not read raster bounds for boundary overlay")

    return png_bytes, bounds


def _overlay_boundaries(png_bytes, bounds, max_level=1):
    """Draw admin boundary outlines (levels 0..max_level) over the rendered PNG.

    Failures degrade gracefully to the plain raster image.
    """
    if bounds is None:
        return png_bytes
    try:
        from adminboundarymanager.models import AdminBoundary
        from PIL import Image, ImageDraw

        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        draw = ImageDraw.Draw(img)
        xmin, ymin, xmax, ymax = bounds
        if xmax <= xmin or ymax <= ymin:
            return png_bytes

        def to_px(lon, lat):
            x = (lon - xmin) / (xmax - xmin) * img.width
            y = (ymax - lat) / (ymax - ymin) * img.height
            return x, y

        boundaries = AdminBoundary.objects.filter(level__lte=max_level)
        for boundary in boundaries.iterator():
            geom = boundary.geom.simplify(0.01)
            polygons = geom if geom.geom_type == "MultiPolygon" else [geom]
            line_width = 2 if boundary.level == 0 else 1
            color = (60, 60, 60, 255) if boundary.level == 0 else (110, 110, 110, 200)
            for polygon in polygons:
                points = [to_px(lon, lat) for lon, lat in polygon.exterior_ring.coords]
                if len(points) > 1:
                    draw.line(points, fill=color, width=line_width)

        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        logger.exception("Boundary overlay failed; returning plain raster image")
        return png_bytes


def _params_hash(layer_id, raster_file, style, width, height, show_boundaries):
    payload = json.dumps(
        [str(layer_id), raster_file.pk, style, width, height, bool(show_boundaries)],
        sort_keys=True, default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def render_map_element(element, issue, force=False):
    """Render (or reuse from cache) the PNG asset for a map element of an issue."""
    from ..models import IssueAsset

    layer = get_layer(element.get("layer_id"))
    raster_file = resolve_raster_file(layer, element, issue)
    style = _style_for(layer, element)
    width = int(element.get("width_px", DEFAULT_WIDTH))
    height = int(element.get("height_px", DEFAULT_HEIGHT))
    show_boundaries = element.get("show_boundaries", True)

    params_hash = _params_hash(layer.pk, raster_file, style, width, height, show_boundaries)
    asset = IssueAsset.objects.filter(issue=issue, element_id=element["id"]).first()
    if asset and asset.params_hash == params_hash and asset.file and not force:
        return asset

    png_bytes, bounds = _render_png(raster_file, style, width, height)
    if show_boundaries:
        png_bytes = _overlay_boundaries(png_bytes, bounds)

    if asset is None:
        asset = IssueAsset(issue=issue, element_id=element["id"])
    elif asset.file:
        asset.file.delete(save=False)

    asset.params_hash = params_hash
    asset.raster_file_id = raster_file.pk
    asset.raster_time = raster_file.time
    asset.width = width
    asset.height = height
    asset.file.save(f"issue-{issue.pk}-{element['id']}.png", ContentFile(png_bytes), save=True)
    return asset


def render_layer_preview(layer_id, width=600, height=440, time=None, show_boundaries=True):
    """Stateless PNG preview for the template editor (latest file, or given time)."""
    layer = get_layer(layer_id)
    files = layer.raster_files.order_by("-time")
    raster_file = files.filter(time=time).first() if time else files.first()
    if raster_file is None:
        raise MapRenderError(_("Layer '%s' has no uploaded files yet") % layer.title)

    style = layer.style.get_style_as_json() if getattr(layer, "style", None) else None
    png_bytes, bounds = _render_png(raster_file, style, width, height)
    if show_boundaries:
        png_bytes = _overlay_boundaries(png_bytes, bounds)
    return png_bytes, raster_file
