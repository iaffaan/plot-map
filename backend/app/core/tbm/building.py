from dataclasses import dataclass, field
from typing import List, Dict
from app.core.tbm.plot import Plot
from app.core.tbm.room import Room
from app.core.tbm.wall import Wall
from app.core.tbm.opening import Opening
from app.core.tbm.junction import Junction
from app.core.tbm.floor import Floor
from app.core.tbm.stair import Stair
from app.core.tbm.column import Column
from app.core.tbm.beam import Beam

@dataclass
class Building:
    id: str
    plot: Plot
    name: str = "Default Project"
    floor_ids: List[str] = field(default_factory=list)
    
    # DDD Lookup Registries
    floors: Dict[str, Floor] = field(default_factory=dict)
    rooms: Dict[str, Room] = field(default_factory=dict)
    walls: Dict[str, Wall] = field(default_factory=dict)
    openings: Dict[str, Opening] = field(default_factory=dict)
    junctions: Dict[str, Junction] = field(default_factory=dict)
    stairs: Dict[str, Stair] = field(default_factory=dict)
    columns: Dict[str, Column] = field(default_factory=dict)
    beams: Dict[str, Beam] = field(default_factory=dict)

