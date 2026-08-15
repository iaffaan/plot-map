from typing import List, Tuple

class SpatialIndex:
    """
    Abstracted Spatial Index for collision-aware placement.
    Uses simple bounding-box overlap validation for the MVP, 
    designed to be transparently swapped with an STRtree in production.
    """
    def __init__(self):
        # List of Tuple: (min_x, min_y, max_x, max_y, entity_id)
        self._boxes: List[Tuple[float, float, float, float, str]] = []
        
    def insert(self, entity_id: str, min_x: float, min_y: float, max_x: float, max_y: float) -> None:
        """Inserts a bounding box into the spatial index."""
        # Add a tiny padding to avoid exact-border overlap edge cases
        padding = 0.05
        self._boxes.append((
            min_x - padding,
            min_y - padding,
            max_x + padding,
            max_y + padding,
            entity_id
        ))
        
    def intersects(self, min_x: float, min_y: float, max_x: float, max_y: float) -> bool:
        """
        Queries the index to check if a candidate box intersects with any existing elements.
        """
        for bx_min, by_min, bx_max, by_max, _ in self._boxes:
            # Overlap check (AABB intersection test)
            if not (max_x < bx_min or min_x > bx_max or max_y < by_min or min_y > by_max):
                return True
        return False

    def clear(self) -> None:
        self._boxes.clear()
