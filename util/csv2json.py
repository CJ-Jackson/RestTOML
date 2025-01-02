#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
import argparse
import csv
import json
import os
import sys
import tomllib
from dataclasses import dataclass
from typing import Self, Any


def error_and_exit(error_name: str, error_message: str):
    json.dump({"name": error_name, "message": error_message}, sys.stderr, indent="\t")
    exit(100)


parser = argparse.ArgumentParser("Convert CSV to Json")
parser.add_argument("toml")
args = parser.parse_args()

arg_toml = args.toml

toml_data = None
try:
    with open(arg_toml, "rb") as f:
        toml_data = tomllib.load(f)
except (OSError, tomllib.TOMLDecodeError):
    print("Failed to open toml", file=sys.stderr)

os.chdir(os.path.dirname(os.path.abspath(arg_toml)))


class CsvDataError(Exception): pass


@dataclass(frozen=True)
class CsvData():
    file: str
    use_header: bool = True
    map: tuple = ()
    hint: tuple = ()
    delimiter: str = ','
    dialect: str = 'excel'
    quotechar: str = "'"

    @classmethod
    def create(cls, data: dict) -> Self:
        if "file" not in data:
            raise CsvDataError("Must have file")
        file = data["file"]

        return cls(
            file=file,
            use_header=data.get("use_header", True),
            map=tuple(data.get("map", [])),
            hint=tuple(data.get("hint", [])),
            delimiter=data.get("delimiter", ','),
            dialect=data.get("dialect", 'excel'),
            quotechar=data.get("quotechar", "'")
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
            case "str" | "string":
                return str(value)
            case "int" | "interger":
                return int(value)
            case "float":
                return float(value)
            case "bool":
                return bool(int(value))
        return str(value)



try:
    toml_data = CsvData.create(toml_data)
except CsvDataError as e:
    error_and_exit("CSV_DATA_ERROR", e.__str__())

csv_header: list | None = None
csv_list = []

first = True
with open(toml_data.file) as csvfile:
    csv_reader = csv.reader(
        csvfile,
        dialect=toml_data.dialect,
        delimiter=toml_data.delimiter,
        quotechar=toml_data.quotechar
    )
    for row in csv_reader:
        row = list(row)
        if first:
            toml_data.hint_len_check(len(row))
            first = False
            if toml_data.use_header:
                csv_header = row
                continue
            elif toml_data.map:
                csv_header = list(toml_data.map)
        map = {}
        if csv_header:
            if len(csv_header) != len(row):
                error_and_exit("CSV_HEADER_LENGHT", "Length of CSV is not equal to row")
            for i in range(len(csv_header)):
                map[csv_header[i]] = toml_data.hint_value(i, row[i])
        else:
            for i in range(len(row)):
                map[str(i)] = toml_data.hint_value(i, row[i])
        csv_list.append(map)

json.dump({"batch": csv_list}, sys.stdout, indent="\t")