# RestTOML for JSON

## How to use it

First the `bin` folder will need to be in the path.

You will need to create the adapter before you can make the request, we will start with a dummy adapter, can be written in any language as long as it output json but will use Python for this.

`~/.config/resttoml/json/dummy.py`

```python
#!/usr/env/bin python3
import json
import sys

json.dump({
    "url": "https://api.example.com/", # The beginning of the URL
    "headers": { # The header to merge with in the request
        "Content-Type": "application/json; charset=UTF-8",
        "X-TOKEN": "I-am-token"
    },
    "verify": True # to verify TLS certificate
}, sys.stdout, indent="\t")
```
Also give it execute permission. oAuth are to be done with the adapter and place the token into the header.

To build the first request
```toml
#!/usr/env/bin -S rest_toml_json --adapter dummy.py

[http]
# The adapter url will be prepended to the endpoint
endpoint = "hello/world"
```

Make it executable and run `./request.toml`

## TOML Docs

### rest_toml_json

```toml
#!/usr/env/bin -S rest_toml_json --adapter dummy.py

# All argument default to string, but can type hinted with the following.
[arg.id] # --arg id=5
type = "int"

# Optional
[pipe.name]
# It works with anything that return json. Mandatory
script = "./other_request.toml"

# argument to pass to script defaults to []
arg = ["--arg", 'hello=world']

# add `--pipe` flag to script, default to true
pass_pipe_flag = true

# Pass `--arg` to script, default to false
pass_arg = false

# Mandatory
[http]
# Endpoint of the url. Mandatory, do not add query use [http.params]
# `hello/world/{id}` (`#d!` can be terminated with `//` or by another `#d!`)
endpoint = "hello/world/#d!arg/id"
# Http Method, default to "get"
method = "get"

# Optional, url query string
[http.params]
hello="world" # ?hello=world

# Optional, http headers
[http.headers]
X-Custom = "custom"

# Optional, http cookies
[http.cookies]
ACookie = "yum yum"

# The json payload
[http.payload]
value = "test"
# get a piece of data from the pipe (can also be use with params, headers and cookies)
title = "#d!pipe/name/body/title"
```

#### cli `--help`
```
usage: rest_toml_json [-h] [--adapter ADAPTER] [--show-request] [--show-header] [--pipe] [--indent] [--arg ARG] toml

Process HTTP Rest request for JSON

positional arguments:
  toml

options:
  -h, --help         show this help message and exit
  --adapter ADAPTER
  --show-request
  --show-header
  --pipe
  --indent
  --arg ARG
```

### rest_toml_json_batch

```toml
#!/usr/env/bin -S rest_toml_json_batch --adapter dummy.py

# Mandatory
[batch]
# It works with anything that return json. Mandatory
# Recommended with csv2json and toml2json
script = "./other_request.toml"
# argument to pass to script defaults to []
arg = []
# The key that contains the list, default to batch
key = "batch"

# Mandatory
[http]
# Endpoint of the url. Mandatory, do not add query use [http.params]
endpoint = "hello/world"
# Http Method, default to "get"
method = "get"

# Optional, url query string
[http.params]
hello="world" # ?hello=world

# Optional, http headers
[http.headers]
X-Custom = "custom"

# Optional, http cookies
[http.cookies]
ACookie = "yum yum"

# The json payload
[http.payload]
value = "test"
# get a piece of data from batch row (can also be use with params, headers and cookies)
title = "#d!batch/title"
```

#### cli `--help`
```
usage: rest_toml_json_batch [-h] [--adapter ADAPTER] [--show-request] toml

Process Batch HTTP Rest request for JSON

positional arguments:
  toml

options:
  -h, --help         show this help message and exit
  --adapter ADAPTER
  --show-request
```
