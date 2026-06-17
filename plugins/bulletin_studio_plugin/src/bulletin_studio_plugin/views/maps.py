from django.http import HttpResponse
from django.views.decorators.http import require_GET

from ..services.map_render import MapRenderError, render_layer_preview
from ._helpers import fail


@require_GET
def map_preview(request, layer_id):
    """Stateless PNG preview of a layer's latest (or given-time) file, for the editor."""
    try:
        width = int(request.GET.get("width", 600))
        height = int(request.GET.get("height", 440))
        show_boundaries = request.GET.get("boundaries", "1") != "0"
        png_bytes, raster_file = render_layer_preview(
            layer_id, width=width, height=height,
            time=request.GET.get("time"), show_boundaries=show_boundaries,
        )
    except MapRenderError as e:
        return fail(e, status=404)
    except Exception as e:
        return fail(e, status=500)

    response = HttpResponse(png_bytes, content_type="image/png")
    response["X-Raster-Time"] = raster_file.time.isoformat()
    return response
