from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.ops import unary_union

@dataclass
class Point2D:
    x: float
    y: float

@dataclass
class Polygon2D:
    vertices: List[Tuple[float, float]]  # List of (x, y) coordinates

class GeometryService:
    @staticmethod
    def create_point(x: float, y: float) -> Point2D:
        return Point2D(x, y)
        
    @staticmethod
    def create_polygon(vertices: List[Tuple[float, float]]) -> Polygon2D:
        return Polygon2D(vertices)
        
    @staticmethod
    def offset_segment(x1: float, y1: float, x2: float, y2: float, thickness: float) -> Polygon2D:
        """
        Creates a buffered polygon around a line segment.
        Uses flat cap styling to create clean rectangular wall panels.
        """
        line = LineString([(x1, y1), (x2, y2)])
        buffered = line.buffer(thickness / 2.0, cap_style='flat', join_style='mitre')
        
        # Extract exterior coordinates
        exterior_coords = list(buffered.exterior.coords)
        # Snapping vertices to 4 decimals to avoid tiny float errors
        coords = [(round(cx, 4), round(cy, 4)) for cx, cy in exterior_coords]
        return Polygon2D(coords)
        
    @staticmethod
    def union_polygons(polygons: List[Polygon2D]) -> List[Polygon2D]:
        """
        Merges overlapping polygons into a list of unified, non-overlapping boundary polygons.
        """
        shapely_polys = [Polygon(p.vertices) for p in polygons if len(p.vertices) >= 3]
        if not shapely_polys:
            return []
            
        union_res = unary_union(shapely_polys)
        
        # Convert back to Polygon2D list
        result = []
        if isinstance(union_res, Polygon):
            result.append(Polygon2D(list(union_res.exterior.coords)))
        elif isinstance(union_res, MultiPolygon):
            for poly in union_res.geoms:
                result.append(Polygon2D(list(poly.exterior.coords)))
                
        return result
        
    @staticmethod
    def difference_polygons(base: Polygon2D, tool: Polygon2D) -> List[Polygon2D]:
        """
        Subtracts the tool polygon from the base polygon.
        """
        base_poly = Polygon(base.vertices)
        tool_poly = Polygon(tool.vertices)
        
        diff = base_poly.difference(tool_poly)
        
        result = []
        if isinstance(diff, Polygon):
            if not diff.is_empty:
                result.append(Polygon2D(list(diff.exterior.coords)))
        elif isinstance(diff, MultiPolygon):
            for poly in diff.geoms:
                result.append(Polygon2D(list(poly.exterior.coords)))
        return result

    @staticmethod
    def get_bounds(poly: Polygon2D) -> Tuple[float, float, float, float]:
        """
        Returns (min_x, min_y, max_x, max_y) bounding box of the polygon.
        """
        p = Polygon(poly.vertices)
        return p.bounds
        
    @staticmethod
    def rotate_point(x: float, y: float, angle_degrees: float, cx: float = 0.0, cy: float = 0.0) -> Tuple[float, float]:
        """
        Rotates a point around a pivot point (cx, cy) by a given angle in degrees.
        """
        angle_rad = np.radians(angle_degrees)
        cos_val, sin_val = np.cos(angle_rad), np.sin(angle_rad)
        
        # Shift to origin
        tx = x - cx
        ty = y - cy
        
        # Rotate
        rx = tx * cos_val - ty * sin_val
        ry = tx * sin_val + ty * cos_val
        
        # Shift back
        return rx + cx, ry + cy
