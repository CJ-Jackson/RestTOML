#!/usr/bin/env python3
import argparse
import json
import os
import sys
import tomllib
from dataclasses import dataclass, field
from typing import Self


def error_and_exit(error_name: str, error_message: str):
    json.dump({"name": error_name, "message": error_message}, sys.stderr, indent="\t")
    exit(100)


parser = argparse.ArgumentParser(description="Process HTTP Rest request for JSON")

parser.add_argument("toml")

args = parser.parse_args()

arg_toml = args.toml

adapter_data = {
    "url": "https://jsonplaceholder.typicode.com/",
    "headers": {"X-TEST": "TEST"}
}

# TODO: Add adapter flag, for now we use embedded data.

class AdapterDataError(Exception): pass


@dataclass(frozen=True)
class AdapterData():
    url: str
    headers: dict[str, str]

    @classmethod
    def create(cls, data: dict):
        if "url" not in data:
            raise AdapterDataError("Adapter must provide url")
        url = data["url"]
        if "headers" not in data:
            raise AdapterDataError("Adapter must provide headers")
        headers = data["headers"]
        return cls(url=url, headers=headers)


try:
    adapter_data = AdapterData.create(adapter_data)
except AdapterDataError as e:
    error_and_exit("ADAPTER_DATA_ERROR", e.__str__())

print(adapter_data)

toml_data = None
try:
    with open(arg_toml, "rb") as f:
        toml_data = tomllib.load(f)
except tomllib.TOMLDecodeError as e:
    error_and_exit("TOML_DECODE_ERROR", e.__str__())
except OSError as e:
    error_and_exit("OS_ERROR", e.__str__())
if not toml_data:
    exit(0)

os.chdir(os.path.dirname(os.path.abspath(arg_toml)))

class HttpDataError(Exception): pass


@dataclass(frozen=True)
class HttpData():
    endpoint: str
    params: dict[str, str] = field(default_factory=dict[str, str])
    headers: dict[str, str] = field(default_factory=dict[str, str])
    payload: dict[str, str]|str = field(default_factory=dict[str, str])
    method: str = "GET"

    @classmethod
    def create(cls, data: dict) -> Self:
        if "endpoint" not in data:
            raise HttpDataError("Must have endpoint")
        endpoint = data["endpoint"]

        return cls(
            endpoint=endpoint,
            params=data.get("params", {}),
            headers=data.get("headers", {}),
            payload=data.get("payload", {}),
            method=data.get("method", "GET").strip().upper(),
        )


class TomlDataError(Exception): pass


@dataclass(frozen=True)
class TomlData():
    http: HttpData
    pipe: dict[str, str]|None = None

    @classmethod
    def create(cls, data: dict) -> Self:
        if "http" not in data:
            raise TomlDataError
        http = HttpData.create(data["http"])

        return cls(
            http=http,
            pipe=data.get("pipe", None)
        )

try:
    toml_data = TomlData.create(toml_data)
except HttpDataError as e:
    error_and_exit("HTTP_DATA_ERROR", e.__str__())
except TomlDataError as e:
    error_and_exit("TOML_DATA_ERROR", e.__str__())

print(toml_data)