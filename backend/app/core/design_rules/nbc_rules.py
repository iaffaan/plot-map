from typing import List, Tuple
from app.core.tbm import Building, Room

class DesignRuleViolation:
    def __init__(self, rule_id: str, severity: str, message: str, entity_id: str = ""):
        self.rule_id = rule_id
        self.severity = severity  # "ERROR" or "WARNING"
        self.message = message
        self.entity_id = entity_id

    def __repr__(self):
        return f"[{self.severity}] {self.rule_id}: {self.message}"

def validate_nbc_rules(building: Building) -> List[DesignRuleViolation]:
    """
    Validates room and opening dimensions against standard building codes (NBC).
    """
    violations = []
    
    # 1. Room Area and Dimension rules
    # Standard residential minimums:
    # Bedroom >= 80 sqft, Min width >= 8 ft
    # Kitchen >= 50 sqft, Min width >= 5 ft
    # Bathroom >= 15 sqft, Min width >= 3 ft
    
    for r_id, room in building.rooms.items():
        # Retrieve the wall coordinates to calculate width and height
        # For simplicity, we can get width and height from room target/min area
        # or calculate from room boundary wall geometry.
        # Let's use the room area for the semantic check.
        area = room.target_area
        
        if room.type.lower() == "bedroom":
            if area < 80.0:
                violations.append(DesignRuleViolation(
                    rule_id="NBC_BEDROOM_AREA",
                    severity="ERROR",
                    message=f"Bedroom '{room.name}' has area of {area:.1f} sqft, below NBC minimum of 80 sqft.",
                    entity_id=r_id
                ))
        elif room.type.lower() == "kitchen":
            if area < 50.0:
                violations.append(DesignRuleViolation(
                    rule_id="NBC_KITCHEN_AREA",
                    severity="ERROR",
                    message=f"Kitchen '{room.name}' has area of {area:.1f} sqft, below NBC minimum of 50 sqft.",
                    entity_id=r_id
                ))
        elif room.type.lower() in ["bathroom", "toilet", "wc"]:
            if area < 15.0:
                violations.append(DesignRuleViolation(
                    rule_id="NBC_BATHROOM_AREA",
                    severity="ERROR",
                    message=f"Bathroom '{room.name}' has area of {area:.1f} sqft, below NBC minimum of 15 sqft.",
                    entity_id=r_id
                ))
                
    # 2. Door Width rules
    # Bedroom Doors >= 3.0 ft
    # Bathroom Doors >= 2.5 ft
    # Main Entrance Doors >= 3.28 ft (1 meter)
    for o_id, opening in building.openings.items():
        if opening.type == "Door":
            width = opening.width
            # Determine door target type by room connections
            is_bathroom_door = False
            is_entrance_door = False
            
            connected_rooms = []
            if opening.connects_room_a_id:
                connected_rooms.append(building.rooms.get(opening.connects_room_a_id))
            if opening.connects_room_b_id:
                connected_rooms.append(building.rooms.get(opening.connects_room_b_id))
                
            types = [r.type.lower() for r in connected_rooms if r]
            if any(t in ["bathroom", "toilet", "wc"] for t in types):
                is_bathroom_door = True
            if not opening.connects_room_b_id:  # Connects to outdoors
                is_entrance_door = True
                
            if is_entrance_door and width < 3.25:
                violations.append(DesignRuleViolation(
                    rule_id="NBC_ENTRANCE_DOOR_WIDTH",
                    severity="ERROR",
                    message=f"Entrance door '{o_id}' width is {width:.2f} ft, below NBC minimum of 3.28 ft (1m).",
                    entity_id=o_id
                ))
            elif is_bathroom_door and width < 2.5:
                violations.append(DesignRuleViolation(
                    rule_id="NBC_BATHROOM_DOOR_WIDTH",
                    severity="ERROR",
                    message=f"Bathroom door '{o_id}' width is {width:.2f} ft, below NBC minimum of 2.5 ft.",
                    entity_id=o_id
                ))
            elif width < 3.0 and not is_bathroom_door and not is_entrance_door:
                violations.append(DesignRuleViolation(
                    rule_id="NBC_ROOM_DOOR_WIDTH",
                    severity="WARNING",
                    message=f"Room door '{o_id}' width is {width:.2f} ft, standard recommended is 3.0 ft.",
                    entity_id=o_id
                ))
                
    return violations
