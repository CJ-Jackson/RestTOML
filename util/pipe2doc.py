#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
import json
import sys


def error_and_exit(error_name: str, error_message: str):
    json.dump({"name": error_name, "message": error_message}, sys.stderr, indent="\t")
    exit(100)

edition_dict: dict = {}

def exec_edition_dict(data: dict) -> str:
    try:
        return edition_dict[data["edition"]](data)
    except KeyError as e:
        error_and_exit("PIPE_2_DOC_KEY_ERROR", e.__str__())
    return ""


def exec_json_edition(data: dict) -> str:
    return f"""
# URL
`{data['url']}`

# METHOD
`{data['method']}`

# STATUS
`{data['status']}`

# ELAPSED
`{data['elapsed']}`

# Request
## Headers
```json
{json.dumps(data['request']['headers'], indent="\t")}
```
## Payload
```json
{json.dumps(data['request']['payload'], indent="\t")}
```

# Response
## Headers
```json
{json.dumps(data['headers'], indent="\t")}
```

## Cookies
```json
{json.dumps(data['cookies'], indent="\t")}
```

## Body
```json
{json.dumps(data['body'], indent="\t")}
```
""".strip()


edition_dict["json"] = exec_json_edition


def exec_xml_edition(data: dict) -> str:
    return f"""
# URL
`{data['url']}`

# METHOD
`{data['method']}`

# STATUS
`{data['status']}`

# ELAPSED
`{data['elapsed']}`

# Request
## Headers
```json
{json.dumps(data['request']['headers'], indent="\t")}
```
## Payload
```xml
{data['request']['payload_original']}
```

# Response
## Headers
```json
{json.dumps(data['headers'], indent="\t")}
```

## Cookies
```json
{json.dumps(data['cookies'], indent="\t")}
```

## Body
```xml
{data['body_original']}
```
""".strip()


edition_dict["xml"] = exec_xml_edition


data = {}
try:
    data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    error_and_exit("PIPE_2_DOC_JSON_ERROR", e.__str__())

print(exec_edition_dict(data))