import os
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
import openai
import instructor
from dotenv import load_dotenv
from intent_schema import CompilerIntent
from geometry_compiler import BuildingCompiler

# Load .env file
load_dotenv()

app = FastAPI(
    title="Uncharted | Constraint-Driven Building Compiler AI Layer",
    description="FastAPI router and LLM orchestration parsing layer for spatial compilation.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize instructor with Gemini provider using google-genai
gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
client = None

if gemini_api_key:
    try:
        client = instructor.from_provider(
            model="google/gemini-2.5-flash",
            api_key=gemini_api_key
        )
        print("[AI Layer] Gemini client successfully initialized.")
    except Exception as e:
        print(f"[WARNING] Failed to initialize Gemini client: {e}")
else:
    print("[WARNING] GEMINI_API_KEY or GOOGLE_API_KEY not found in environment. Gemini client is disabled.")

class CompileRequest(BaseModel):
    """
    Request model containing the unstructured natural language prompt from the user.
    """
    prompt: str

@app.post("/api/compile", status_code=200)
def compile_layout_endpoint(request: CompileRequest):
    """
    POST endpoint that takes a natural language description, extracts structured constraints
    using gpt-4o and instructor, validates them, and executes the math engine.
    """
    if not request.prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty."
        )
    try:
        if client is None:
            raise ValueError("Gemini API key is not configured; client is not initialized.")
        # Call the LLM to parse user intent into the CompilerIntent schema using Gemini
        intent: CompilerIntent = client.create(
            response_model=CompilerIntent,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a deterministic Natural Language Parser for an architectural constraint engine. "
                        "Your ONLY objective is to extract parameters into strict JSON. DO NOT design the house. "
                        "DO NOT calculate coordinates. If a user asks for a 'G+1' house, that equals 2 floors. "
                        "Use standard Indian minimums if dimensions are missing."
                    )
                },
                {
                    "role": "user",
                    "content": request.prompt
                }
            ]
        )
    except ValidationError as val_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Pydantic Validation Failed during LLM structured extraction: {val_err.errors()}"
        )
    except Exception as exc:
        # Heuristic rule-based fallback parser for local testing if OpenAI API Key is missing or invalid
        import re
        from intent_schema import RoomIntent, RoomCategory
        
        print(f"[AI Layer] LLM call failed ({exc}). Using local rule-based parser fallback...")
        
        # 1. Parse plot dimensions (e.g., "40x40", "43.75x41")
        width, depth = 40.0, 40.0
        dim_match = re.search(r'(\d+(?:\.\d+)?)\s*[x×*]\s*(\d+(?:\.\d+)?)', request.prompt)
        if dim_match:
            width = float(dim_match.group(1))
            depth = float(dim_match.group(2))
            
        # 2. Parse floor count (e.g., "G+1" -> 2, "G+2" -> 3)
        floors = 1
        floor_match = re.search(r'g\+(\d+)', request.prompt, re.IGNORECASE)
        if floor_match:
            floors = int(floor_match.group(1)) + 1
        else:
            num_floor_match = re.search(r'(\d+)\s*floor', request.prompt, re.IGNORECASE)
            if num_floor_match:
                floors = int(num_floor_match.group(1))
                
        # 3. Parse setback (e.g., "setback of 5.0")
        setback = 5.0
        setback_match = re.search(r'setback\s+(?:of\s+)?(\d+(?:\.\d+)?)', request.prompt, re.IGNORECASE)
        if setback_match:
            setback = float(setback_match.group(1))
            
        # 4. Parse rooms based on enum category matches
        rooms = []
        for cat in RoomCategory:
            if cat.value in request.prompt.lower():
                count = 1
                # Check for counts (e.g., "2 bedrooms")
                count_match = re.search(r'(\d+)\s*' + cat.value, request.prompt, re.IGNORECASE)
                if count_match:
                    count = int(count_match.group(1))
                for _ in range(count):
                    rooms.append(RoomIntent(room_type=cat))
                    
        # Fallback default room list if none matched
        if not rooms:
            rooms = [
                RoomIntent(room_type=RoomCategory.BEDROOM),
                RoomIntent(room_type=RoomCategory.LIVING),
                RoomIntent(room_type=RoomCategory.KITCHEN),
                RoomIntent(room_type=RoomCategory.BATHROOM)
            ]
            
        intent = CompilerIntent(
            plot_width=width,
            plot_depth=depth,
            floors=floors,
            front_road_setback=setback,
            rooms=rooms
        )

    try:
        # Instantiate BuildingCompiler and apply setbacks
        compiler = BuildingCompiler(
            plot_width=intent.plot_width,
            plot_depth=intent.plot_depth
        )
        compiler.apply_setbacks(
            front=intent.front_road_setback,
            back=3.0,
            sides=3.0
        )
    except Exception as engine_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Math Engine initialization/execution failed: {str(engine_err)}"
        )

    # Calculate envelope setbacks based on front setback and 3.0 ft side/back setbacks
    front_setback = intent.front_road_setback
    side_setback = 3.0
    back_setback = 3.0
    
    env_w = max(0.0, intent.plot_width - (2 * side_setback))
    env_d = max(0.0, intent.plot_depth - front_setback - back_setback)
    buildable_area = env_w * env_d

    return {
        "status": "success",
        "success": True,
        "message": "Math Engine Executed Successfully",
        "extracted_intent": intent.model_dump(),
        "layout": {},
        "boundaries": {
            "plot": [
                [0.0, 0.0],
                [intent.plot_width, 0.0],
                [intent.plot_width, intent.plot_depth],
                [0.0, intent.plot_depth]
            ],
            "envelope": [
                [side_setback, front_setback],
                [intent.plot_width - side_setback, front_setback],
                [intent.plot_width - side_setback, intent.plot_depth - back_setback],
                [side_setback, intent.plot_depth - back_setback]
            ]
        },
        "metadata": {
            "buildable_area_sqft": buildable_area,
            "ots_generated_count": 0
        }
    }

@app.get("/health")
def health_check():
    """
    Basic health check endpoint.
    """
    return {"status": "healthy"}
