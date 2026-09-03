import math
import re
from typing import Any

from app.schemas.intent import CompilerIntent, RoomCategory, RoomIntent

PARSER_SYSTEM_PROMPT = (
    "You are a deterministic Natural Language Parser for an architectural constraint engine. "
    "Your ONLY objective is to extract parameters into strict JSON. DO NOT design the house. "
    "DO NOT calculate coordinates. If a user asks for a 'G+1' house, that equals 2 floors. "
    "Use standard Indian minimums if dimensions are missing."
)

def parse_requirements_fallback(prompt: str) -> CompilerIntent:
    """
    Enhanced fallback parser using regex and line analysis to extract parameters from structured or unstructured prompts
    when primary AI provider is unavailable.
    """
    # 1. Parse plot dimensions (e.g., "40x40", "30x40", "43.75x41")
    width, depth = 40.0, 40.0
    dim_match = re.search(r'(\d+(?:\.\d+)?)\s*[x×*]\s*(\d+(?:\.\d+)?)', prompt)
    if dim_match:
        width = float(dim_match.group(1))
        depth = float(dim_match.group(2))
        
    # 2. Parse floor count (e.g., "G+1" -> 2, "G+2" -> 3, "Ground Floor... First Floor" -> 2)
    floors = 1
    floor_match = re.search(r'g\+(\d+)', prompt, re.IGNORECASE)
    if floor_match:
        floors = int(floor_match.group(1)) + 1
    else:
        prompt_lower = prompt.lower()
        if "third floor" in prompt_lower or "3rd floor" in prompt_lower:
            floors = 4
        elif "second floor" in prompt_lower or "2nd floor" in prompt_lower:
            floors = 3
        elif "first floor" in prompt_lower or "1st floor" in prompt_lower or "ground floor" in prompt_lower and ("floor 1" in prompt_lower or "floor 2" in prompt_lower):
            floors = 2
        else:
            num_floor_match = re.search(r'(\d+)\s*floor', prompt, re.IGNORECASE)
            if num_floor_match:
                floors = int(num_floor_match.group(1))
            
    # 3. Parse setback (e.g., "setback of 5.0")
    setback = 5.0
    setback_match = re.search(r'setback\s+(?:of\s+)?(\d+(?:\.\d+)?)', prompt, re.IGNORECASE)
    if setback_match:
        setback = float(setback_match.group(1))
        
    # 4. Parse rooms line-by-line for structured briefs
    rooms = []
    lines = prompt.splitlines()
    for line in lines:
        l_lower = line.strip().lower()
        if not l_lower or l_lower.startswith("#") or "staircase" in l_lower or "shared stair" in l_lower:
            continue
        
        # Check specific room keywords
        if "living" in l_lower or "hall" in l_lower or "lounge" in l_lower:
            rooms.append(RoomIntent(room_type=RoomCategory.LIVING))
        elif "kitchen" in l_lower or "pantry" in l_lower:
            rooms.append(RoomIntent(room_type=RoomCategory.KITCHEN))
        elif "master bed" in l_lower or "bedroom" in l_lower or "bed room" in l_lower:
            rooms.append(RoomIntent(room_type=RoomCategory.BEDROOM))
        elif "bath" in l_lower or "toilet" in l_lower or "washroom" in l_lower or "wc" in l_lower:
            rooms.append(RoomIntent(room_type=RoomCategory.BATHROOM))
        elif "balcony" in l_lower or "terrace" in l_lower:
            rooms.append(RoomIntent(room_type=RoomCategory.BALCONY))
        elif "utility" in l_lower or "service" in l_lower or "wash area" in l_lower:
            rooms.append(RoomIntent(room_type=RoomCategory.UTILITY))
        elif "pooja" in l_lower or "mandir" in l_lower:
            rooms.append(RoomIntent(room_type=RoomCategory.POOJA))

    # If line-by-line yielded nothing, fall back to global keyword search
    if not rooms:
        for cat in RoomCategory:
            if cat.value in prompt.lower():
                count = 1
                count_match = re.search(r'(\d+)\s*' + cat.value, prompt, re.IGNORECASE)
                if count_match:
                    count = int(count_match.group(1))
                for _ in range(count):
                    rooms.append(RoomIntent(room_type=cat))
                
    # Fallback default room program if still empty
    if not rooms:
        if floors == 1:
            rooms = [
                RoomIntent(room_type=RoomCategory.BEDROOM),
                RoomIntent(room_type=RoomCategory.LIVING),
                RoomIntent(room_type=RoomCategory.KITCHEN),
                RoomIntent(room_type=RoomCategory.BATHROOM)
            ]
        elif floors == 2:
            rooms = [
                RoomIntent(room_type=RoomCategory.LIVING),
                RoomIntent(room_type=RoomCategory.KITCHEN),
                RoomIntent(room_type=RoomCategory.BEDROOM),
                RoomIntent(room_type=RoomCategory.BEDROOM),
                RoomIntent(room_type=RoomCategory.BATHROOM),
                RoomIntent(room_type=RoomCategory.BATHROOM),
            ]
        else:
            rooms = [
                RoomIntent(room_type=RoomCategory.LIVING),
                RoomIntent(room_type=RoomCategory.KITCHEN),
                RoomIntent(room_type=RoomCategory.BEDROOM),
                RoomIntent(room_type=RoomCategory.BEDROOM),
                RoomIntent(room_type=RoomCategory.BEDROOM),
                RoomIntent(room_type=RoomCategory.BATHROOM),
                RoomIntent(room_type=RoomCategory.BATHROOM),
            ]
        
    # 5. Parse qualitative objectives (ventilation, daylighting)
    prompt_lower = prompt.lower()
    prioritize_vent = any(k in prompt_lower for k in ["ventilat", "cross-vent", "cross vent", "airflow", "airy", "breeze"])
    prioritize_light = any(k in prompt_lower for k in ["natural light", "daylight", "sunlight", "sunlit", "lighting"])
    
    target_objectives = []
    if prioritize_vent:
        target_objectives.append("cross_ventilation")
    if prioritize_light:
        target_objectives.append("natural_daylight")

    return CompilerIntent(
        plot_width=width,
        plot_depth=depth,
        floors=floors,
        front_road_setback=setback,
        confidence_score=0.45,
        fallback_used=True,
        prioritize_ventilation=prioritize_vent,
        prioritize_daylight=prioritize_light,
        target_objectives=target_objectives,
        rooms=rooms
    )

def parse_requirements(
    prompt: str,
    client: Any = None,
    ai_state: dict[str, Any] | None = None,
) -> CompilerIntent:
    """
    Main requirements extraction handler. Attempts to parse unstructured prompt into
    a structured CompilerIntent using OpenAI-compatible NIM or Gemini client.
    Falls back gracefully to multi-tier parsing.
    """
    from app.core.config import settings

    if client is not None:
        last_exception = None
        max_attempts = 1
        backoff_delay = 1.0

        model_name = settings.NVIDIA_MODEL if hasattr(settings, "NVIDIA_MODEL") and settings.NVIDIA_MODEL else "nvidia/nemotron-3.5-lightning-30b-a3b"

        for attempt in range(1, max_attempts + 1):
            try:
                raw_res = None
                if hasattr(client, "create"):
                    raw_res = client.create(
                        model=model_name,
                        response_model=CompilerIntent,
                        max_retries=0 if ai_state is not None else 1,
                        strict=False,
                        messages=[
                            {
                                "role": "system",
                                "content": PARSER_SYSTEM_PROMPT
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    )
                elif hasattr(client, "chat") and hasattr(client.chat, "completions"):
                    raw_res = client.chat.completions.create(
                        model=model_name,
                        response_model=CompilerIntent,
                        max_retries=0 if ai_state is not None else 1,
                        strict=False,
                        messages=[
                            {
                                "role": "system",
                                "content": PARSER_SYSTEM_PROMPT
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    )
                else:
                    raise AttributeError("Unsupported client type")

                if isinstance(raw_res, CompilerIntent):
                    intent = raw_res
                elif isinstance(raw_res, str):
                    intent = CompilerIntent.model_validate_json(raw_res)
                else:
                    intent = raw_res
                intent.confidence_score = 0.95
                intent.fallback_used = False
                return intent
            except Exception as e:  # noqa: BLE001
                last_exception = e
                if attempt < max_attempts:
                    import time
                    time.sleep(backoff_delay)
                    backoff_delay *= 2.0
                else:
                    break

        if last_exception is not None:
            e = last_exception
            if ai_state is not None:
                error_text = str(e).lower()
                error_type = type(e).__name__.lower()
                if (
                    getattr(e, "status_code", None) == 429
                    or "429" in error_text
                    or "resource_exhausted" in error_text
                ):
                    failure_type = "quota"
                elif isinstance(e, TimeoutError) or "timeout" in error_type or "timeout" in error_text:
                    failure_type = "timeout"
                elif (
                    isinstance(e, OSError)
                    or "connection" in error_type
                    or "remoteprotocol" in error_type
                    or "disconnected" in error_text
                ):
                    failure_type = "network"
                else:
                    failure_type = "schema"
                ai_state["compiler_failed"] = True
                ai_state["failure_type"] = failure_type
                ai_state["quota_exhausted"] = failure_type == "quota"
            print(f"[AI Layer] Primary LLM call failed ({last_exception}). Using rule-based fallback...")

    return parse_requirements_fallback(prompt)

def parse_intent_to_layout(
    description: str,
    plot_width: float,
    plot_depth: float,
    setbacks: dict,
    floors: int = 1
) -> dict[str, Any]:
    """
    Parses a natural language description and plot parameters into a structured room and stair core configuration.
    Dynamically scales room sizes based on the available buildable area to guarantee solver feasibility.
    """
    # 1. Calculate buildable area
    sb_left = float(setbacks.get('left', setbacks.get('left', 0.0)))
    sb_right = float(setbacks.get('right', setbacks.get('right', 0.0)))
    sb_bottom = float(setbacks.get('bottom', setbacks.get('front', 0.0)))
    sb_top = float(setbacks.get('top', setbacks.get('back', 0.0)))
    
    buildable_width = max(0.0, plot_width - sb_left - sb_right)
    buildable_depth = max(0.0, plot_depth - sb_bottom - sb_top)
    raw_buildable_area = buildable_width * buildable_depth
    
    # 2. Determine stair core size and position
    stair_width = 8.0 if buildable_width < 30.0 else 10.0
    stair_height = 8.0 if buildable_depth < 30.0 else 10.0
    
    # If the buildable area is extremely small, scale down stair core further
    if raw_buildable_area < 400.0:
        stair_width = min(6.0, buildable_width * 0.25)
        stair_height = min(6.0, buildable_depth * 0.25)
        
    stair_area = stair_width * stair_height
    net_buildable_area = max(50.0, raw_buildable_area - stair_area)
    
    # Choose corner for stair core (default bottom-left)
    stair_edge = "bottom-left"
    if "right" in description.lower():
        stair_edge = "bottom-right"
    if "top" in description.lower():
        stair_edge = "top-left" if "left" in description.lower() else "top-right"
        
    stair_core = {
        "width": stair_width,
        "height": stair_height,
        "edge": stair_edge
    }
    
    # 3. Detect number of bedrooms requested
    num_bedrooms = 2  # Default
    
    # Check for direct number patterns
    bedroom_match = re.search(r'(\d+)\s*(?:bhk|bedroom|bed)', description, re.IGNORECASE)
    if bedroom_match:
        num_bedrooms = int(bedroom_match.group(1))
    else:
        # Check for word patterns
        desc_lower = description.lower()
        if "one bedroom" in desc_lower or "1 bedroom" in desc_lower or "1bhk" in desc_lower or "single bedroom" in desc_lower:
            num_bedrooms = 1
        elif "two bedroom" in desc_lower or "2 bedroom" in desc_lower or "2bhk" in desc_lower or "double bedroom" in desc_lower:
            num_bedrooms = 2
        elif "three bedroom" in desc_lower or "3 bedroom" in desc_lower or "3bhk" in desc_lower:
            num_bedrooms = 3
        elif "four bedroom" in desc_lower or "4 bedroom" in desc_lower or "4bhk" in desc_lower:
            num_bedrooms = 4
            
    # 4. Enforce self-healing limits based on net buildable area
    if net_buildable_area < 380.0 and num_bedrooms > 1:
        num_bedrooms = 1
    elif net_buildable_area < 650.0 and num_bedrooms > 2:
        num_bedrooms = 2
    elif net_buildable_area < 900.0 and num_bedrooms > 3:
        num_bedrooms = 3
        
    # 5. Define base rooms and target proportions of net buildable area
    rooms_config = []
    adjacencies = []
    
    # Entrance Lobby (all scenarios)
    rooms_config.append({
        "name": "Entrance Lobby",
        "type": "Entrance",
        "min_area": min(24.0, max(9.0, net_buildable_area * 0.04)),
        "min_width": 3.0,
        "min_height": 3.0,
        "requires_ventilation": False,
        "adjacent_to_road": True
    })
    
    # Living Room (all scenarios)
    living_area = min(240.0, max(80.0, net_buildable_area * 0.25))
    rooms_config.append({
        "name": "Living Room",
        "type": "Living Room",
        "min_area": living_area,
        "min_width": max(8.0, min(10.0, buildable_width * 0.3)),
        "min_height": max(8.0, min(10.0, buildable_depth * 0.3)),
        "requires_ventilation": True,
        "adjacent_to_road": True
    })
    adjacencies.append(("Entrance Lobby", "Living Room"))
    
    # Kitchen (all scenarios)
    kitchen_area = min(120.0, max(45.0, net_buildable_area * 0.15))
    rooms_config.append({
        "name": "Kitchen",
        "type": "Kitchen",
        "min_area": kitchen_area,
        "min_width": 6.5,
        "min_height": 6.5,
        "requires_ventilation": True,
        "adjacent_to_road": False
    })
    adjacencies.append(("Living Room", "Kitchen"))
    
    # Bedrooms & Bathrooms
    if num_bedrooms == 1:
        bed_area = min(180.0, max(90.0, net_buildable_area * 0.25))
        rooms_config.append({
            "name": "Master Bedroom",
            "type": "Bedroom",
            "min_area": bed_area,
            "min_width": 9.0,
            "min_height": 9.0,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Master Bedroom"))
        
        bath_area = min(45.0, max(25.0, net_buildable_area * 0.08))
        rooms_config.append({
            "name": "Bathroom",
            "type": "Bathroom",
            "min_area": bath_area,
            "min_width": 4.5,
            "min_height": 4.5,
            "requires_ventilation": False,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Bathroom"))
        
    elif num_bedrooms == 2:
        mbed_area = min(180.0, max(90.0, net_buildable_area * 0.20))
        rooms_config.append({
            "name": "Master Bedroom",
            "type": "Bedroom",
            "min_area": mbed_area,
            "min_width": 9.0,
            "min_height": 9.0,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Master Bedroom"))
        
        bed2_area = min(140.0, max(80.0, net_buildable_area * 0.16))
        rooms_config.append({
            "name": "Bedroom 2",
            "type": "Bedroom",
            "min_area": bed2_area,
            "min_width": 8.5,
            "min_height": 8.5,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Bedroom 2"))
        
        # Two bathrooms for 2 BHK
        bath1_area = min(45.0, max(20.0, net_buildable_area * 0.05))
        rooms_config.append({
            "name": "Master Bath",
            "type": "Bathroom",
            "min_area": bath1_area,
            "min_width": 4.5,
            "min_height": 4.5,
            "requires_ventilation": False,
            "adjacent_to_road": False
        })
        adjacencies.append(("Master Bedroom", "Master Bath"))
        
        bath2_area = min(45.0, max(20.0, net_buildable_area * 0.05))
        rooms_config.append({
            "name": "Common Bath",
            "type": "Bathroom",
            "min_area": bath2_area,
            "min_width": 4.5,
            "min_height": 4.5,
            "requires_ventilation": False,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Common Bath"))
        
    else: # 3 or more BHK
        mbed_area = min(180.0, max(90.0, net_buildable_area * 0.16))
        rooms_config.append({
            "name": "Master Bedroom",
            "type": "Bedroom",
            "min_area": mbed_area,
            "min_width": 9.0,
            "min_height": 9.0,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Master Bedroom"))
        
        bed2_area = min(140.0, max(80.0, net_buildable_area * 0.14))
        rooms_config.append({
            "name": "Bedroom 2",
            "type": "Bedroom",
            "min_area": bed2_area,
            "min_width": 8.5,
            "min_height": 8.5,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Bedroom 2"))
        
        bed3_area = min(120.0, max(80.0, net_buildable_area * 0.12))
        rooms_config.append({
            "name": "Bedroom 3",
            "type": "Bedroom",
            "min_area": bed3_area,
            "min_width": 8.0,
            "min_height": 8.0,
            "requires_ventilation": True,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Bedroom 3"))
        
        bath1_area = min(40.0, max(20.0, net_buildable_area * 0.045))
        rooms_config.append({
            "name": "Master Bath",
            "type": "Bathroom",
            "min_area": bath1_area,
            "min_width": 4.0,
            "min_height": 4.5,
            "requires_ventilation": False,
            "adjacent_to_road": False
        })
        adjacencies.append(("Master Bedroom", "Master Bath"))
        
        bath2_area = min(40.0, max(20.0, net_buildable_area * 0.045))
        rooms_config.append({
            "name": "Common Bath",
            "type": "Bathroom",
            "min_area": bath2_area,
            "min_width": 4.0,
            "min_height": 4.5,
            "requires_ventilation": False,
            "adjacent_to_road": False
        })
        adjacencies.append(("Living Room", "Common Bath"))
        
    # 6. Safety check: scale down rooms if total exceeds 40% of net buildable area
    total_requested_area = sum(r["min_area"] for r in rooms_config)
    safety_target_area = 0.40 * net_buildable_area
    if total_requested_area > safety_target_area:
        scale_factor = safety_target_area / total_requested_area
        scale_factor_dim = math.sqrt(scale_factor)
        for r in rooms_config:
            scaled_area = r["min_area"] * scale_factor
            
            abs_min = 80.0
            if r["type"] == "Entrance":
                abs_min = 9.0
            elif r["type"] == "Kitchen":
                abs_min = 45.0
            elif r["type"] == "Bathroom":
                abs_min = 20.0
            elif r["type"] == "Living Room":
                abs_min = 80.0
                
            r["min_area"] = max(abs_min, scaled_area)
            r["min_width"] = max(3.0, r["min_width"] * scale_factor_dim)
            r["min_height"] = max(3.0, r["min_height"] * scale_factor_dim)
            
    return {
        "stair_core": stair_core,
        "rooms": rooms_config,
        "adjacencies": adjacencies
    }
