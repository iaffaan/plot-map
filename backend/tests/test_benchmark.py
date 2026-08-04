import time
import random
from app.services.compiler.serializer import compile_blueprint

def test_performance_benchmarks():
    """
    Performance test suite (Phase 12) simulating compilation across 20 randomized plot sizes
    and floor levels to assess average compile times, failure rates, and timeouts.
    """
    random.seed(42)  # Deterministic test cases
    
    num_runs = 20
    success_count = 0
    total_time = 0.0
    max_time = 0.0
    
    print(f"\n--- STARTING PERFORMANCE BENCHMARK OVER {num_runs} RANDOM PLOT RUNS ---")
    
    for i in range(num_runs):
        width = round(random.uniform(40.0, 50.0), 1)
        depth = round(random.uniform(40.0, 50.0), 1)
        floors = random.choice([1, 2])
        
        # Build realistic program of rooms with correct schemas
        rooms = [
            {"name": "Main Door", "type": "Entrance", "min_width": 3.0, "min_height": 3.0, "min_area": 9.0, "requires_ventilation": False, "adjacent_to_road": True, "floor_assignment": 1},
            {"name": "Living Room", "type": "Living Room", "min_width": 10.0, "min_height": 10.0, "min_area": 100.0, "requires_ventilation": True, "adjacent_to_road": True, "floor_assignment": 1},
            {"name": "Kitchen", "type": "Kitchen", "min_width": 8.0, "min_height": 8.0, "min_area": 64.0, "requires_ventilation": True, "adjacent_to_road": False, "floor_assignment": 1},
            {"name": "Bathroom 1", "type": "Bathroom", "min_width": 5.0, "min_height": 5.0, "min_area": 25.0, "requires_ventilation": True, "adjacent_to_road": False, "floor_assignment": 1}
        ]
        
        adjacencies = [
            ("Main Door", "Living Room"),
            ("Living Room", "Kitchen"),
            ("Living Room", "Bathroom 1")
        ]
        
        if floors > 1:
            rooms.extend([
                {"name": "Bedroom 1", "type": "Bedroom", "min_width": 10.0, "min_height": 10.0, "min_area": 100.0, "requires_ventilation": True, "adjacent_to_road": False, "floor_assignment": 2},
                {"name": "Bathroom 2", "type": "Bathroom", "min_width": 5.0, "min_height": 5.0, "min_area": 25.0, "requires_ventilation": True, "adjacent_to_road": False, "floor_assignment": 2}
            ])
            adjacencies.append(("Bedroom 1", "Bathroom 2"))
        else:
            rooms.extend([
                {"name": "Bedroom 1", "type": "Bedroom", "min_width": 10.0, "min_height": 10.0, "min_area": 100.0, "requires_ventilation": True, "adjacent_to_road": False, "floor_assignment": 1}
            ])
            adjacencies.append(("Living Room", "Bedroom 1"))
            
        payload = {
            "plot": {"width": width, "depth": depth},
            "setbacks": {"left": 3.0, "right": 3.0, "bottom": 5.0, "top": 3.0},
            "stair_core": {"width": 8.0, "height": 8.0, "edge": "bottom-left"},
            "road_edge": "bottom",
            "grid_snap": 0.5,
            "time_limit_sec": 3,
            "floors": floors,
            "rooms": rooms,
            "adjacencies": adjacencies
        }
        
        start_time = time.perf_counter()
        res = compile_blueprint(payload)
        duration = time.perf_counter() - start_time
        
        total_time += duration
        max_time = max(max_time, duration)
        
        if res.get("success", False):
            success_count += 1
            
        # Assert that the compiler respects the time limit and doesn't hang
        assert duration < 5.0, f"Run {i} exceeded safe runtime limit of 5s: {duration:.2f}s"
        
    avg_time = total_time / num_runs
    success_rate = (success_count / num_runs) * 100.0
    
    print(f"Benchmark completed:")
    print(f"  - Success Rate: {success_rate:.1f}% ({success_count}/{num_runs})")
    print(f"  - Average Compile Time: {avg_time:.3f} seconds")
    print(f"  - Max Compile Time: {max_time:.3f} seconds")
    
    # Assert acceptable performance thresholds
    assert success_rate >= 80.0, f"Success rate dropped below 80%: {success_rate:.1f}%"
    assert avg_time < 2.5, f"Average compile time exceeded 2.5s threshold: {avg_time:.3f}s"
