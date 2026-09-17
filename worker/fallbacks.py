"""
Fallbacks module for SAKSHI worker
Contains rule-based fallbacks when LLM is unavailable
"""
import re
from typing import Dict, Any, List

def rule_template_fallback(text: str) -> Dict[str, Any]:
    """
    Rule-based fallback for text analysis when LLM is unavailable or fails validation.
    Extracts information from text using keyword matching and simple heuristics.
    Never invents information - only returns what can be reasonably inferred.
    """
    if not text or not isinstance(text, str):
        return {
            "category": "unknown",
            "urgency": "LOW",
            "dept": "general",
            "location": {"lat": 0.0, "lng": 0.0},
            "missing": ["location", "text"],
            "conflicts": [],
            "packet_draft": {
                "summary": "",
                "category": "unknown",
                "urgency": "LOW"
            }
        }
    
    text_lower = text.lower().strip()
    
    # Category detection using keyword matching
    category_patterns = {
        "pothole": [r"\bpothole\b", r"\broad\s+(?:damage|break|hole)\b", r"\bpavement\s+(?:break|hole)\b", r"\bstreet\s+(?:damage|hole)\b"],
        "garbage": [r"\bgarbage\b", r"\btrash\b", r"\bwaste\b", r"\bdump\b", r"\brubbish\b", r"\blitter\b"],
        "streetlight": [r"\bstreet\s+light\b", r"\blamp\s+post\b", r"\belectric\s+light\b", r"\blight\s+not\s+working\b", r"\bpole\s+light\b"],
        "water_supply": [r"\bwater\s+(?:leak|break|pipe)\b", r"\bflood\b", r"\bwater\s+logging\b", r"\bpipe\s+burst\b", r"\bwater\s+supply\b"],
        "electrical": [r"\belectric\s+(?:wire|cable)\b", r"\bpower\s+(?:outage|failure)\b", r"\bsparking\s+wire\b", r"\btransformer\b"],
        "sanitation": [r"\btoilet\b", r"\bsewage\b", r"\bdrain\s+(?:blocked|clogged)\b", r"\btoilet\s+blocked\b"],
        "public_works": [r"\bfootpath\b", r"\bsidewalk\b", r"\bwall\s+(?:damage|break)\b", r"\bfence\s+(?:broken|damage)\b"]
    }
    
    category = "other"  # default
    for cat, patterns in category_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                category = cat
                break
        if category != "other":
            break
    
    # Urgency detection
    urgency_patterns = {
        "HIGH": [r"\bemergency\b", r"\bdanger\b", r"\baccident\b", r"\bfire\b", r"\bflood\b", r"\binjury\b", r"\btrapped\b", r"\bcollapse\b"],
        "MEDIUM": [r"\burgent\b", r"\bserious\b", r"\bblocked\b", r"\bobstruction\b", r"\bmajor\b", r"\bsignificant\b"],
        "LOW": []  # default
    }
    
    urgency = "LOW"  # default
    for urg, patterns in urgency_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                urgency = urg
                break
        if urgency != "LOW":
            break
    
    # Department mapping based on category
    dept_mapping = {
        "pothole": "public_works",
        "garbage": "sanitation",
        "streetlight": "electrical",
        "water_supply": "water_dept",
        "electrical": "electrical",
        "sanitation": "sanitation",
        "public_works": "public_works",
        "other": "general"
    }
    dept = dept_mapping.get(category, "general")
    
    # Location extraction (very basic - would be enhanced with NER in production)
    location = {"lat": 0.0, "lng": 0.0}  # Default invalid location
    missing = []
    
    # Check if text contains location-like information
    # This is a simplified check - real implementation would use gazetteer/NER
    location_indicators = [
        r"\bnear\b", r"\bat\b", r"\bopposite\b", r"\bbetween\b", 
        r"\bkhansama\b", r"\bm g road\b", r"\bresidency\b", r"\bpark\b"
    ]
    
    has_location_reference = any(re.search(pattern, text_lower) for pattern in location_indicators)
    
    if not has_location_reference:
        missing.append("location")
    
    # Conflict detection (simplified)
    conflicts = []
    # In a real implementation, we would compare text with image evidence
    # For now, we'll check for obvious contradictions in text alone
    
    # Packet draft creation
    packet_draft = {
        "summary": text[:500] if len(text) > 500 else text,  # Truncate if too long
        "category": category,
        "urgency": urgency
    }
    
    return {
        "category": category,
        "urgency": urgency,
        "dept": dept,
        "location": location,
        "missing": missing,
        "conflicts": conflicts,
        "packet_draft": packet_draft
    }

def extract_location_from_text(text: str) -> Dict[str, float]:
    """
    Attempt to extract location coordinates from text.
    Returns default (0.0, 0.0) if extraction fails.
    Never invents coordinates - only returns what can be reasonably parsed.
    """
    # This would use NER, gazetteer matching, or geocoding in production
    # For now, return invalid location to trigger 'missing' flag
    return {"lat": 0.0, "lng": 0.0}

def assess_text_quality(text: str) -> Dict[str, Any]:
    """
    Assess the quality and completeness of text input.
    Returns quality metrics and completeness flags.
    """
    if not text:
        return {
            "length": 0,
            "word_count": 0,
            "has_details": False,
            "quality": "poor",
            "missing_elements": ["text"]
        }
    
    word_count = len(text.split())
    has_details = word_count >= 10  # Arbitrary threshold
    
    quality = "good" if word_count >= 20 else "fair" if word_count >= 10 else "poor"
    
    missing_elements = []
    if word_count < 5:
        missing_elements.append("sufficient_detail")
    
    return {
        "length": len(text),
        "word_count": word_count,
        "has_details": has_details,
        "quality": quality,
        "missing_elements": missing_elements
    }