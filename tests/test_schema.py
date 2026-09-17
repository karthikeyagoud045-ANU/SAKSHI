"""
Schema tests for SAKSHI worker
Tests AnalysisOut validation and fallback behavior
"""
import pytest
from worker.schemas import AnalysisOut, FieldOutput, TextInput
from worker.fallbacks import rule_template_fallback

def test_analysis_out_validates():
    """Test that AnalysisOut validates correct data"""
    # Valid data
    data = {
        "category": {"value": "pothole", "confidence": 0.9, "evidence": ["evidence1"]},
        "urgency": {"value": "MEDIUM", "confidence": 0.8, "evidence": ["evidence1"]},
        "department": {"value": "public_works", "confidence": 0.85, "evidence": ["evidence1"]},
        "location": {"value": {"lat": 12.9716, "lng": 77.5946}, "confidence": 0.9, "evidence": ["evidence2"]},
        "missing": [],
        "conflicts": [],
        "dup_score": 0.75,
        "parent_id": None,
        "status": "intake",
        "packet_draft": {"summary": "Test complaint", "category": "pothole", "urgency": "MEDIUM"}
    }
    
    # Should validate without error
    analysis = AnalysisOut(**data)
    assert analysis.category.value == "pothole"
    assert analysis.urgency.value == "MEDIUM"
    assert analysis.status == "intake"

def test_bad_llm_json_fallback_uncertain():
    """Test that bad LLM JSON triggers fallback to UNCERTAIN"""
    # This would test the analyze endpoint's behavior when LLM returns invalid JSON
    # For now, test the fallback function directly
    
    # Empty text should trigger fallback
    result = rule_template_fallback("")
    assert result["category"] == "unknown"
    assert result["urgency"] == "LOW"
    assert "missing" in result
    assert "text" in result["missing"]
    
    # None text should trigger fallback
    result = rule_template_fallback(None)
    assert result["category"] == "unknown"
    assert result["urgency"] == "LOW"

def test_field_output_validation():
    """Test FieldOutput validation"""
    # Valid FieldOutput
    field = FieldOutput(value="test", confidence=0.9, evidence=["ev1", "ev2"])
    assert field.value == "test"
    assert field.confidence == 0.9
    assert field.evidence == ["ev1", "ev2"]
    
    # Test confidence bounds (0.0 to 1.0)
    field = FieldOutput(value="test", confidence=0.0, evidence=[])
    assert field.confidence == 0.0
    
    field = FieldOutput(value="test", confidence=1.0, evidence=["ev1"])
    assert field.confidence == 1.0
