from typing import List
from app.core.tbm import Building
from app.core.exceptions import UnchartedException
from app.core.design_rules.nbc_rules import validate_nbc_rules, DesignRuleViolation
from app.core.design_rules.stair_feasibility import validate_stair_feasibility

class DesignRuleException(UnchartedException):
    """Raised when the TBM design violates building code, setback, or stair constraints."""
    def __init__(self, message: str, violations: List[DesignRuleViolation]):
        detail_msg = "\n".join([str(v) for v in violations])
        super().__init__(message, detail=detail_msg)
        self.violations = violations

def validate_setbacks(building: Building) -> List[DesignRuleViolation]:
    """
    Validates if any junctions or room boundaries encroach on the plot setbacks.
    """
    violations = []
    plot = building.plot
    setbacks = plot.setbacks
    
    left_bound = setbacks.get("left", 0.0)
    right_bound = plot.width - setbacks.get("right", 0.0)
    bottom_bound = setbacks.get("bottom", 0.0)
    top_bound = plot.depth - setbacks.get("top", 0.0)
    
    eps = 0.01  # tolerance for floating point Snaps
    
    for j_id, junction in building.junctions.items():
        if junction.x < left_bound - eps:
            violations.append(DesignRuleViolation(
                rule_id="SETBACK_LEFT_VIOLATION",
                severity="ERROR",
                message=f"Junction '{j_id}' (x={junction.x:.2f}) encroaches on left setback bound ({left_bound:.2f} ft).",
                entity_id=j_id
            ))
        if junction.x > right_bound + eps:
            violations.append(DesignRuleViolation(
                rule_id="SETBACK_RIGHT_VIOLATION",
                severity="ERROR",
                message=f"Junction '{j_id}' (x={junction.x:.2f}) encroaches on right setback bound ({right_bound:.2f} ft).",
                entity_id=j_id
            ))
        if junction.y < bottom_bound - eps:
            violations.append(DesignRuleViolation(
                rule_id="SETBACK_BOTTOM_VIOLATION",
                severity="ERROR",
                message=f"Junction '{j_id}' (y={junction.y:.2f}) encroaches on bottom setback bound ({bottom_bound:.2f} ft).",
                entity_id=j_id
            ))
        if junction.y > top_bound + eps:
            violations.append(DesignRuleViolation(
                rule_id="SETBACK_TOP_VIOLATION",
                severity="ERROR",
                message=f"Junction '{j_id}' (y={junction.y:.2f}) encroaches on top setback bound ({top_bound:.2f} ft).",
                entity_id=j_id
            ))
            
    return violations

def validate_building_design(building: Building, raise_on_error: bool = True) -> List[DesignRuleViolation]:
    """
    Runs all compliance rules on the building model.
    """
    violations = []
    
    # 1. Run NBC room and door dimensions checks
    violations.extend(validate_nbc_rules(building))
    
    # 2. Run Stair footprint feasibility checks
    violations.extend(validate_stair_feasibility(building))
    
    # 3. Run Plot setback check
    violations.extend(validate_setbacks(building))
    
    # Filter for severe errors
    errors = [v for v in violations if v.severity == "ERROR"]
    
    if raise_on_error and errors:
        raise DesignRuleException(
            message=f"Building layout validation failed with {len(errors)} critical design rule errors.",
            violations=violations
        )
        
    return violations
