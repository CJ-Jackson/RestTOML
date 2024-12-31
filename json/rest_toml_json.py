#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "requests>=2.32.3",
#   "rich>=13.9.4",
#   "dpath>=2.2.0"
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
from typing import Self

import requests
import urllib3
import dpath
from rich import print_json
from rich.pretty import pprint


def error_and_exit(error_name: str, error_message: str):
    json.dump({"name": error_name, "message": error_message}, sys.stderr, indent="\t")
    exit(100)


parser = argparse.ArgumentParser(description="Process HTTP Rest request for JSON")

parser.add_argument("toml")
parser.add_argument("--adapter")
parser.add_argument("--show-header", action='store_true')
parser.add_argument("--pipe", action='store_true')
parser.add_argument("--arg", action='append')

args = parser.parse_args()

arg_toml = args.toml
flag_adapter = args.adapter
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
            if arg[0].endswith(":int"):
                arg_dict[arg[0].removesuffix(":int")] = int(arg[1])
            if arg[1].endswith(":float"):
                arg_dict[arg[0].removesuffix(":float")] = float(arg[1])
            if arg[1].endswith(":bool"):
                arg_dict[arg[0].removesuffix(":bool")] = bool(int(arg[1]))
            else:
                arg_dict[arg[0]] = arg[1]
    return arg_dict


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
    cookies: dict[str, str] =  field(default_factory=dict[str, str])
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
            cookies=data.get("cookies", {}),
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


class Piper:
    """
    Process `json` from `stdin` pipe
    """

    __switch: dict[str, bool]
    __data: dict

    def __init__(self, switch: dict[str, bool] | list[str], data: dict):
        match switch:
            case dict():
                self.__switch = switch
            case list():
                self.__switch = {}
                for item in switch:
                    self.__switch[item] = True
        self.__data = data

    def process(self, switch: str, user_data: dict | list) -> dict | list | None:
        if not self.__switch.get(switch, False):
            return user_data
        if type(user_data) is dict:
            return self.__process_dict(user_data)
        elif type(user_data) is list:
            return self.__process_list(user_data)

    def __process_list(self, user_data: list) -> list:
        new_data: list = []
        for value in user_data:
            match value:
                case str() if len(value) > 3 and value[:3] == "#d!":
                    value = dpath.get(self.__data, value[3:])
                case dict():
                    value = self.__process_dict(value)
                case list():
                    value = self.__process_list(value)
            new_data.append(value)
        return new_data

    def __process_dict(self, user_data: dict) -> dict:
        for key, value in user_data.items():
            match value:
                case str() if len(value) > 3 and value[:3] == "#d!":
                    user_data[key] = dpath.get(self.__data, value[3:])
                case dict():
                    user_data[key] = self.__process_dict(value)
                case list():
                    user_data[key] = self.__process_list(value)
        return user_data

arg_dict = process_flag_args()
piper = Piper(["arg"], {"arg": arg_dict})
if toml_data.pipe:
    all_pipe_data = {}
    try:
        for key, pipe in toml_data.pipe.items():
            pipe_data = subprocess.run([
                pipe, "--pipe"
            ], check=True, capture_output=True).stdout.decode('utf-8').strip()
            all_pipe_data[key] = json.loads(pipe_data)
        piper = Piper(["arg", "pipe"], {"arg": arg_dict, "pipe": all_pipe_data})
    except subprocess.CalledProcessError as e:
        error_and_exit("PIPE_ERROR", e.__str__())
    except json.JSONDecodeError as e:
        error_and_exit("JSON_PIPE_ERROR", e.__str__())


def process_endpoint_arg() -> str:
    endpoint = toml_data.http.endpoint
    for key, value in arg_dict.items():
        endpoint = endpoint.replace("{"+key+"}", value)
    return endpoint


req = requests.Request(
    method=toml_data.http.method,
    url=adapter_data.url + process_endpoint_arg(),
    headers=piper.process("arg", toml_data.http.headers) | adapter_data.headers,
    params=piper.process("arg", toml_data.http.params),
    cookies=piper.process("arg", toml_data.http.cookies),
)

session = requests.Session()

prepared_req = req.prepare()

if toml_data.http.method not in ["GET", "HEAD"]:
    if type(toml_data.http.payload) is str:
        json_payload = json.loads(toml_data.http.payload)
        prepared_req.body = json.dumps(piper.process("arg", json_payload))
    else:
        prepared_req.body = json.dumps(piper.process("arg", toml_data.http.payload))

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
        "status": res.status_code,
        "headers": dict(res.headers),
        "cookies": cookies_,
        "body": res.json(),
    }, sys.stdout, indent="\t")
    exit(0)

print(f"Status: {res.status_code}")
print(f"Elapsed: {res.elapsed}")
if flag_show_header:
    print("-- Response Headers --")
    pprint(res.headers, expand_all=True)
print("-- Response Body --")
print_json(res.text)
