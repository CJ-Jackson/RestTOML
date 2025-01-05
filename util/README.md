# RestTOML Util

## csv2json

Convert CSV to JSON

### Example csv
```csv
id,date
0,2024-01-01
1,2024-02-01
```

### Example TOML
```
#!/usr/bin/env csv2json

file = "./example.csv"

[[hint]]
type = "int"

[[hint]]
cmd = "datetime_format"
from = "%Y-%m-%d" # Mandatory
to = "_json" # Mandatory
tz = "UTC" # default to null
to_tz = "America/New_York" # default to null
allow_fail = false # default to true
```

### Output (with `--indent`)
```json
{
	"batch": [
		{
			"id": 0,
			"date": "2023-12-31T19:00:00.000000Z"
		},
		{
			"id": 1,
			"date": "2024-01-31T19:00:00.000000Z"
		}
	]
}
```

### CLI `--help`
```
usage: Convert CSV to Json [-h] [--indent] toml

positional arguments:
  toml

options:
  -h, --help  show this help message and exit
  --indent
```

## pipe2doc

Create a markdown doc on http client `--pipe`

### Usage

```
./http_get.toml --pipe | pipe2doc
```

## toml2json

Convert toml to json

### Usage
```toml
#!/usr/bin/env toml2json

[[batch]]
id = 1

[[batch]]
id = 2
```

### Output (with `--indent`)
```json
{
	"batch": [
		{
			"id": 0
		},
		{
			"id": 1
		}
	]
}
```

### CLI `--help`
```
usage: Convert Toml to Json [-h] [--indent] toml

positional arguments:
  toml

options:
  -h, --help  show this help message and exit
  --indent
```