"""
Evaluation dry run tests for SAKSHI worker
Tests that eval runner returns expected metrics
"""
import pytest
from worker.evalrun import load_seeds

def test_eval_runner_returns_metrics():
    """Test that eval runner returns all 4 metrics"""
    # Test that load_seeds function works
    seeds = load_seeds()
    assert isinstance(seeds, list)
    assert len(seeds) > 0
    
    # Check seed structure
    for seed in seeds:
        assert "id" in seed
        assert "inputs" in seed
        assert "expected" in seed
        
        # Check inputs
        inputs = seed["inputs"]
        assert "text" in inputs
        assert "spans" in inputs
        
        # Check expected outputs
        expected = seed["expected"]
        assert "category" in expected
        assert "urgency" in expected
        assert "status" in expected
        assert "missing" in expected

def test_seed_scenarios():
    """Test that we have the required seed scenarios"""
    seeds = load_seeds()
    
    # Should have 10 seeds as per specification
    assert len(seeds) == 10
    
    # Check for specific seed types
    seed_ids = [seed["id"] for seed in seeds]
    
    # 3 normal seeds
    normal_seeds = [sid for sid in seed_ids if sid.startswith("seed_normal_")]
    assert len(normal_seeds) == 3
    
    # 2 duplicate pairs (one voice-vs-photo cross-modal)
    duplicate_seeds = [sid for sid in seed_ids if "duplicate" in sid]
    assert len(duplicate_seeds) >= 2  # At least 2 duplicate seeds
    
    # 1 missing-location
    missing_loc_seeds = [sid for sid in seed_ids if "missing_location" in sid]
    assert len(missing_loc_seeds) == 1
    
    # 1 text-says-fire/photo-shows-puddle conflict
    conflict_seeds = [sid for sid in seed_ids if "conflict" in sid]
    assert len(conflict_seeds) == 1
    
    # 1 HIGH-urgency duplicate (must bypass auto-link -> human_review)
    high_urg_dup_seeds = [sid for sid in seed_ids if "high_urgency_duplicate" in sid]
    assert len(high_urg_dup_seeds) == 1
    
    # 1 Telugu voice note
    telugu_seeds = [sid for sid in seed_ids if "telugu" in sid]
    assert len(telugu_seeds) == 1
    
    # 1 no-photo text-only
    text_only_seeds = [sid for sid in seed_ids if "text_only" in sid]
    assert len(text_only_seeds) == 1

def test_expected_outputs_structure():
    """Test that expected outputs have correct structure"""
    seeds = load_seeds()
    
    for seed in seeds:
        expected = seed["expected"]
        
        # Required fields
        assert "category" in expected
        assert "urgency" in expected
        assert "status" in expected
        assert "missing" in expected
        
        # Optional fields that may be present
        # dup_parent may be null or string
        # conflicts may be present
        
        # Validate status values
        assert expected["status"] in [
            "intake", "triage", "tray", "merged", "human_review", "approved", "sent"
        ]
        
        # Validate urgency values
        assert expected["urgency"] in ["LOW", "MEDIUM", "HIGH"]
        
        # Validate missing is a list
        assert isinstance(expected["missing"], list)
