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
from http import cookies
from dataclasses import dataclass, field
from typing import Self, MutableMapping

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
parser.add_argument("--show-header", action='store_true')
parser.add_argument("--pipe", action='store_true')
parser.add_argument("--arg", action='append')

args = parser.parse_args()

arg_toml = args.toml
flag_adapter = args.adapter
flag_show_request = args.show_request
flag_show_header = args.show_header
flag_pipe = args.pipe
flag_args = args.arg


def process_flag_args() -> dict:
    arg_dict = {}
    if not flag_args:
        return arg_dict
    for arg in flag_args:
        arg = str(arg).split("=", maxsplit=2)
        if len(arg) == 2:
            name = arg[0]
            value = arg[1]
            if name.endswith(":int"):
                name = name.removesuffix(":int")
                value = int(value)
            if name.endswith(":float"):
                name = name.removesuffix(":int")
                value = float(value)
            if name.endswith(":bool"):
                name = arg[0].removesuffix(":bool")
                value = bool(int(arg[1]))
            arg_dict[name.split(":", maxsplit=2)[0]] = value
    return arg_dict


def arg_pass() -> list:
    args = []
    for arg in flag_args:
        args += ["--arg", str(arg)]
    return args


adapter_data = {
    "url": "https://jsonplaceholder.typicode.com/",
    "headers": {"Content-type": "application/json; charset=UTF-8"},
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
        if "url" not in data:
            raise AdapterDataError("Adapter must provide url")
        url = data["url"]
        if "headers" not in data:
            raise AdapterDataError("Adapter must provide headers")
        headers = data["headers"]
        return cls(url=url, headers=headers, verify=data.get("verify", True))


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
    payload: dict[str, str] | str = field(default_factory=dict[str, str])
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
            cookies=data.get("cookies", {}),
            payload=data.get("payload", {}),
            method=data.get("method", "GET").strip().upper(),
        )


class TomlDataError(Exception): pass


@dataclass(frozen=True)
class TomlData():
    http: HttpData
    pipe: dict[str, str] | None = None

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


def _list_to_dict(v: list) -> dict:
    d = {}
    for i in range(len(v)):
        d[str(i)] = v[i]
    return d


def _flatten_dict_gen(d, parent_key, sep):
    for k, v in d.items():
        if type(v) is list:
            v = _list_to_dict(v)
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            yield from flatten_dict(v, new_key, sep=sep).items()
        else:
            yield new_key, v


def flatten_dict(d: MutableMapping, parent_key: str = '', sep: str = '/'):
    return dict(_flatten_dict_gen(d, parent_key, sep))


class Piper:
    __switch: dict[str, bool]
    __data: dict

    def __init__(self, data: dict):
        self.__data = flatten_dict(data)

    def process(self, user_data: dict | list) -> dict | list | None:
        try:
            if type(user_data) is dict:
                return self.__process_dict(user_data)
            elif type(user_data) is list:
                return self.__process_list(user_data)
        except KeyError as ex:
            error_and_exit(
                "PIPER_KEY_ERROR",
                f"'#d!{ex.__str__().strip("'")}' not found"
            )

    def __process_list(self, user_data: list) -> list:
        for i in range(len(user_data)):
            match user_data[i]:
                case str() if str(user_data[i]).startswith("#d!"):
                    user_data[i] = self.__data[str(user_data[i])[3:].strip('/')]
                case dict():
                    user_data[i] = self.__process_dict(user_data[i])
                case list():
                    user_data[i] = self.__process_list(user_data[i])
        return user_data

    def __process_dict(self, user_data: dict) -> dict:
        for key, value in user_data.items():
            match value:
                case str() if str(value).startswith("#d!"):
                    user_data[key] = self.__data[str(value)[3:].strip('/')]
                case dict():
                    user_data[key] = self.__process_dict(value)
                case list():
                    user_data[key] = self.__process_list(value)
        return user_data


arg_dict = process_flag_args()
piper = Piper({"arg": arg_dict, "test": [0, 42, 0]})
if toml_data.pipe:
    all_pipe_data = {}
    try:
        pass_args = arg_pass()
        for key, pipe in toml_data.pipe.items():
            pipe_data = subprocess.run([
                                           pipe, "--pipe"
                                       ] + pass_args, check=True, capture_output=True).stdout.decode('utf-8').strip()
            all_pipe_data[key] = json.loads(pipe_data)
        piper = Piper({"arg": arg_dict, "pipe": all_pipe_data})
    except subprocess.CalledProcessError as e:
        error_and_exit("PIPE_ERROR", e.__str__())
    except json.JSONDecodeError as e:
        error_and_exit("JSON_PIPE_ERROR", e.__str__())


def process_endpoint_arg() -> str:
    endpoint = toml_data.http.endpoint

    d_poss = [i for i in range(len(endpoint)) if endpoint.startswith("#d!", i) or endpoint.startswith("//", i)]

    endpoint_split = []
    previous_pos = 0
    for pos in d_poss:
        endpoint_split.append(endpoint[previous_pos:pos].strip("/"))
        previous_pos = pos
    endpoint_split.append(endpoint[previous_pos:].strip("/"))

    endpoint = piper.process(endpoint_split)
    return "/".join(str(v) for v in endpoint).rstrip("/")


req = requests.Request(
    method=toml_data.http.method,
    url=adapter_data.url + process_endpoint_arg(),
    headers=piper.process(toml_data.http.headers) | adapter_data.headers,
    params=piper.process(toml_data.http.params),
    cookies=piper.process(toml_data.http.cookies),
)

session = requests.Session()

prepared_req = req.prepare()

payload = "{}"
if toml_data.http.method not in ["GET", "HEAD"]:
    if type(toml_data.http.payload) is str:
        json_payload = json.loads(toml_data.http.payload)
        prepared_req.body = json.dumps(piper.process(json_payload))
    else:
        prepared_req.body = json.dumps(piper.process(toml_data.http.payload))
    payload = prepared_req.body

if not adapter_data.verify:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

res = session.send(prepared_req, verify=adapter_data.verify)

if flag_pipe:
    cookies_ = {}
    if "set-cookie" in dict(res.headers):
        for cookie in dict(res.headers["set-cookie"]):
            simple_cookie = cookies.SimpleCookie()
            simple_cookie.load(cookie)
            for key, morsel in simple_cookie.items():
                cookies_[key] = morsel.value
    json.dump({
        "edition": "json",
        "request": {"headers": dict(res.request.headers), "payload": json.loads(payload)},
        "status": res.status_code,
        "headers": dict(res.headers),
        "cookies": cookies_,
        "body": res.json(),
    }, sys.stdout, indent="\t")
    exit(0)

if flag_show_request:
    print("-- Request Headers --")
    pprint(dict(res.request.headers), expand_all=True)
    print("-- Request Payload --")
    print_json(payload)

print("-- Response --")
print(f"Status: {res.status_code}")
print(f"Elapsed: {res.elapsed}")
if flag_show_header:
    print("-- Response Headers --")
    pprint(dict(res.headers), expand_all=True)
print("-- Response Body --")
print_json(res.text)
