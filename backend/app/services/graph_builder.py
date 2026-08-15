import networkx as nx
from typing import Dict, List, Set
from app.core.tbm import Building

def build_graph_from_tbm(building: Building) -> nx.Graph:
    """
    Regenerates a NetworkX topological graph from a Building TBM.
    The graph represents:
    - Rooms as nodes (with type='room')
    - Openings (Doors/Windows) as nodes (with type='opening')
    - Edges representing adjacency and direct physical connectivity.
    """
    G = nx.Graph()
    
    # 1. Add Room nodes
    for r_id, room in building.rooms.items():
        G.add_node(
            r_id,
            type="room",
            room_type=room.type,
            name=room.name,
            floor_id=room.floor_id
        )
        
    # 2. Add Opening nodes and connectivity edges
    for o_id, opening in building.openings.items():
        G.add_node(
            o_id,
            type="opening",
            opening_type=opening.type,
            wall_id=opening.wall_id
        )
        # If it connects rooms (like a Door)
        if opening.connects_room_a_id and opening.connects_room_b_id:
            G.add_edge(opening.connects_room_a_id, o_id, relation="connects")
            G.add_edge(o_id, opening.connects_room_b_id, relation="connects")
            
    # 3. Add Wall adjacency edges between rooms
    for w_id, wall in building.walls.items():
        if wall.room_a_id and wall.room_b_id:
            # Direct wall contact between rooms
            G.add_edge(
                wall.room_a_id,
                wall.room_b_id,
                relation="adjacency",
                wall_id=w_id
            )
            
    return G

def get_isolated_rooms(building: Building) -> List[str]:
    """
    Returns a list of Room IDs that have no physical door connections
    (i.e., completely locked or inaccessible).
    """
    G = build_graph_from_tbm(building)
    isolated = []
    
    for node_id, attrs in G.nodes(data=True):
        if attrs.get("type") == "room":
            # Check if this room node has any adjacent "opening" nodes of type "Door"
            has_door = False
            for neighbor in G.neighbors(node_id):
                n_attrs = G.nodes[neighbor]
                if n_attrs.get("type") == "opening" and n_attrs.get("opening_type") == "Door":
                    has_door = True
                    break
            if not has_door:
                isolated.append(node_id)
                
    return isolated

def check_all_accessible_from(building: Building, start_room_id: str) -> Dict[str, bool]:
    """
    Validates if all rooms on the same floor are reachable from a starting room (e.g. Foyer/Living Room).
    Uses NetworkX shortest path transitions via door connections only.
    """
    G = build_graph_from_tbm(building)
    
    # Create a sub-graph containing only room nodes and "Door" opening nodes
    door_nodes = {
        node for node, attrs in G.nodes(data=True)
        if attrs.get("type") == "opening" and attrs.get("opening_type") == "Door"
    }
    room_nodes = {node for node, attrs in G.nodes(data=True) if attrs.get("type") == "room"}
    allowed_nodes = door_nodes.union(room_nodes)
    
    accessibility_subgraph = G.subgraph(allowed_nodes)
    
    result = {}
    for r_id in room_nodes:
        if r_id == start_room_id:
            result[r_id] = True
            continue
        try:
            # Check path connection
            connected = nx.has_path(accessibility_subgraph, start_room_id, r_id)
            result[r_id] = connected
        except nx.NetworkXError:
            result[r_id] = False
            
    return result
