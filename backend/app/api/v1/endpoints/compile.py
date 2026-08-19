from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import get_gemini_client
from app.core.exceptions import (
    AIParserError,
    InfeasibleRequestError,
    OptimizationSolverError,
    TopologyValidationError,
)
from app.services.ai.explainer import explain_layout
from app.services.ai.parser import parse_requirements
from app.services.compiler.serializer import compile_blueprint
from app.services.optimization.feasibility import verify_feasibility
from app.services.optimization.room_generator import generate_layout_program

router = APIRouter()

class CompileRequest(BaseModel):
    """Request model containing the unstructured natural language prompt from the user."""
    prompt: str

@router.post("", status_code=200)
def compile_layout(request: CompileRequest, client: Any = Depends(get_gemini_client)):  # noqa: B008
    """
    POST endpoint that will take a natural language description, extract constraints
    using the AI parsing layer, and execute the math optimization engine.
    """
    if not request.prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty."
        )
        
    ai_state = {
        "compiler_failed": False,
        "quota_exhausted": False,
        "failure_type": None,
    }

    # 1. Parse natural language prompt into CompilerIntent schema
    try:
        intent = parse_requirements(request.prompt, client, ai_state)
    except Exception as exc:  # noqa: BLE001
        raise AIParserError(
            message="Failed to parse user intent into structural requirements.",
            detail=str(exc)
        )
        
    # 2. Map CompilerIntent to setback configuration (Default 3 ft sides, and front road setback)
    # By default, road is at the bottom (front).
    setbacks = {
        "left": 3.0,
        "right": 3.0,
        "bottom": intent.front_road_setback,
        "top": 3.0
    }
    
    # 2b. Run Feasibility Engine validation checks
    is_feasible, reason = verify_feasibility(intent, setbacks)
    if not is_feasible:
        raise InfeasibleRequestError(
            message="Requested layout exceeds legal or physical limits of the plot.",
            detail=reason
        )
        
    # 3. Generate room program sizes and adjacencies matching the buildable area constraints
    try:
        layout_program = generate_layout_program(intent, setbacks)
    except Exception as exc:  # noqa: BLE001
        raise InfeasibleRequestError(
            message="Failed to generate feasible room sizes for the given plot layout.",
            detail=str(exc)
        )
        
    payload = {
        "plot": {
            "width": intent.plot_width,
            "depth": intent.plot_depth
        },
        "setbacks": setbacks,
        "stair_core": layout_program["stair_core"],
        "rooms": layout_program["rooms"],
        "adjacencies": layout_program["adjacencies"],
        "road_edge": "bottom",
        "grid_snap": 0.5,
        "time_limit_sec": 5,
        "floors": intent.floors
    }
    
    # 5. Compile layout blueprint using the geometry and solver services
    compiled_result = compile_blueprint(payload)
    
    if not compiled_result.get("success", False):
        error_msg = compiled_result.get("error", "Unknown compilation error.")
        if "setbacks do not exceed plot boundaries" in error_msg:
            raise InfeasibleRequestError(message="Plot setbacks exceed plot dimensions.", detail=error_msg)
        elif "Optimization Constraint Solver Error" in error_msg:
            raise OptimizationSolverError(message="MILP solver failed to pack rooms under the requested constraints.", detail=error_msg)
        elif "Topological Validation Error" in error_msg:
            raise TopologyValidationError(message="Topological privacy or access constraints violated.", detail=error_msg)
        else:
            raise OptimizationSolverError(message="Blueprint compilation failed due to solver/boundary constraints.", detail=error_msg)
            
    # 6. Generate natural language explanation explaining layout design decisions
    explanation = explain_layout(request.prompt, compiled_result, client, ai_state)
    
    # 7. Generate CAD-quality 2D Drawing (SVG)
    try:
        from app.services.relationship_builder import build_tbm_from_layout
        from app.services.geometry_resolver import resolve_geometry
        from app.core.design_rules.rule_engine import validate_building_design
        from app.drawing import Drawing, Polyline, export_drawing_to_svg
        from app.services.dimension_engine import generate_dimensions
        from app.services.annotation_engine import generate_annotations
        from app.drawing.symbols import generate_door_symbol, generate_window_symbol
        
        # Build TBM Model
        building = build_tbm_from_layout(payload, compiled_result)
        
        # Validate rules (silent check for warnings/errors)
        validate_building_design(building, raise_on_error=False)
        
        # Resolve 2D Polygons
        geom = resolve_geometry(building)
        
        # Create Drawing
        drawing = Drawing()
        
        # Add Wall Panels
        for w_id, panels in geom.wall_panels.items():
            for p in panels:
                drawing.add(Polyline(
                    layer="Walls",
                    color="#1e293b",  # dark slate-800
                    stroke_width=2.5,
                    points=p.vertices,
                    is_closed=True
                ))
                
        # Add Openings (Doors & Windows Symbols)
        for op_id, op in building.openings.items():
            box = geom.opening_boxes.get(op_id)
            if box:
                wall = building.walls.get(op.wall_id)
                j1 = building.junctions.get(wall.start_junction_id)
                j2 = building.junctions.get(wall.end_junction_id)
                dx = j2.x - j1.x
                dy = j2.y - j1.y
                L = (dx**2 + dy**2)**0.5
                ux, uy = dx / L, dy / L
                
                center = op.position_offset
                h_w = op.width / 2.0
                x1_op = j1.x + (center - h_w) * ux
                y1_op = j1.y + (center - h_w) * uy
                x2_op = j1.x + (center + h_w) * ux
                y2_op = j1.y + (center + h_w) * uy
                
                if op.type == "Door":
                    for sym_p in generate_door_symbol(x1_op, y1_op, x2_op, y2_op):
                        drawing.add(sym_p)
                else:
                    for sym_p in generate_window_symbol(x1_op, y1_op, x2_op, y2_op, wall.thickness):
                        drawing.add(sym_p)
                        
        # Generate Dimensions
        generate_dimensions(building, geom, drawing)
        
        # Generate Annotations & Title Block
        generate_annotations(building, geom, drawing)
        
        # Export SVG String
        drawing_svg = export_drawing_to_svg(drawing)
    except Exception as exc:
        drawing_svg = f'<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><!-- Drawing Generation Error: {str(exc)} --></svg>'
        
    return {
        "status": "success",
        "success": True,
        "message": "Layout compiled successfully.",
        "extracted_intent": intent.model_dump(),
        "layout": compiled_result.get("layout", {}),
        "boundaries": compiled_result.get("boundaries", {}),
        "metadata": compiled_result.get("metadata", {}),
        "geometry": compiled_result.get("geometry", {}),
        "floors": compiled_result.get("floors", {}),
        "metrics": compiled_result.get("metrics", {}),
        "render_tree": compiled_result.get("render_tree", {}),
        "drawing_svg": drawing_svg,
        "explanation": explanation.model_dump()
    }

