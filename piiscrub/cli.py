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
    group.add_argument("--dir", type=str, help="Path to directory to process")
    parent_parser.add_argument("--entities", type=str, nargs="+", help="Specific entities to target (e.g., EMAIL CREDIT_CARD)")
    parent_parser.add_argument("--allowlist", type=str, nargs="+", help="Specific strings to bypass scrubbing (e.g., support@example.com)")
    parent_parser.add_argument("--custom-pattern", nargs=2, action="append", metavar=("NAME", "REGEX"), help="Inject a custom regex pattern. Can be used multiple times.")
    parent_parser.add_argument("--stream", action="store_true", help="Process the file chunk-by-chunk.")
    parent_parser.add_argument("--parallel", action="store_true", help="Process the file in parallel using multiple cores.")
    parent_parser.add_argument("--config", type=str, help="Path to piiscrub.json configuration file.")
    parent_parser.add_argument("--report", type=str, help="Path to save the JSON audit report.")
    parent_parser.add_argument("--profile", type=str, help="Compliance profile to use (e.g., pci-dss, hipaa, gdpr, strict)")
    parent_parser.add_argument("--json-key", type=str, nargs="+", help="Specific JSON keys to target for scrubbing.")
    parent_parser.add_argument("--csv-column", type=str, nargs="+", help="Specific CSV columns to target for scrubbing.")
    parent_parser.add_argument("--recursive", "-r", action="store_true", help="Process the directory recursively.")

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
    profile = args.profile or config.get("profile")
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
        profile=profile,
        allowlist=allowlist,
        custom_patterns=custom_patterns_dict if custom_patterns_dict else None
    )

    if (args.stream or args.parallel) and not (args.file or args.dir):
        print("Error: --stream or --parallel requires --file or --dir.", file=sys.stderr)
        sys.exit(1)

    start_time = time.time()
    if args.dir:
        if not os.path.isdir(args.dir):
            print(f"Error: {args.dir} is not a directory.", file=sys.stderr)
            sys.exit(1)
        
        output_dir = getattr(args, "output", None)
        if not output_dir and args.command == "scrub":
            output_dir = args.dir + "_scrubbed"
            print(f"No output directory specified. Saving scrubbed files to: {output_dir}")
        
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        files_to_process = []
        if args.recursive:
            for root, _, files in os.walk(args.dir):
                for f in files:
                    files_to_process.append(os.path.join(root, f))
        else:
            for f in os.listdir(args.dir):
                full_path = os.path.join(args.dir, f)
                if os.path.isfile(full_path):
                    files_to_process.append(full_path)

        for f_path in files_to_process:
            rel_path = os.path.relpath(f_path, args.dir)
            f_out = os.path.join(output_dir, rel_path) if output_dir else None
            if f_out:
                os.makedirs(os.path.dirname(f_out), exist_ok=True)
            
            print(f"Processing {rel_path}...")
            # Reuse file processing logic or call a function
            _process_file_internal(cs, args, f_path, f_out, style)
    
    elif args.file:
        _process_file_internal(cs, args, args.file, args.output, style)
    else:
        # Traditional in-memory logic for --text
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
            "execution_time_seconds": round(execution_time, 4),
            "entities_found" if args.command == "extract" else "entities_redacted": cs.get_stats(),
        }
        if args.command == "scrub":
            report["style"] = style
            
        with open(args.report, "w", encoding="utf-8") as f_rep:
            json.dump(report, f_rep, indent=4)

def _process_file_internal(cs, args, input_file, output_file, style):
    """Internal helper to process a single file."""
    file_ext = os.path.splitext(input_file)[1].lower() if input_file else None
    
    if args.parallel and args.command == "scrub":
        out_path = output_file or (input_file + ".scrubbed")
        cs.scrub_file_parallel(input_file, out_path, replacement_style=style)
        return

    try:
        if args.stream:
            with open(input_file, "r", encoding="utf-8") as f:
                if args.command == "extract":
                    results = cs.extract_stream(f)
                    print(json.dumps(results, indent=2))
                elif args.command == "scrub":
                    if output_file:
                        with open(output_file, "w", encoding="utf-8") as f_out:
                            for scrubbed_line in cs.scrub_stream(f, replacement_style=style):
                                f_out.write(scrubbed_line)
                    else:
                        for scrubbed_line in cs.scrub_stream(f, replacement_style=style):
                            sys.stdout.write(scrubbed_line)
        else:
            with open(input_file, "r", encoding="utf-8") as f:
                text = f.read()

            if args.command == "extract":
                results = cs.extract_entities(text)
                print(json.dumps(results, indent=2))
            elif args.command == "scrub":
                if file_ext == ".json" and args.json_key:
                    try:
                        data = json.loads(text)
                        scrubbed_data = cs.scrub_json(data, keys_to_scrub=args.json_key, replacement_style=style)
                        result = json.dumps(scrubbed_data, indent=2)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON in {input_file}: {e}", file=sys.stderr)
                        return
                elif file_ext == ".csv" and args.csv_column:
                    f_iter = text.splitlines()
                    result = "".join(cs.scrub_csv(f_iter, columns_to_scrub=args.csv_column, replacement_style=style))
                else:
                    result = cs.scrub_text(text, replacement_style=style)

                if output_file:
                    with open(output_file, "w", encoding="utf-8") as f_out:
                        f_out.write(result)
                else:
                    print(result)
    except IOError as e:
        print(f"Error processing file {input_file}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
