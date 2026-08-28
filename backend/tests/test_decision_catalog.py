import json
import pytest
from pathlib import Path

from app.schemas.architectural_analysis import DecisionDimension
from app.services.analysis.catalog_loader import (
    get_catalog_alternatives,
    get_catalog_incompatibilities,
    get_catalog_relationships,
    load_decision_catalog,
)


def test_catalog_loads_default():
    catalog = load_decision_catalog()
    assert isinstance(catalog, dict)
    assert "dimensions" in catalog
    assert "vertical_circulation" in catalog["dimensions"]


def test_catalog_missing_file_raises_not_found(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError):
        load_decision_catalog(non_existent)


def test_catalog_malformed_json_raises_value_error(tmp_path: Path):
    malformed_file = tmp_path / "bad.json"
    malformed_file.write_text("{ this is invalid json ", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed JSON"):
        load_decision_catalog(malformed_file)


def test_get_catalog_alternatives_known_dimension():
    alts = get_catalog_alternatives(DecisionDimension.VERTICAL_CIRCULATION)
    assert isinstance(alts, list)
    assert alts == ["shared", "independent", "hybrid"]


def test_get_catalog_alternatives_unknown_dimension():
    alts = get_catalog_alternatives("completely_unknown_dimension")
    assert isinstance(alts, list)
    assert len(alts) == 0


def test_get_catalog_incompatibilities_and_relationships_serializable():
    incompatibilities = get_catalog_incompatibilities()
    relationships = get_catalog_relationships()

    assert isinstance(incompatibilities, list)
    assert isinstance(relationships, list)

    for incompat in incompatibilities:
        assert isinstance(incompat.model_dump_json(), str)

    for rel in relationships:
        assert isinstance(rel.model_dump_json(), str)


def test_catalog_loader_custom_dynamic_entry(tmp_path: Path):
    custom_catalog = {
        "version": 1,
        "dimensions": {
            "brand_new_dimension": {
                "alternatives": ["A", "B", "C"]
            }
        },
        "incompatibilities": [],
        "relationships": [],
    }
    catalog_file = tmp_path / "custom_catalog.json"
    catalog_file.write_text(json.dumps(custom_catalog), encoding="utf-8")

    loaded = load_decision_catalog(catalog_file)
    alts = get_catalog_alternatives("brand_new_dimension", catalog=loaded)
    assert alts == ["A", "B", "C"]
