from dataclasses import dataclass, field
from typing import List
from app.drawing.primitives import CADPrimitive

@dataclass
class Drawing:
    elements: List[CADPrimitive] = field(default_factory=list)
    layers: List[str] = field(default_factory=lambda: [
        "Walls", "Doors", "Windows", "Dimensions", "Annotations", "Furniture", "Structural", "Grid", "Utilities"
    ])
    
    def add(self, element: CADPrimitive):
        self.elements.append(element)
        
    def filter_layer(self, layer_name: str) -> List[CADPrimitive]:
        return [el for el in self.elements if el.layer == layer_name]
