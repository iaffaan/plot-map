def test_compile_success(client):
    """Verify that the compile endpoint compiles a valid layout successfully."""
    payload = {"prompt": "1bhk on a 40x40 plot"}
    response = client.post("/api/v1/compile", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["status"] == "success"
    assert "layout" in json_data
    assert "boundaries" in json_data
    assert "metadata" in json_data
    assert "extracted_intent" in json_data
    assert json_data["extracted_intent"]["plot_width"] == 40.0
    assert json_data["extracted_intent"]["plot_depth"] == 40.0

def test_compile_empty_prompt(client):
    """Verify that an empty prompt results in a 400 Bad Request."""
    payload = {"prompt": "   "}
    response = client.post("/api/v1/compile", json=payload)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_compile_infeasible_request(client):
    """Verify that extremely small plot sizes result in an infeasible request error."""
    payload = {"prompt": "Need a 3BHK on a 10x10 plot"}
    response = client.post("/api/v1/compile", json=payload)
    assert response.status_code == 400
    json_data = response.json()
    assert json_data["status"] == "infeasible"
    assert "reason" in json_data
