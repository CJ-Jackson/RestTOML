#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
import argparse
import json
import sys
import tomllib

parser = argparse.ArgumentParser("Convert Toml to Json")
parser.add_argument("toml")
parser.add_argument("--indent", action='store_true')
args = parser.parse_args()
flag_indent = args.indent

arg_toml = args.toml

try:
    with open(arg_toml, "rb") as f:
        toml = tomllib.load(f)
        if flag_indent:
            json.dump(toml, sys.stdout, indent="\t")
        else:
            json.dump(toml, sys.stdout)
except (OSError, tomllib.TOMLDecodeError):
    print("Failed to open toml", file=sys.stderr)