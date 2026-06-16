# edgecall functions

Every `*.py` file in this directory is autoloaded at startup. Each one
registers a function the weak model can choose to run.

## Add a function

Create a file here, decorate a callable:

```python
from edgecall.registry import register

@register(id="0006", desc="say hello to a name")
def run(args):
    name = args.get("name", "world")
    return {"greeting": f"hello, {name}"}
```

Rules:

- **`id`** is a short stable string (letters, digits, `_`, `-`, up to 16
  chars) the model echoes back to pick this function. `NEXT` is reserved.
- **`desc`** is a single natural-language line the model reads on the menu.
  Make it describe *when to use this*, not how it works.
- **`run(args)`** receives one dict. `args["request"]` is always the
  original natural-language request; any other keys are caller-supplied.
  Return any JSON-serialisable value. Returning an `{"error": ...}` dict is
  fine; raising is caught and reported as a `function-error`.

## Order matters

Functions are paginated **3 at a time in load order**, and the model pages
through with `NEXT`. Files load in sorted filename order, so the numeric
prefixes (`0001_`, `0002_`, ...) set the menu order. **Put your most-used
functions first**: a function on page 3 costs the model two blind `NEXT`
replies to reach, and weak models are not good at paging blindly.

## Restart to pick up changes

Functions are loaded once at startup. After adding or editing a file,
restart the server (`edgecall serve`) or re-run `edgecall dispatch`.
