"""
Core engine of PiiScrub. Provide classes and methods to scrub and extract PII.
"""
import re
import hashlib
import json
import csv
import io
from typing import Optional, List, Dict, Generator, Any, Union
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
        Replace valid PII in the text with placeholders or hashes in a single pass.
        This prevents nested redaction tags (e.g., <EMAIL_<PHONE_...>>) by ensuring
        each part of the text is replaced at most once.
        
        Args:
            text: Raw input text.
            replacement_style: "tag" (<EMAIL>), "redacted" (<REDACTED>), "hash" (sha256 hex), or "synthetic".
            
        Returns:
            Scrubbed text.
        """
        import hashlib
        
        # Collect all valid matches across all entities
        all_matches = []
        for entity in self.entities:
            pattern = self.patterns[entity]
            for match in pattern.finditer(text):
                match_text = match.group(0)
                if self._is_valid_match(entity, match_text):
                    all_matches.append({
                        'start': match.start(),
                        'end': match.end(),
                        'entity': entity,
                        'text': match_text
                    })
        
        # Sort matches by start position, then by length (descending) 
        # to prefer longer matches if they start at the same index.
        all_matches.sort(key=lambda x: (x['start'], -(x['end'] - x['start'])))
        
        # Build the scrubbed text in a single pass
        scrubbed_parts = []
        last_index = 0
        
        for m in all_matches:
            if m['start'] < last_index:
                # Skip overlapping matches
                continue
                
            # Append text before the match
            scrubbed_parts.append(text[last_index:m['start']])
            
            # Record stat
            self.stats[m['entity']] = self.stats.get(m['entity'], 0) + 1
            
            # Generate replacement
            replacement = ""
            if replacement_style == "hash":
                hashed = hashlib.sha256(m['text'].encode('utf-8')).hexdigest()[:8]
                replacement = f"<{m['entity']}_{hashed}>"
            elif replacement_style == "redacted":
                replacement = "<REDACTED>"
            elif replacement_style == "synthetic" and self.fake:
                fake_method_name = _FAKER_MAPPING.get(m['entity'])
                if fake_method_name and hasattr(self.fake, fake_method_name):
                    replacement = str(getattr(self.fake, fake_method_name)())
                else:
                    replacement = f"<{m['entity']}_FAKE>"
            else:
                replacement = f"<{m['entity']}>"
            
            scrubbed_parts.append(replacement)
            last_index = m['end']
            
        # Append remaining text
        scrubbed_parts.append(text[last_index:])
        
        return "".join(scrubbed_parts)

    def scrub_json(self, data: Any, keys_to_scrub: Optional[List[str]] = None, replacement_style: str = "tag") -> Any:
        """
        Recursively scrub PII from a JSON-like object (dict or list).
        If keys_to_scrub is provided, only those keys are targeted.
        Otherwise, all string values are scrubbed.
        """
        if isinstance(data, dict):
            new_dict = {}
            for k, v in data.items():
                if keys_to_scrub is None or k in keys_to_scrub:
                    new_dict[k] = self.scrub_json(v, keys_to_scrub=None, replacement_style=replacement_style)
                else:
                    new_dict[k] = self.scrub_json(v, keys_to_scrub=keys_to_scrub, replacement_style=replacement_style)
            return new_dict
        elif isinstance(data, list):
            return [self.scrub_json(item, keys_to_scrub=keys_to_scrub, replacement_style=replacement_style) for item in data]
        elif isinstance(data, str):
            if keys_to_scrub is None:
                return self.scrub_text(data, replacement_style=replacement_style)
            return data
        else:
            return data

    def scrub_csv(self, file_iterator, columns_to_scrub: List[str], replacement_style: str = "tag") -> Generator[str, None, None]:
        """
        Scrub specific columns in a CSV file.
        Yields scrubbed rows as CSV strings.
        """
        reader = csv.DictReader(file_iterator)
        fieldnames = reader.fieldnames
        if not fieldnames:
            return

        # Yield header
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)

        for row in reader:
            for col in columns_to_scrub:
                if col in row and row[col]:
                    row[col] = self.scrub_text(row[col], replacement_style=replacement_style)
            writer.writerow(row)
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

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
