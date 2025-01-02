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
args = parser.parse_args()

arg_toml = args.toml

try:
    with open(arg_toml, "rb") as f:
        toml = tomllib.load(f)
        json.dump(toml, sys.stdout, indent="\t")
except (OSError, tomllib.TOMLDecodeError):
    print("Failed to open toml", file=sys.stderr)