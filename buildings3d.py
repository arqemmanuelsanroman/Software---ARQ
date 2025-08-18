# buildings3d.py — OSMnx 2.x compatible (features_from_bbox with 2 positional args)
# Generate a 3D model (glTF .glb) of buildings around a lat/lon using OSM data.
# Colors meshes by building / building:use (optionally landuse if present).

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, List, Dict

import numpy as np
import geopandas as gpd
import shapely.geometry as sgeom

import osmnx as ox
import trimesh

# --- Config ---
DEFAULT_LEVEL_HEIGHT_M = 3.2  # meters per building level if no 'height' tag
MIN_HEIGHT_M = 3.0            # minimum extrusion to make it visible

# Simple color palette (RGBA 0..255) by use/category
COLOR_MAP: Dict[str, Tuple[int, int, int, int]] = {
    "residential": (80, 160, 255, 255),   # light blue
    "commercial":  (255, 160, 60, 255),   # orange
    "industrial":  (180, 180, 180, 255),  # gray
    "retail":      (255, 120, 120, 255),  # red-ish
    "office":      (255, 210, 80, 255),   # yellow
    "education":   (160, 120, 255, 255),  # purple
    "hospital":    (250, 120, 200, 255),  # pink
    "public":      (120, 220, 180, 255),  # teal
    "default":     (200, 200, 200, 255),  # default gray
}

@dataclass
class OSM3DConfig:
    lat: float
    lon: float
    radius_m: float = 500.0  # search radius in meters
    simplify: bool = True    # simplify polygons
    merge_multipolygons: bool = True  # explode multipolygons to polygons

def _bbox_from_point_m(lat: float, lon: float, dist_m: float):
    north, south, east, west = ox.utils_geo.bbox_from_point((lat, lon), dist=dist_m)
    return north, south, east, west

def _footprint_height(attrs: dict) -> float:
    h = None
    for key in ("height", "building:height"):
        if key in attrs and attrs[key] not in (None, "", "NaN"):
            try:
                h = float(str(attrs[key]).replace("m", "").strip())
                break
            except ValueError:
                pass
    if h is None:
        levels = None
        for key in ("building:levels", "levels"):
            if key in attrs and attrs[key] not in (None, "", "NaN"):
                try:
                    levels = float(attrs[key])
                    break
                except ValueError:
                    pass
        if levels is not None:
            h = max(levels * DEFAULT_LEVEL_HEIGHT_M, MIN_HEIGHT_M)
        else:
            h = MIN_HEIGHT_M
    return float(h)

def _footprint_color(attrs: dict) -> Tuple[int, int, int, int]:
    for key in ("building:use", "landuse", "building"):
        val = attrs.get(key)
        if isinstance(val, str):
            val = val.lower()
            if val in COLOR_MAP:
                return COLOR_MAP[val]
            if val in ("apartments", "house", "residential"):
                return COLOR_MAP["residential"]
            if val in ("retail", "shop", "mall"):
                return COLOR_MAP["retail"]
            if val in ("commercial", "hotel"):
                return COLOR_MAP["commercial"]
            if val in ("industrial", "warehouse"):
                return COLOR_MAP["industrial"]
            if val in ("school", "university", "college"):
                return COLOR_MAP["education"]
            if val in ("hospital", "clinic"):
                return COLOR_MAP["hospital"]
            if val in ("office",):
                return COLOR_MAP["office"]
    return COLOR_MAP["default"]

def _polygon_to_trimesh(poly: sgeom.Polygon, height: float) -> trimesh.Trimesh:
    if not poly.is_valid:
        poly = poly.buffer(0)
        if not isinstance(poly, sgeom.Polygon):
            if isinstance(poly, sgeom.MultiPolygon):
                poly = max(poly.geoms, key=lambda g: g.area)
            else:
                raise ValueError("Invalid polygon after buffer(0)")
    # Skip tiny slivers
    if float(poly.area) <= 1e-12:
        raise ValueError("Polygon too small")
    # Robust extrude with trimesh.creation
    try:
        mesh = trimesh.creation.extrude_polygon(poly, height=max(float(height), MIN_HEIGHT_M))
    except Exception:
        poly2 = poly.buffer(0.05)
        mesh = trimesh.creation.extrude_polygon(poly2, height=max(float(height), MIN_HEIGHT_M))
    return mesh

def fetch_buildings_gdf(cfg: OSM3DConfig) -> gpd.GeoDataFrame:
    north, south, east, west = _bbox_from_point_m(cfg.lat, cfg.lon, cfg.radius_m)
    tags = {"building": True}  # focus on footprints of buildings
    try:
        # OSMnx 2.x signature: features_from_bbox(bbox_tuple, tags_dict)
        gdf = ox.features_from_bbox((north, south, east, west), tags)
    except Exception as e:
        raise RuntimeError(f"No se pudo descargar datos OSM: {e}")

    # --- Reproyectar a CRS métrico (UTM) para extrusión en metros ---
    try:
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        gdf = gdf.to_crs(gdf.estimate_utm_crs())
    except Exception:
        # Como fallback, usa Web Mercator
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        gdf = gdf.to_crs("EPSG:3857")

    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    if gdf.empty:
        return gdf

    if cfg.merge_multipolygons:
        gdf = gdf.explode(ignore_index=True)

    if cfg.simplify:
        gdf["geometry"] = gdf["geometry"].simplify(0.05, preserve_topology=True)

    return gdf

def build_glb_from_osm(cfg: OSM3DConfig, out_path: str) -> str:
    gdf = fetch_buildings_gdf(cfg)
    if gdf.empty:
        raise RuntimeError("No se encontraron edificios en el área seleccionada. Intenta aumentar el radio.")

    scene = trimesh.Scene()
    count = 0
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        attrs = row.to_dict()

        height = _footprint_height(attrs)
        color = _footprint_color(attrs)

        if isinstance(geom, sgeom.Polygon):
            polys: List[sgeom.Polygon] = [geom]
        elif geom.geom_type == "MultiPolygon":
            polys = list(geom.geoms)
        else:
            continue

        for poly in polys:
            try:
                mesh = _polygon_to_trimesh(poly, max(height, MIN_HEIGHT_M))
                rgba = np.array(color, dtype=np.uint8)
                colors = np.tile(rgba, (len(mesh.vertices), 1))
                mesh.visual.vertex_colors = colors
                scene.add_geometry(mesh)
                count += 1
            except Exception:
                continue

    if count == 0:
        raise RuntimeError("No se pudo crear ninguna malla.")

    scene.export(out_path)
    return out_path
