#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "requests>=2.32.3",
#   "rich>=13.9.4"
# ]
# ///
import argparse
import json
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from typing import Self, MutableMapping, Any, Generator

import requests
import urllib3
from rich import print_json
from rich.pretty import pprint


def error_and_exit(error_name: str, error_message: str):
    json.dump({"name": error_name, "message": error_message}, sys.stderr, indent="\t")
    exit(100)


parser = argparse.ArgumentParser(description="Process HTTP Rest request for JSON")

parser.add_argument("toml")
parser.add_argument("--adapter")
parser.add_argument("--show-request", action='store_true')

args = parser.parse_args()

arg_toml = args.toml
flag_adapter = args.adapter
flag_show_request = args.show_request

adapter_data = {
    "url": "http://127.0.0.1:18080",
    "headers": {"Content-Type": "application/json; charset=UTF-8"},
    "verify": True,
}

if flag_adapter:
    try:
        adapter_data = subprocess.run([
            os.path.expanduser(f"~/.config/resttoml/json/{flag_adapter}")
        ], check=True, capture_output=True).stdout.decode('utf-8')
        adapter_data = json.loads(adapter_data)
    except subprocess.CalledProcessError as e:
        error_and_exit("FLAG_ADAPTER_ERROR", e.__str__())
    except json.JSONDecodeError as e:
        error_and_exit("FLAG_ADAPTER_JSON_ERROR", e.__str__())


class AdapterDataError(Exception): pass


@dataclass(frozen=True)
class AdapterData():
    url: str
    headers: dict[str, str]
    verify: bool = True

    @classmethod
    def create(cls, data: dict):
        match data:
            case {"url": str(), "headers": dict()}:
                pass
            case _:
                raise AdapterDataError("Adapter must have 'url'(str) and 'headers'(dict)")
        return cls(
            url=data["url"],
            headers=data["headers"],
            verify=data.get("verify", True)
        )


try:
    adapter_data = AdapterData.create(adapter_data)
except AdapterDataError as e:
    error_and_exit("ADAPTER_DATA_ERROR", e.__str__())

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
    cookies: dict[str, str] = field(default_factory=dict[str, str])
    payload: dict[str, Any] | str = field(default_factory=dict[str, Any])
    method: str = "GET"

    @classmethod
    def create(cls, data: dict) -> Self:
        match data:
            case {"endpoint": str()}:
                pass
            case _:
                raise HttpDataError("Must have 'endpoint'(str)")
        return cls(
            endpoint=data["endpoint"],
            params=data.get("params", {}),
            headers=data.get("headers", {}),
            cookies=data.get("cookies", {}),
            payload=data.get("payload", {}),
            method=data.get("method", "GET").strip().upper(),
        )


class BatchDataError(Exception): pass


@dataclass(frozen=True)
class BatchData():
    script: str
    arg: tuple = ()
    key: str = "batch"

    @classmethod
    def create(cls, data: dict) -> Self:
        match data:
            case {"script": str()}:
                pass
            case _:
                raise BatchDataError("Must have 'script'(str)")
        return cls(
            script=data["script"],
            arg=tuple(data.get("arg", [])),
            key=data.get("key", "batch")
        )


class TomlDataError(Exception): pass


@dataclass(frozen=True)
class TomlData():
    http: HttpData
    batch: BatchData

    @classmethod
    def create(cls, data: dict) -> Self:
        match data:
            case {"http": dict(), "batch": dict()}:
                pass
            case _:
                raise TomlDataError("Must have 'http'(dict) and 'batch'(dict)")
        return cls(
            http=HttpData.create(data["http"]),
            batch= BatchData.create(data["batch"])
        )


try:
    toml_data = TomlData.create(toml_data)
except HttpDataError as e:
    error_and_exit("HTTP_DATA_ERROR", e.__str__())
except TomlDataError as e:
    error_and_exit("TOML_DATA_ERROR", e.__str__())
except BatchDataError as e:
    error_and_exit("BATCH_DATA_ERROR", e.__str__())


def _list_to_dict(v: list) -> Generator[tuple[str, Any], dict]:
    yield "_", tuple(v)
    for i in range(len(v)):
        yield str(i), v[i]

def _flatten_dict_gen(d, parent_key, sep) -> Generator[tuple[str, Any], dict]:
    for k, v in d.items():
        if type(v) is list:
            v = dict(_list_to_dict(v))
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            yield from flatten_dict(v, new_key, sep=sep).items()
        else:
            yield new_key, v


def flatten_dict(d: MutableMapping, parent_key: str = '', sep: str = '/') -> dict:
    return dict(_flatten_dict_gen(d, parent_key, sep))


class Piper:
    __data: dict

    def __init__(self, data: dict):
        self.__data = flatten_dict(data)

    def process(self, user_data: dict | list) -> dict | list | None:
        try:
            if type(user_data) is dict:
                return dict(self.__process_dict(user_data))
            elif type(user_data) is list:
                return list(self.__process_list(user_data))
        except KeyError as ex:
            error_and_exit(
                "PIPER_KEY_ERROR",
                f"'#d!{ex.__str__().strip("'")}' not found"
            )

    def __process_list(self, user_data: list) -> Generator[Any, list]:
        for i in range(len(user_data)):
            match user_data[i]:
                case str() if str(user_data[i]).startswith("#d!"):
                    yield self.__data[str(user_data[i])[3:].strip('/')]
                case dict():
                    yield dict(self.__process_dict(user_data[i]))
                case list():
                    yield list(self.__process_list(user_data[i]))
                case _:
                    yield user_data[i]

    def __process_dict(self, user_data: dict) -> Generator[tuple[str, Any], dict]:
        for key, value in user_data.items():
            match value:
                case str() if str(value).startswith("#d!"):
                    yield key, self.__data[str(value)[3:].strip('/')]
                case dict():
                    yield key, dict(self.__process_dict(value))
                case list():
                    yield key, list(self.__process_list(value))
                case _:
                    yield key, value


endpoint = toml_data.http.endpoint

d_poss = [i for i in range(len(endpoint)) if endpoint.startswith("#d!", i) or endpoint.startswith("//", i)]

endpoint_split = []
previous_pos = 0
for pos in d_poss:
    endpoint_split.append(endpoint[previous_pos:pos].strip("/"))
    previous_pos = pos
endpoint_split.append(endpoint[previous_pos:].strip("/"))


def process_endpoint_arg(piper: Piper) -> str:
    endpoint = piper.process(endpoint_split)
    return "/".join(str(v) for v in endpoint).rstrip("/")


batch: list | None = None
try:
    batch_data = subprocess.run([
                                    toml_data.batch.script
                                ] + list(toml_data.batch.arg), capture_output=True, check=True).stdout.decode('utf-8')
    batch_data = json.loads(batch_data)
    batch = batch_data[toml_data.batch.key]
except KeyError as e:
    error_and_exit("BATCH_KEY_ERROR", e.__str__())
except json.JSONDecodeError as e:
    error_and_exit("BATCH_JSON_ERROR", e.__str__())
except subprocess.CalledProcessError as e:
    error_and_exit("BATCH_PROCESS_ERROR", e.__str__())

session = requests.Session()

for pos in range(len(batch)):

    piper = Piper({"batch": batch[pos]})

    payload = ""
    if toml_data.http.method not in ["GET", "HEAD"]:
        if type(toml_data.http.payload) is str:
            payload = json.loads(toml_data.http.payload)
            payload = json.dumps(piper.process(payload))
        else:
            payload = json.dumps(piper.process(toml_data.http.payload))

    req = requests.Request(
        method=toml_data.http.method,
        url=adapter_data.url.rstrip("/") + "/" + process_endpoint_arg(piper),
        headers=piper.process(toml_data.http.headers) | adapter_data.headers,
        params=piper.process(toml_data.http.params),
        cookies=piper.process(toml_data.http.cookies),
        data=payload
    )

    prepared_req = req.prepare()

    if not adapter_data.verify:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    res: requests.Response | None = None
    try:
        res = session.send(prepared_req, verify=adapter_data.verify)
    except requests.ConnectionError as e:
        error_and_exit("REQUESTS_CONNECTION_ERROR", e.__str__())

    print(f"-- Batch: {pos + 1} --")

    if flag_show_request:
        print("-- Request Headers --")
        pprint(dict(res.request.headers), expand_all=True)
        print("-- Request Payload --")
        print_json(payload)

    print("-- Response --")
    print(f"URL: {res.request.url}")
    print(f"Status: {res.status_code}")
    print(f"Elapsed: {res.elapsed}")
    print("-- Response Body --")
    print_json(res.text)
