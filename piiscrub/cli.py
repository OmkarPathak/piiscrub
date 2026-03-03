import argparse
import sys
import re
import json
import os
import time
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

def load_config(config_path=None):
    """Load configuration from a JSON file."""
    path = config_path or "piiscrub.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load config file {path}: {e}", file=sys.stderr)
    return {}

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
    parent_parser.add_argument("--custom-pattern", nargs=2, action="append", metavar=("NAME", "REGEX"), help="Inject a custom regex pattern. Can be used multiple times.")
    parent_parser.add_argument("--stream", action="store_true", help="Process the file chunk-by-chunk.")
    parent_parser.add_argument("--parallel", action="store_true", help="Process the file in parallel using multiple cores.")
    parent_parser.add_argument("--config", type=str, help="Path to piiscrub.json configuration file.")
    parent_parser.add_argument("--report", type=str, help="Path to save the JSON audit report.")

    # Extract subcommand
    parser_extract = subparsers.add_parser("extract", parents=[parent_parser], help="Extract PII entities from text")
    
    # Scrub subcommand
    parser_scrub = subparsers.add_parser("scrub", parents=[parent_parser], help="Scrub PII entities from text")
    parser_scrub.add_argument("--style", type=str, choices=["tag", "redacted", "hash", "synthetic"], help="Replacement style: 'tag', 'redacted', 'hash', or 'synthetic'")
    parser_scrub.add_argument("--output", type=str, help="Output file path (recommended for large files or parallel mode)")

    args = parser.parse_args()

    # Load config file if present
    config = load_config(args.config)
    
    # Merge config with args (CLI args take precedence)
    entities = args.entities or config.get("entities")
    allowlist = args.allowlist or config.get("allowlist")
    parallel = args.parallel or config.get("parallel", False)
    style = (getattr(args, "style", None) or config.get("style", "tag"))

    # Process custom patterns from CLI
    custom_patterns_dict = {}
    if args.custom_pattern:
        for name, pattern_str in args.custom_pattern:
            try:
                custom_patterns_dict[name] = re.compile(pattern_str)
            except re.error as e:
                print(f"Error compiling regex for {name}: {e}", file=sys.stderr)
                sys.exit(1)
                
    # Merge custom patterns from config
    config_patterns = config.get("custom_patterns", {})
    for name, pattern_str in config_patterns.items():
        if name not in custom_patterns_dict:
            try:
                custom_patterns_dict[name] = re.compile(pattern_str)
            except re.error as e:
                print(f"Error compiling config regex for {name}: {e}", file=sys.stderr)

    # Initialize Core Engine
    cs = PiiScrub(
        entities=entities, 
        allowlist=allowlist,
        custom_patterns=custom_patterns_dict if custom_patterns_dict else None
    )

    if (args.stream or parallel) and not args.file:
        print("Error: --stream or --parallel requires --file.", file=sys.stderr)
        sys.exit(1)

    start_time = time.time()
    total_lines = 0

    if parallel and args.command == "scrub":
        output_path = args.output or (args.file + ".scrubbed")
        print(f"Processing in parallel... saving to {output_path}")
        cs.scrub_file_parallel(args.file, output_path, replacement_style=style)
        # We can count lines by reading the file or getting it from parallel scrub (if we update it)
        # For now, let's keep it simple and just report execution time and entities
        execution_time = time.time() - start_time
        if args.report:
            report = {
                "command": args.command,
                "execution_time_seconds": round(execution_time, 4),
                "entities_redacted": cs.get_stats(),
                "style": style
            }
            with open(args.report, "w", encoding="utf-8") as f_rep:
                json.dump(report, f_rep, indent=4)
        return

    if args.stream:
        # Streaming logic for files
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                if args.command == "extract":
                    results = cs.extract_stream(f)
                    print(json.dumps(results, indent=2))
                elif args.command == "scrub":
                    for scrubbed_line in cs.scrub_stream(f, replacement_style=style):
                        total_lines += 1
                        if args.output:
                            with open(args.output, "a", encoding="utf-8") as f_out:
                                f_out.write(scrubbed_line)
                        else:
                            sys.stdout.write(scrubbed_line)
        except IOError as e:
            print(f"Error reading file {args.file}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Traditional in-memory logic
        text = get_text_from_args(args)
        total_lines = len(text.splitlines())
        
        if args.command == "extract":
            results = cs.extract_entities(text)
            print(json.dumps(results, indent=2))
            
        elif args.command == "scrub":
            result = cs.scrub_text(text, replacement_style=style)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f_out:
                    f_out.write(result)
            else:
                print(result)

    execution_time = time.time() - start_time
    if args.report:
        report = {
            "command": args.command,
            "total_lines_processed": total_lines,
            "execution_time_seconds": round(execution_time, 4),
            "entities_found" if args.command == "extract" else "entities_redacted": cs.get_stats(),
        }
        if args.command == "scrub":
            report["style"] = style
            
        with open(args.report, "w", encoding="utf-8") as f_rep:
            json.dump(report, f_rep, indent=4)

if __name__ == "__main__":
    main()
