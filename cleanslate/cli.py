import argparse
import sys
import json
from cleanslate.core import CleanSlate

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
    parser = argparse.ArgumentParser(description="CleanSlate - PII Scrubbing and Extraction Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run: 'scrub' or 'extract'")
    subparsers.required = True

    # Common arguments for both scrub and extract
    parent_parser = argparse.ArgumentParser(add_help=False)
    group = parent_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", type=str, help="Raw text string to process")
    group.add_argument("--file", type=str, help="Path to text file to process")
    parent_parser.add_argument("--entities", type=str, nargs="+", help="Specific entities to target (e.g., EMAIL CREDIT_CARD)")

    # Extract subcommand
    parser_extract = subparsers.add_parser("extract", parents=[parent_parser], help="Extract PII entities from text")
    
    # Scrub subcommand
    parser_scrub = subparsers.add_parser("scrub", parents=[parent_parser], help="Scrub PII entities from text")
    parser_scrub.add_argument("--style", type=str, choices=["tag", "redacted"], default="tag", help="Replacement style: 'tag' (<EMAIL>) or 'redacted' (<REDACTED>)")

    args = parser.parse_args()

    # Read input
    text = get_text_from_args(args)
    
    # Initialize Core Engine
    cs = CleanSlate(entities=args.entities)

    if args.command == "extract":
        results = cs.extract_entities(text)
        print(json.dumps(results, indent=2))
        
    elif args.command == "scrub":
        result = cs.scrub_text(text, replacement_style=args.style)
        print(result)

if __name__ == "__main__":
    main()
