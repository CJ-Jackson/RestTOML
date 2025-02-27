#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
import argparse
import csv
import datetime
import json
import os
import sys
import tomllib
import zoneinfo
from dataclasses import dataclass
from typing import Self, Any
from collections.abc import Iterator


def error_and_exit(error_name: str, error_message: str):
    json.dump({"name": error_name, "message": error_message}, sys.stderr, indent="\t")
    exit(100)


parser = argparse.ArgumentParser("Convert CSV to Json")
parser.add_argument("toml")
parser.add_argument("--indent", action='store_true')
args = parser.parse_args()

arg_toml = args.toml
flag_indent = args.indent

toml_data = None
try:
    with open(arg_toml, "rb") as f:
        toml_data = tomllib.load(f)
except (OSError, tomllib.TOMLDecodeError):
    print("Failed to open toml", file=sys.stderr)

os.chdir(os.path.dirname(os.path.abspath(arg_toml)))


hint_cmd = {}

def handle_hint_command(data: dict, value: str) -> str:
    try:
        return hint_cmd[data["cmd"]](data, value)
    except KeyError as e:
        error_and_exit("HINT_COMMAND_KEY_ERROR", e.__str__())
    return value

class DateTimeFormatterError(Exception): pass


@dataclass(frozen=True)
class DateTimeFormatter():
    from_format: str
    to_format: str
    allow_fail: bool = False
    tz: str | None = None
    to_tz: str | None = None

    @classmethod
    def create(cls, data: dict) -> Self:
        _cls: Self
        match data:
            case {"to": str(), "from": str()}:
                pass
            case _:
                raise DateTimeFormatterError("Must have 'from'(str) and 'to'(str)")
        return cls(
            from_format=data["from"],
            to_format=data["to"],
            allow_fail=data.get("allow_fail", False),
            tz=data.get("tz", None),
            to_tz=data.get("to_tz", None)
        )

    def process(self, value: str) -> str:
        try:
            try:
                tz = zoneinfo.ZoneInfo(self.tz)
            except TypeError:
                tz = None
                pass
            try:
                to_tz = zoneinfo.ZoneInfo(self.to_tz)
            except TypeError:
                to_tz = None
                pass
            from_format = self.__defined_format(self.from_format)
            to_format = self.__defined_format(self.to_format)
            dt = datetime.datetime.strptime(value, from_format)
            if tz:
                dt = dt.replace(tzinfo=tz)
            if to_tz:
                dt = dt.astimezone(to_tz)
            return dt.strftime(to_format)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError) as e:
            if self.allow_fail:
                return value
            raise DateTimeFormatterError(e.__str__())

    def __defined_format(self, format: str) -> str:
        format_dict = {
            "_json": "%Y-%m-%dT%H:%M:%S.%fZ",
        }
        return format_dict.get(format, format)


def handle_date_time_cmd(data: dict, value: str) -> str:
    try:
        if type(data.get("__cache", None)) is not DateTimeFormatter:
            data["__cache"] = DateTimeFormatter.create(data)
        dtf: DateTimeFormatter = data["__cache"]
        return dtf.process(value)
    except DateTimeFormatter as e:
        error_and_exit("DATE_TIME_FORMATTER", e.__str__())
    return value


hint_cmd["datetime_format"] = handle_date_time_cmd


class CsvDataError(Exception): pass


@dataclass(frozen=True)
class CsvData():
    file: str
    use_header: bool = True
    map: tuple = ()
    hint: tuple = ()
    delimiter: str = ','
    dialect: str = 'excel'
    quotechar: str = '"'
    skipinitialspace: bool = False
    strict: bool = False

    @classmethod
    def create(cls, data: dict) -> Self:
        match data:
            case {"file": str()}:
                pass
            case _:
                raise CsvDataError("Must have 'file'(str)")
        return cls(
            file=data["file"],
            use_header=data.get("use_header", True),
            map=tuple(data.get("map", [])),
            hint=tuple(data.get("hint", [])),
            delimiter=data.get("delimiter", ','),
            dialect=data.get("dialect", 'excel'),
            quotechar=data.get("quotechar", '"'),
            skipinitialspace=data.get("skipinitialspace", False),
            strict=data.get("strict", False)
        )

    def hint_len_check(self, row_len: int):
        if not self.hint:
            return
        if len(self.hint) != row_len:
            error_and_exit(
                "HINT_NOT_EQUAL_TO_ROW",
                "lenght of hint, need to match lenght of row!"
                )

    def hint_value(self, pos: int, value: str) -> str | int | float | bool:
        if not self.hint:
            return str(value)
        match self.hint[pos]:
            case "str" | "string" | {"type": "str" | "string"}:
                return str(value)
            case "int" | "integer" | {"type": "int" | "integer"}:
                return int(value)
            case "float" | {"type": "float"}:
                return float(value)
            case "bool" | {"type": "bool"}:
                value = str(value).strip().lower()
                return value in ["1", "true", "yes"]
            case {"cmd": _}:
                return handle_hint_command(self.hint[pos], value)
        return str(value)



try:
    toml_data = CsvData.create(toml_data)
except CsvDataError as e:
    error_and_exit("CSV_DATA_ERROR", e.__str__())


def get_rows_from_csv() -> Iterator[list]:
    with open(toml_data.file) as csvfile:
        csv_reader = csv.reader(
            csvfile,
            dialect=toml_data.dialect,
            delimiter=toml_data.delimiter,
            quotechar=toml_data.quotechar
        )
        for row in csv_reader:
            yield list(row)


rows = list(get_rows_from_csv())

csv_header: list | None = None
if toml_data.use_header:
    csv_header = rows[0]
    rows = rows[1:]
elif toml_data.map:
    csv_header = list(toml_data.map)
    if len(csv_header) != len(rows[0]):
        error_and_exit(
            "CSV_HEADER_LENGHT",
            "Length of CSV is not equal to row"
        )
else:
    csv_header = list(range(len(rows[0])))

toml_data.hint_len_check(len(csv_header))


def handle_csv_column(row: list) -> Iterator[tuple[str, Any]]:
    for pos in range(len(row)):
        yield str(csv_header[pos]), toml_data.hint_value(pos, row[pos])


def handle_csv_rows(rows: list) -> Iterator[dict[str, Any]]:
    for row in rows:
        yield dict(handle_csv_column(row))


if flag_indent:
    json.dump({"batch": list(handle_csv_rows(rows))}, sys.stdout, indent="\t")
else:
    json.dump({"batch": list(handle_csv_rows(rows))}, sys.stdout)