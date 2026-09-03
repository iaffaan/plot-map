from typing import Any

from app.schemas.explanation import DesignExplanation

EXPLAINER_SYSTEM_PROMPT = (
    "You are an expert architectural consultant. "
    "Your task is to analyze a compiled building layout and explain the design decisions "
    "behind it in a professional, clear, and reassuring tone. "
    "Focus on how the layout maximizes natural light, ventilation, plumbing efficiency, "
    "and Vastu Shastra principles based on the room positions and metrics provided."
)

def explain_layout_fallback(prompt: str, layout_data: dict[str, Any]) -> DesignExplanation:
    """
    Rule-based local fallback to provide design explanations when Gemini is unavailable.
    """
    metadata = layout_data.get("metadata", {})
    plot_w = metadata.get("plot_width", 40.0)
    plot_d = metadata.get("plot_depth", 40.0)
    floors = metadata.get("floors_count", 1)
    metrics = layout_data.get("metrics", {})
    
    overall = (
        f"A customized G+{floors-1} floor plan meticulously optimized for a {plot_w}x{plot_d} ft plot. "
        f"By honoring setbacks, the layout creates a buildable footprint of {metadata.get('buildable_area_sqft', 0.0)} sqft, "
        f"yielding a total Floor Area Ratio (FAR) of {metrics.get('far', 0.0)}."
    )
    
    kitchen = (
        "The kitchen is positioned along the outer boundaries to leverage setbacks. "
        "This facilitates external window integration, ensuring morning daylighting and direct extraction of heat and exhaust."
    )
    
    plumbing = (
        "Vertical wet walls are aligned across floors. Bathrooms are stacked directly above "
        "one another or situated adjacent to the primary shafts, keeping wastewater drops short and vertical."
    )
    
    vastu = (
        "Room placement is zoned based on orientation. The entrance is kept open, "
        "and primary living spaces are organized to maximize cross-ventilation, respecting standard solar path guidelines."
    )
    
    circulation = (
        f"Circulation is optimized with an accessibility score of {metrics.get('accessibility_score', 90.0)}. "
        "Corridor space is minimized to maximize room sizes, keeping pathways clear and avoiding winding passages."
    )
    
    return DesignExplanation(
        overall_concept=overall,
        kitchen_placement=kitchen,
        plumbing_efficiency=plumbing,
        vastu_compliance=vastu,
        circulation_efficiency=circulation
    )

def explain_layout(
    prompt: str,
    layout_data: dict[str, Any],
    client: Any = None,
    ai_state: dict[str, Any] | None = None,
) -> DesignExplanation:
    """
    Generates a structured architectural explanation of the compiled layout.
    Uses Gemini if client is available; otherwise falls back to a rule-based generator.
    """
    if client is not None and not (ai_state and ai_state.get("compiler_failed")):
        try:
            # Format compiled data details for the model prompt
            metadata = layout_data.get("metadata", {})
            metrics = layout_data.get("metrics", {})
            floors = layout_data.get("floors", {})
            
            floor_summary = []
            for f_idx, f_data in floors.items():
                rooms = list(f_data.get("layout", {}).keys())
                floor_summary.append(f"Floor {f_idx}: {', '.join(rooms)}")
                
            input_summary = (
                f"Original User Request: '{prompt}'\n"
                f"Plot Dimensions: {metadata.get('plot_width')} x {metadata.get('plot_depth')} ft\n"
                f"Floor Count: {metadata.get('floors_count')}\n"
                f"FAR: {metrics.get('far')}\n"
                f"Plot Coverage: {metrics.get('plot_coverage_pct')}%\n"
                f"Daylighting Score: {metrics.get('daylighting_score')}/100\n"
                f"Cross Ventilation Score: {metrics.get('cross_ventilation_score')}/100\n"
                f"Buildability Score: {metrics.get('buildability_score')}/100\n"
                f"Privacy Score: {metrics.get('privacy_score')}/100\n"
                f"Floor Layouts:\n" + "\n".join(floor_summary)
            )
            
            model_name = "nvidia/nemotron-3.5-lightning-30b-a3b"
            from app.core.config import settings
            if hasattr(settings, "NVIDIA_MODEL") and settings.NVIDIA_MODEL:
                model_name = settings.NVIDIA_MODEL

            raw_exp = None
            if hasattr(client, "create"):
                raw_exp = client.create(
                    model=model_name,
                    response_model=DesignExplanation,
                    max_retries=1,
                    messages=[
                        {
                            "role": "system",
                            "content": EXPLAINER_SYSTEM_PROMPT
                        },
                        {
                            "role": "user",
                            "content": f"Analyze this compiled layout and explain the design:\n\n{input_summary}"
                        }
                    ]
                )
            elif hasattr(client, "chat") and hasattr(client.chat, "completions"):
                raw_exp = client.chat.completions.create(
                    model=model_name,
                    response_model=DesignExplanation,
                    max_retries=1,
                    messages=[
                        {
                            "role": "system",
                            "content": EXPLAINER_SYSTEM_PROMPT
                        },
                        {
                            "role": "user",
                            "content": f"Analyze this compiled layout and explain the design:\n\n{input_summary}"
                        }
                    ]
                )
            elif hasattr(client, "models") and hasattr(client.models, "generate_content"):
                from google.genai import types
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=f"{EXPLAINER_SYSTEM_PROMPT}\n\nAnalyze this compiled layout and explain the design:\n\n{input_summary}",
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=DesignExplanation,
                    )
                )
                raw_exp = response.text
            else:
                raise AttributeError("Unsupported client type: client does not support OpenAI chat.completions or create")

            if isinstance(raw_exp, DesignExplanation):
                return raw_exp
            elif isinstance(raw_exp, str):
                return DesignExplanation.model_validate_json(raw_exp)
            else:
                return raw_exp
        except Exception as e:  # noqa: BLE001
            print(f"[AI Explainer] LLM call failed ({e}). Falling back to rule-based explainer...")
            
    return explain_layout_fallback(prompt, layout_data)
