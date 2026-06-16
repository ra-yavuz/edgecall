# edgecall

**Route a plain-language request to one of your own functions, using a
deliberately weak local model.** edgecall is a small, self-hosted, OpenAI-
compatible API. You POST a sentence like "what is the gold price"; a tiny
model (phi3-class, the kind that runs on a Raspberry Pi or a phone) reads a
short menu of your registered functions, picks one, and edgecall runs it and
returns the result.

The model never sees your whole function list at once. Functions are shown
a few at a time as a numbered menu, and the model pages through with a
"next" option until it picks one. That is the entire trick: pick one item
off a short list is the easiest thing a weak model can do, so a weak model
is enough.

## What it is for

You want useful, pre-programmed actions ("look up the gold price", "read out
the message of the day", "what's the weather") triggered by natural language,
but you do not want to pay for a frontier model or send anything to the
cloud. edgecall lets a cheap local model do the routing while you keep the
actual work in plain Python functions you control and extend.

- **Bring your own model.** edgecall does not host a model. It talks to any
  OpenAI-compatible `/v1` endpoint: llama.cpp's server, ollama, LM Studio,
  or a [hydra-llm](https://github.com/ra-yavuz/hydra-llm) model server.
- **Extend without retraining.** Add a function by dropping a Python file in
  a folder. Give it an id and a one-line description. Restart. Done.
- **Runs small.** The dispatcher is tiny; the heavy part (the model) is
  whatever endpoint you point it at. Designed for edge hardware.
- **OpenAI-compatible.** A `POST /v1/chat/completions` shim lets existing
  OpenAI clients drive it unmodified, alongside a native `/v1/dispatch`.

## How it works

```
request: "i need to know the current gold price"
   |
   v
edgecall shows the weak model menu page 0:
   0001  show the message of the day
   0002  find the current gold price
   0003  get the current weather for a location
   NEXT  none of these, see more options
   |
   model replies: 0002
   v
edgecall runs function 0002 -> { "price": 4347.1, "currency": "USD", ... }
```

If the right function is not on the current page, the model replies `NEXT`
and edgecall shows the next page. There is no embedding model and no index
to maintain: pages are just slices of your function list in registration
order. The trade-off is that a function deep in the list costs the model one
`NEXT` per page to reach, and weak models page blindly, so **put your most-
used functions first** (see [functions/README.md](functions/README.md)).

## Add a function

Every `*.py` file in the functions directory is autoloaded at startup:

```python
from edgecall.registry import register

@register(id="0006", desc="say hello to a name")
def run(args):
    name = args.get("name", "world")
    return {"greeting": f"hello, {name}"}
```

`args["request"]` is always the original sentence; other keys are whatever
the caller passed. Return any JSON-serialisable value. The bundled examples
include a message-of-the-day function that serves from a text file, plus
live gold-price and weather lookups over public no-key APIs.

## Quickstart

### With Docker Compose

```bash
git clone https://github.com/ra-yavuz/edgecall
cd edgecall
# Edit docker-compose.yml: set EDGECALL_MODEL_BASE_URL to your endpoint.
docker compose up -d

curl -s -X POST localhost:8900/v1/dispatch \
     -H 'content-type: application/json' \
     -d '{"request":"what is the gold price"}'
```

### <a name="install"></a>Install (Debian / Ubuntu)

From the signed apt repository:

```bash
sudo bash -c 'set -e; install -m 0755 -d /etc/apt/keyrings && curl -fsSL https://ra-yavuz.github.io/apt/pubkey.gpg -o /etc/apt/keyrings/ra-yavuz.gpg && echo "deb [signed-by=/etc/apt/keyrings/ra-yavuz.gpg] https://ra-yavuz.github.io/apt stable main" > /etc/apt/sources.list.d/ra-yavuz.list && apt update && apt install -y edgecall'
```

Or grab the `.deb` from [Releases](https://github.com/ra-yavuz/edgecall/releases) and `sudo apt install ./edgecall_*.deb`.

Then:

```bash
edgecall functions                 # list what is registered
edgecall serve                     # run the API on 127.0.0.1:8900
edgecall dispatch "what time is it" --trace   # route one request, no server
```

Configure with flags or environment variables:

| Variable | Flag | Default | Meaning |
|---|---|---|---|
| `EDGECALL_MODEL_BASE_URL` | `--model-base-url` | `http://localhost:11434/v1` | OpenAI-compatible endpoint |
| `EDGECALL_MODEL` | `--model` | `phi3` | model name to request |
| `EDGECALL_FUNCTIONS_DIR` | `--functions-dir` | bundled `functions/` | where function files live |
| `EDGECALL_HOST` / `EDGECALL_PORT` | `--host` / `--port` | `127.0.0.1` / `8900` | server bind |
| `EDGECALL_PAGE_SIZE` | `--page-size` | `3` | functions per menu page |
| `EDGECALL_MAX_RETRIES` | `--max-retries` | `1` | re-asks per page on a junk reply |

## API

- `POST /v1/dispatch` - `{"request": "...", "args": {...}, "trace": false}`
  returns `{"status", "function_id", "result", "error"}` (and `trace` if
  asked). `status` is one of `ok`, `function-error`, `exhausted`,
  `model-error`.
- `POST /v1/chat/completions` - OpenAI-compatible shim. The last user
  message is the request; the function result comes back as the assistant
  message content (JSON encoded). One request, one function, no streaming.
- `GET /v1/functions` - list registered functions.
- `GET /healthz`, `GET /` - liveness and an info page.

## The honest limitation

A weak model picking from a menu will sometimes pick wrong, and edgecall
will faithfully run whatever it picked. That is the deal you accept for not
paying for a frontier model. Mitigations baked in: a tight low-temperature
reply, strict parsing (only an id actually on the page is accepted), bounded
retries, and a full decision trace so you can see why a wrong call happened.
For high-stakes actions, do not rely on the model's pick alone; gate the
function itself.

## Disclaimer / no warranty

edgecall runs functions you register, on inputs chosen by an unreliable
language model, and exposes an HTTP API on a local port. It is provided **as
is, without warranty of any kind**, express or implied, including but not
limited to merchantability, fitness for a particular purpose, and
noninfringement.

By installing or running this software you accept that:

- You alone are responsible for any damage to your hardware, data, network,
  or system, and for what your registered functions do.
- The author and contributors are **not liable** for any harm, data loss,
  security incident, model output, function result, or other damages,
  however caused.
- Language model output is unreliable. The model will sometimes route a
  request to the wrong function. edgecall executes the function the model
  chooses. **Do not rely on it for safety-critical actions**; gate
  dangerous functions independently of the model's choice.
- Functions you add can do anything Python can do, including make network
  calls and touch the filesystem. You are responsible for what you register.
- The bundled example functions call third-party public APIs
  (`api.gold-api.com`, `api.open-meteo.com`); their availability and content
  are outside this project's control.

If you do not accept these terms, do not install or run this software.

Full legal license: see [`LICENSE`](LICENSE) (MIT).

## Author

[Ramazan Yavuz](https://ramazan-yavuz.tr). Part of a set of independent,
open-source tools published at [ra-yavuz.github.io](https://ra-yavuz.github.io/).
