#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "requests>=2.32.3",
#   "rich>=13.9.4",
#   "xmltodict>=0.14.2"
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
from xml.parsers.expat import ExpatError
from typing import Self, Any
from collections.abc import Iterator, MutableMapping

import requests
import urllib3
import xmltodict
from rich.pretty import pprint
from rich.console import Console
from rich.syntax import Syntax


def error_and_exit(error_name: str, error_message: str):
    json.dump({"name": error_name, "message": error_message}, sys.stderr, indent="\t")
    exit(100)


parser = argparse.ArgumentParser(description="Process HTTP Rest request for XML")

parser.add_argument("toml")
parser.add_argument("--adapter")
parser.add_argument("--show-request", action='store_true')
parser.add_argument("--show-header", action='store_true')
parser.add_argument("--pipe", action='store_true')
parser.add_argument("--indent", action='store_true')
parser.add_argument("--arg", action='append')

args = parser.parse_args()

arg_toml = args.toml
flag_adapter = args.adapter
flag_show_request = args.show_request
flag_show_header = args.show_header
flag_pipe = args.pipe
flag_args = args.arg
flag_indent = args.indent


def process_flag_args(data_type: dict) -> dict:
    arg_dict = {}
    if not flag_args:
        return arg_dict
    for arg in flag_args:
        arg = str(arg).split("=", maxsplit=2)
        if len(arg) == 2:
            name = arg[0]
            value = arg[1]
            value_type = data_type.get(name, {})
            match value_type:
                case {"type": "str" | "string"}:
                    value = str(value)
                case {"type": "int" | "integer"}:
                    value = int(value)
                case {"type": "float"}:
                    value = float(value)
                case {"type": "bool"}:
                    value = str(value).strip().lower()
                    value = value in ["1", "true", "yes"]
                case _:
                    value = str(value)
            match arg_dict.get(name, None):
                case None:
                    arg_dict[name] = value
                case list():
                    arg_list = list(arg_dict[name])
                    arg_list.append(value)
                    arg_dict[name] = arg_list
                case _:
                    arg_list = [arg_dict[name], value]
                    arg_dict[name] = arg_list
    return arg_dict


def arg_pass() -> Iterator[str]:
    for arg in flag_args:
        yield "--arg"
        yield str(arg)


# https://github.com/CJ-Jackson/AnimalApiTestServer
adapter_data = {
    "url": "http://127.0.0.1:18080",
    "headers": {
        "Content-Type": "application/xml; charset=utf-8",
        "Accept": "application/xml"
        },
    "verify": False,
}

if flag_adapter:
    try:
        adapter_data = subprocess.run([
            os.path.expanduser(f"~/.config/resttoml/xml/{flag_adapter}")
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



class PipeDataError(Exception): pass


@dataclass(frozen=True)
class PipeData():
    script: str
    arg: tuple = ()
    pass_pipe_flag: bool = True
    pass_arg: bool = False

    @classmethod
    def create(cls, data: dict) -> Self:
        match data:
            case {"script": str()}:
                pass
            case _:
                raise PipeDataError("Must have 'script'(str)")
        return cls(
            script=data["script"],
            arg=tuple(data.get("arg", [])),
            pass_pipe_flag=data.get("pass_pipe_flag", True),
            pass_arg=data.get("pass_arg", False)
        )


class TomlDataError(Exception): pass


@dataclass(frozen=True)
class TomlData():
    http: HttpData
    pipe: dict[str, PipeData] | None = None
    arg: dict = field(default_factory=dict)

    @classmethod
    def create(cls, data: dict) -> Self:
        match data:
            case {"http": dict()}:
                pass
            case _:
                raise TomlDataError("Must have 'http'(dict)")

        pipe = None
        if "pipe" in data:
            pipe = data["pipe"]
            for key, value in pipe.items():
                pipe[key] = PipeData.create(value)

        return cls(
            http=HttpData.create(data["http"]),
            pipe=pipe,
            arg=data.get("arg", {})
        )


try:
    toml_data = TomlData.create(toml_data)
except HttpDataError as e:
    error_and_exit("HTTP_DATA_ERROR", e.__str__())
except TomlDataError as e:
    error_and_exit("TOML_DATA_ERROR", e.__str__())
except PipeDataError as e:
    error_and_exit("PIPE_DATA_ERROR", e.__str__())


def _list_to_dict(v: list) -> Iterator[tuple[str, Any]]:
    yield "_", tuple(v)
    for i in range(len(v)):
        yield str(i), v[i]


def _flatten_dict_gen(d, parent_key, sep) -> Iterator[tuple[str, Any]]:
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

    def __process_list(self, user_data: list) -> Iterator[Any]:
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

    def __process_dict(self, user_data: dict) -> Iterator[tuple[str, Any]]:
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


arg_dict = process_flag_args(toml_data.arg)
piper = Piper({"arg": arg_dict})
if toml_data.pipe:
    all_pipe_data = {}
    try:
        pass_args = list(arg_pass())
        for key, pipe in toml_data.pipe.items():
            extra = []
            if pipe.pass_pipe_flag:
                extra += ["--pipe"]
            extra += list(pipe.arg)
            if pipe.pass_arg:
                extra += pass_args
            pipe_data = subprocess.run([
                                           pipe.script
                                       ] + extra, check=True, capture_output=True).stdout.decode('utf-8').strip()
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

payload = ""
if toml_data.http.method not in ["GET", "HEAD"] and toml_data.http.payload:
    if type(toml_data.http.payload) is str:
        payload = xmltodict.parse(toml_data.http.payload)
        payload = xmltodict.unparse(piper.process(payload), pretty=True)
    else:
        payload = xmltodict.unparse(piper.process(toml_data.http.payload), pretty=True)

payload_parsed = {}
if payload:
    payload_parsed = xmltodict.parse(payload)

req = requests.Request(
    method=toml_data.http.method,
    url=adapter_data.url.rstrip("/") + "/" + process_endpoint_arg(),
    headers=piper.process(toml_data.http.headers) | adapter_data.headers,
    params=piper.process(toml_data.http.params),
    cookies=piper.process(toml_data.http.cookies),
    data=payload
)

session = requests.Session()

prepared_req = req.prepare()

if not adapter_data.verify:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

res: requests.Response | None = None
try:
    res = session.send(prepared_req, verify=adapter_data.verify)
except requests.ConnectionError as e:
    error_and_exit("REQUESTS_CONNECTION_ERROR", e.__str__())

def pretty_print_xml(xml: str) -> str:
    try:
        return xmltodict.unparse(xmltodict.parse(xml), pretty=True)
    except (ValueError, ExpatError):
        return ""

if flag_pipe:
    cookies_ = {}
    if "set-cookie" in dict(res.headers):
        for cookie in dict(res.headers["set-cookie"]):
            simple_cookie = cookies.SimpleCookie()
            simple_cookie.load(cookie)
            for key, morsel in simple_cookie.items():
                cookies_[key] = morsel.value
    json_output = {
        "edition": "xml",
        "request": {
            "headers": dict(res.request.headers),
            "payload": payload_parsed,
            "payload_original": payload
            },
        "url": res.request.url,
        "method": res.request.method,
        "status": res.status_code,
        "headers": dict(res.headers),
        "cookies": cookies_,
        "body": xmltodict.parse(res.text),
        "body_original": pretty_print_xml(res.text),
        "elapsed": f"{res.elapsed}"
    }
    if flag_indent:
        json.dump(json_output, sys.stdout, indent="\t")
    else:
        json.dump(json_output, sys.stdout)
    exit(0)

console = Console()

if flag_show_request:
    print("-- Request Headers --")
    pprint(dict(res.request.headers), expand_all=True)
    print("-- Request Payload --")
    console.print(Syntax(payload, "xml", background_color="black"))

print("-- Response --")
print(f"URL: {res.request.url}")
print(f"Status: {res.status_code}")
print(f"Elapsed: {res.elapsed}")
if flag_show_header:
    print("-- Response Headers --")
    pprint(dict(res.headers), expand_all=True)
print("-- Response Body --")


if not res.text:
    exit(0)
console.print(Syntax(pretty_print_xml(res.text), "xml", background_color="black"))
