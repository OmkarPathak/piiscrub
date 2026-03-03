"""
Core engine of PiiScrub. Provide classes and methods to scrub and extract PII.
"""
import re
import hashlib
from typing import Optional, List, Dict, Generator
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from .patterns import COMPILED_PATTERNS
from .validators import validate_credit_card, validate_ipv4, validate_aadhaar

try:
    from faker import Faker
except ImportError:
    Faker = None

# Map entities to their specific validation functions
_VALIDATORS = {
    "CREDIT_CARD": validate_credit_card,
    "IPV4": validate_ipv4,
    "IN_AADHAAR": validate_aadhaar
}

# Map entities to Faker methods
_FAKER_MAPPING = {
    "EMAIL": "email",
    "PHONE_GENERIC": "phone_number",
    "CREDIT_CARD": "credit_card_number",
    "IPV4": "ipv4",
    "IPV6": "ipv6",
    "US_SSN": "ssn",
    "IN_AADHAAR": "aadhaar_id", # Requires Faker-ID locale or similar, fallback to random if not available
}

class PiiScrub:
    def __init__(
        self, 
        entities: Optional[List[str]] = None,
        profile: Optional[str] = None,
        custom_patterns: Optional[Dict[str, re.Pattern]] = None,
        custom_validators: Optional[Dict[str, callable]] = None,
        allowlist: Optional[List[str]] = None
    ):
        """
        Initialize PiiScrub engine.
        
        Args:
            entities: Optional list of entity names to process. If None, all are loaded.
            profile: Optional pre-bundled compliance profile name (e.g., "pci-dss", "hipaa").
            custom_patterns: Optional dictionary mapping new entity names to compiled regex patterns.
            custom_validators: Optional dictionary mapping entity names to validation functions returning bool.
            allowlist: Optional list of exact strings to ignore (e.g., ["support@example.com"]).
        """
        self.allowlist = set(allowlist) if allowlist else set()
        
        if Faker:
            self.fake = Faker()
        else:
            self.fake = None
        
        # Merge default patterns with custom patterns
        self.patterns = COMPILED_PATTERNS.copy()
        if custom_patterns:
            self.patterns.update(custom_patterns)
            
        # Merge default validators with custom validators
        self.validators = _VALIDATORS.copy()
        if custom_validators:
            self.validators.update(custom_validators)
            
        from .profiles import COMPLIANCE_PROFILES
        if profile and profile in COMPLIANCE_PROFILES:
            profile_entities = COMPLIANCE_PROFILES[profile]
            self.entities = profile_entities if profile_entities is not None else list(self.patterns.keys())
        else:
            self.entities = entities if entities is not None else list(self.patterns.keys())
            
        # Filter for only valid entity names
        self.entities = [e for e in self.entities if e in self.patterns]
        self.stats = {}

    def get_stats(self) -> Dict[str, int]:
        """Return the current redaction statistics."""
        return self.stats

    def reset_stats(self):
        """Reset the redaction statistics."""
        self.stats = {}

    def _is_valid_match(self, entity_name: str, match_text: str) -> bool:
        """Check if the matched text passes the algorithmic checksums for the given entity."""
        if match_text in self.allowlist:
            return False
            
        validator = self.validators.get(entity_name)
        if validator:
            return validator(match_text)
        return True

    def scrub_text(self, text: str, replacement_style: str = "tag") -> str:
        """
        Replace valid PII in the text with placeholders or hashes.
        
        Args:
            text: Raw input text.
            replacement_style: "tag" (<EMAIL>), "redacted" (<REDACTED>), or "hash" (sha256 hex).
            
        Returns:
            Scrubbed text.
        """
        import hashlib
        scrubbed_text = text
        for entity in self.entities:
            pattern = self.patterns[entity]
            
            # Use a replace function that validates before replacing
            def replace_match(match):
                match_text = match.group(0)
                if self._is_valid_match(entity, match_text):
                    # Increment stats
                    self.stats[entity] = self.stats.get(entity, 0) + 1
                    
                    if replacement_style == "hash":
                        # Return an 8-character deterministic hash prefix to save tokens
                        # but still allow matching identical entities in datasets.
                        hashed = hashlib.sha256(match_text.encode('utf-8')).hexdigest()[:8]
                        return f"<{entity}_{hashed}>"
                    elif replacement_style == "redacted":
                        return "<REDACTED>"
                    elif replacement_style == "synthetic" and self.fake:
                        fake_method_name = _FAKER_MAPPING.get(entity)
                        if fake_method_name and hasattr(self.fake, fake_method_name):
                            return getattr(self.fake, fake_method_name)()
                        return f"<{entity}_FAKE>"
                    else:
                        return f"<{entity}>"
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
            pattern = self.patterns[entity]
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
                    # Increment stats
                    self.stats[entity] = self.stats.get(entity, 0) + 1
                    
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

    def scrub_file_parallel(
        self, 
        input_path: str, 
        output_path: str, 
        replacement_style: str = "tag", 
        n_cores: Optional[int] = None,
        chunk_size: int = 1000
    ):
        """
        Scrub a large file in parallel using multiple cores.
        """
        if n_cores is None:
            n_cores = multiprocessing.cpu_count()

        with open(input_path, 'r', encoding='utf-8') as f_in, \
             open(output_path, 'w', encoding='utf-8') as f_out:
            
            with ProcessPoolExecutor(max_workers=n_cores) as executor:
                # We process the file in chunks to balance memory and parallelism
                chunk = []
                futures = []
                
                for line in f_in:
                    chunk.append(line)
                    if len(chunk) >= chunk_size:
                        futures.append(executor.submit(_process_chunk, self, chunk, replacement_style))
                        chunk = []
                
                if chunk:
                    futures.append(executor.submit(_process_chunk, self, chunk, replacement_style))
                
                for future in futures:
                    scrubbed_lines, chunk_stats = future.result()
                    f_out.writelines(scrubbed_lines)
                    # Aggregate stats from workers
                    for entity, count in chunk_stats.items():
                        self.stats[entity] = self.stats.get(entity, 0) + count

def _process_chunk(engine: PiiScrub, chunk: List[str], replacement_style: str) -> tuple[List[str], Dict[str, int]]:
    """Helper function for parallel processing (must be at top level for pickling)."""
    engine.reset_stats()
    processed = [engine.scrub_text(line, replacement_style=replacement_style) for line in chunk]
    return processed, engine.get_stats()
