"""
Core engine of CleanSlate. Provide classes and methods to scrub and extract PII.
"""
from typing import Optional, List, Dict
import re
from .patterns import COMPILED_PATTERNS
from .validators import validate_credit_card, validate_ipv4, validate_aadhaar

# Map entities to their specific validation functions
_VALIDATORS = {
    "CREDIT_CARD": validate_credit_card,
    "IPV4": validate_ipv4,
    "IN_AADHAAR": validate_aadhaar
}

class CleanSlate:
    def __init__(self, entities: Optional[List[str]] = None):
        """
        Initialize CleanSlate engine.
        
        Args:
            entities: Optional list of entity names to process. If None, all are loaded.
        """
        self.entities = entities if entities is not None else list(COMPILED_PATTERNS.keys())
        # Filter for only valid entity names
        self.entities = [e for e in self.entities if e in COMPILED_PATTERNS]

    def _is_valid_match(self, entity_name: str, match_text: str) -> bool:
        """Check if the matched text passes the algorithmic checksums for the given entity."""
        validator = _VALIDATORS.get(entity_name)
        if validator:
            return validator(match_text)
        return True

    def scrub_text(self, text: str, replacement_style: str = "tag") -> str:
        """
        Replace valid PII in the text with placeholders.
        
        Args:
            text: Raw input text.
            replacement_style: Either "tag" (e.g., <EMAIL>) or "redacted" (<REDACTED>).
            
        Returns:
            Scrubbed text.
        """
        scrubbed_text = text
        for entity in self.entities:
            pattern = COMPILED_PATTERNS[entity]
            replacement = f"<{entity}>" if replacement_style == "tag" else "<REDACTED>"
            
            # Use a replace function that validates before replacing
            def replace_match(match):
                match_text = match.group(0)
                if self._is_valid_match(entity, match_text):
                    return replacement
                return match_text
                
            scrubbed_text = pattern.sub(replace_match, scrubbed_text)
            
        return scrubbed_text

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract valid PII from the text.
        
        Args:
            text: Raw input text.
            
        Returns:
            A dictionary mapping entity names to a list of matched and validated strings.
        """
        found_entities = {}
        for entity in self.entities:
            pattern = COMPILED_PATTERNS[entity]
            matches = pattern.findall(text)
            
            # findall might return tuples if there are capturing groups.
            # However, our patterns do not use capturing groups returning tuples (they use non-capturing or match bounds).
            # Clean up the output string if necessary
            valid_matches = []
            for match in matches:
                # findall with no capturing groups returns string. If the pattern changes and returns tuples, this needs handle.
                # Current raw patterns return strings.
                if isinstance(match, tuple):
                    match_str = match[0] # Fallback in case a group gets introduced
                else:
                    match_str = match
                    
                if self._is_valid_match(entity, match_str):
                    valid_matches.append(match_str)
                    
            if valid_matches:
                found_entities[entity] = valid_matches
                
        return found_entities

    def scrub_stream(self, file_iterator, replacement_style: str = "tag"):
        """
        Yields scrubbed lines from a file iterator to prevent OOM errors on large datasets.
        
        Args:
            file_iterator: An iterator yielding lines of text (e.g., a file object).
            replacement_style: Either "tag" (e.g., <EMAIL>) or "redacted" (<REDACTED>).
            
        Yields:
            Scrubbed lines of text.
        """
        for line in file_iterator:
            yield self.scrub_text(line, replacement_style=replacement_style)

    def extract_stream(self, file_iterator) -> Dict[str, List[str]]:
        """
        Extract valid PII from a file iterator, aggregating results.
        Automatically deduplicates results per entity to prevent memory blowup on large files.
        
        Args:
            file_iterator: An iterator yielding lines of text.
            
        Returns:
            A dictionary mapping entity names to a list of matched and validated strings.
        """
        found_entities = {}
        for line in file_iterator:
            line_entities = self.extract_entities(line)
            for entity, matches in line_entities.items():
                if entity not in found_entities:
                    found_entities[entity] = set()
                found_entities[entity].update(matches)
                
        # Convert sets back to lists for JSON serialization compatibility
        return {k: list(v) for k, v in found_entities.items()}
