import math
from typing import List
from app.core.tbm import Building
from app.core.design_rules.nbc_rules import DesignRuleViolation

def validate_stair_feasibility(building: Building) -> List[DesignRuleViolation]:
    """
    Validates if staircases defined in the building floors are physically feasible.
    """
    violations = []
    
    # Standard residential stair codes:
    # Riser max height: 7.75 inches (0.646 ft)
    # Tread min depth: 10 inches (0.833 ft)
    # Riser target: ~7.0 inches (0.583 ft)
    
    for f_id, floor in building.floors.items():
        # Get floor height (elevation difference to next level)
        h = floor.height
        
        # Check stairs on this floor
        # We need to find stairs registered under building.stairs
        stair_ids_on_floor = [s_id for s_id, s in building.stairs.items() if s.floor_id == f_id]
        
        for s_id in stair_ids_on_floor:
            stair = building.stairs[s_id]
            
            # Calculate required risers to climb height h
            max_riser_ft = 7.75 / 12.0  # 0.646 ft
            min_risers = math.ceil(h / max_riser_ft)
            
            # We must fit at least min_risers risers (which translates to min_risers - 1 treads)
            min_treads = min_risers - 1
            
            # Validate if the U-shape or straight staircase footprint can fit these treads
            if stair.type == "U-shape":
                # A U-shape stair has two flights parallel to each other, and a landing at the end.
                # Flight width (stair.width) determines the landing depth (which must be at least stair.width).
                # Available length for treads = stair.length - stair.width (landing)
                # Number of treads we can fit per flight = floor( (stair.length - stair.width) / stair.tread_depth )
                # Since there are 2 flights, total treads we can fit = 2 * floor( (stair.length - stair.width) / stair.tread_depth )
                
                available_run = stair.length - stair.width
                if available_run < 0:
                    violations.append(DesignRuleViolation(
                        rule_id="STAIR_FOOTPRINT_TOO_SMALL",
                        severity="ERROR",
                        message=f"U-shape stair '{s_id}' length ({stair.length:.2f} ft) must be larger than width ({stair.width:.2f} ft) to allow for a landing.",
                        entity_id=s_id
                    ))
                    continue
                    
                treads_per_flight = math.floor(available_run / stair.tread_depth)
                max_feasible_treads = 2 * treads_per_flight
                
                if max_feasible_treads < min_treads:
                    violations.append(DesignRuleViolation(
                        rule_id="STAIR_INSUFFICIENT_TREADS",
                        severity="ERROR",
                        message=(
                            f"U-shape stair '{s_id}' footprint ({stair.length:.1f}x{stair.width*2:.1f} ft) "
                            f"can only fit {max_feasible_treads} treads, but requires at least {min_treads} treads "
                            f"to safely climb the floor height of {h:.1f} ft."
                        ),
                        entity_id=s_id
                    ))
            elif stair.type == "Straight":
                # A straight stair needs stair.length to hold all treads
                # Max treads = floor( stair.length / stair.tread_depth )
                max_feasible_treads = math.floor(stair.length / stair.tread_depth)
                
                if max_feasible_treads < min_treads:
                    violations.append(DesignRuleViolation(
                        rule_id="STAIR_INSUFFICIENT_TREADS",
                        severity="ERROR",
                        message=(
                            f"Straight stair '{s_id}' length ({stair.length:.1f} ft) "
                            f"can only fit {max_feasible_treads} treads, but requires at least {min_treads} "
                            f"to safely climb the floor height of {h:.1f} ft."
                        ),
                        entity_id=s_id
                    ))
                    
    return violations
