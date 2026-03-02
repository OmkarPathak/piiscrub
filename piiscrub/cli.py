import argparse
import sys
import re
import json
from piiscrub.core import PiiScrub

def get_text_from_args(args) -> str:
    if args.text is not None:
        return args.text
    elif args.file is not None:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                return f.read()
        except IOError as e:
            print(f"Error reading file {args.file}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: Must provide either --text or --file.", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="PiiScrub - PII Scrubbing and Extraction Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run: 'scrub' or 'extract'")
    subparsers.required = True

    # Common arguments for both scrub and extract
    parent_parser = argparse.ArgumentParser(add_help=False)
    group = parent_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", type=str, help="Raw text string to process")
    group.add_argument("--file", type=str, help="Path to text file to process")
    parent_parser.add_argument("--entities", type=str, nargs="+", help="Specific entities to target (e.g., EMAIL CREDIT_CARD)")
    parent_parser.add_argument("--allowlist", type=str, nargs="+", help="Specific strings to bypass scrubbing (e.g., support@example.com)")
    parent_parser.add_argument("--custom-pattern", nargs=2, action="append", metavar=("NAME", "REGEX"), help="Inject a custom regex pattern. Can be used multiple times. Example: --custom-pattern TICKET_ID '\\bPROJ-\\d{4}\\b'")
    parent_parser.add_argument("--stream", action="store_true", help="Process the file chunk-by-chunk using a generator to avoid Out-Of-Memory errors on huge files.")

    # Extract subcommand
    parser_extract = subparsers.add_parser("extract", parents=[parent_parser], help="Extract PII entities from text")
    
    # Scrub subcommand
    parser_scrub = subparsers.add_parser("scrub", parents=[parent_parser], help="Scrub PII entities from text")
    parser_scrub.add_argument("--style", type=str, choices=["tag", "redacted", "hash"], default="tag", help="Replacement style: 'tag' (<EMAIL>), 'redacted' (<REDACTED>), or 'hash' (<EMAIL_a1b2c3d4>)")

    args = parser.parse_args()

    # Process custom patterns
    custom_patterns_dict = {}
    if args.custom_pattern:
        for name, pattern_str in args.custom_pattern:
            try:
                custom_patterns_dict[name] = re.compile(pattern_str)
            except re.error as e:
                print(f"Error compiling regex for {name}: {e}", file=sys.stderr)
                sys.exit(1)

    # Initialize Core Engine
    cs = PiiScrub(
        entities=args.entities, 
        allowlist=args.allowlist,
        custom_patterns=custom_patterns_dict if custom_patterns_dict else None
    )

    if args.stream and not args.file:
        print("Error: --stream requires --file.", file=sys.stderr)
        sys.exit(1)

    if args.stream:
        # Streaming logic for files
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                if args.command == "extract":
                    results = cs.extract_stream(f)
                    print(json.dumps(results, indent=2))
                elif args.command == "scrub":
                    for scrubbed_line in cs.scrub_stream(f, replacement_style=args.style):
                        # scrub_text might preserve newlines if matching line by line, 
                        # but typically f yields lines with \n attached
                        sys.stdout.write(scrubbed_line)
        except IOError as e:
            print(f"Error reading file {args.file}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Traditional in-memory logic
        text = get_text_from_args(args)
        
        if args.command == "extract":
            results = cs.extract_entities(text)
            print(json.dumps(results, indent=2))
            
        elif args.command == "scrub":
            result = cs.scrub_text(text, replacement_style=args.style)
            print(result)

if __name__ == "__main__":
    main()
