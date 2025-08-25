# **LLMPromptBuilder**

## **Overview**

`PromptBuilder` helps you create **modular, concise, composable prompts**. Split your prompt into sections (e.g., *Role*, *Objective*, *Constraints*, *Domain Knowledge*, *Workflow*), control ordering, and render a final string for LLMs.

**Features**

* Modular sections (add, append, remove, order)
* Ordered (**1., 2., 3.**) or unordered (**-**) nested lists
* Dict-first nesting (e.g., `{"Preprocess": ["Clean", "Normalize"]}`)
* Variable interpolation with `{{var}}` and literal-protect blocks with `{{{...}}}`
* Conditional sections with `include_if` (equality, truthy/falsey, membership)
* JSON / YAML import & export
* Section headers with **Markdown H1–H6** via `title` + `header_size`
* Add prebuilt `Section` instances (`add_section`, `add_sections`) and a `make_section` factory
* `include_empty` to render header-only sections

---

## **Core Classes**

### `Section`

Represents a single prompt section.

**Attributes**

* `name: str` — unique id
* `content: str` — section text (auto-rendered from structured payloads)
* `max_chars: Optional[int]` — truncates with an ellipsis if exceeded
* `title: Optional[str]` — header text; pass plain `"Role"` and control level with `header_size`. If you pass an explicit Markdown header (e.g., `"# Role"`), it’s used verbatim.
* `header_size: int` — Markdown header level **1..6** (`#`..`######`), default **1**
* `include_if: Optional[Mapping[str, Any]]` — conditions evaluated at `compile()` (see below)

**Method**

#### `Section.render(context: Optional[dict] = None) -> str`

* **Parameters**

  * `context`: mapping used for variable substitution in `content` and `title`.

    * When `context is None`, **no** substitution is performed.
    * When `context` is `{}`, substitution runs but missing keys leave tokens unchanged.
* **Returns**

  * Rendered string for the section:

    * If `title` is present → `"#{...} {title}\n{content}"` (level from `header_size`)
    * If `content` becomes empty after trims/truncation → returns `""`. (Header-only rendering is handled by `PromptBuilder.compile(include_empty=True)`.)
* **Notes**

  * Applies `max_chars` before macro substitution.
  * Substitution runs only if `context is not None`.

---

### `PromptBuilder`

Main builder.

**Attributes**

* `sections: OrderedDict[str, Section]` — name → `Section`
* `meta: dict` — freeform metadata
* `order: list[str]` — explicit render order; any unnamed sections are appended at the end

---

## **Method Reference (Complete & Transparent)**

### `pb.set(...) -> PromptBuilder`

Add or replace a section from a structured payload.

**Signature**

```python
set(
  name: str,
  value: SectionPayload,               # str | list/tuple/set | dict
  *,
  title: Optional[str] = None,
  max_chars: Optional[int] = None,
  ordered: bool = False,
  include_if: Optional[Mapping[str, Any]] = None,
  header_size: int = 1,
) -> PromptBuilder
```

**Parameters**

* `name`: unique section id.
* `value`: the content payload.

  * `str` → used as is (excess blank lines normalized).
  * `list/tuple/set` → rendered as a bullet/numbered list; sets are **sorted** for determinism.
  * `dict` → dict-first nesting; each key becomes a labeled node with its children.
* `title`: header text (plain), e.g., `"Objective"`. If you pass `"# Objective"`, it’s used verbatim.
* `max_chars`: truncate `content` to this many chars with an ellipsis.
* `ordered`: when `True`, lists are numbered; otherwise `-`.
* `include_if`: conditions to include this section at `compile()`; see **Conditional Sections**.
* `header_size`: H1..H6 (1..6). Ignored if `title` is Markdown (e.g., starts with `#`).

**Returns**

* `PromptBuilder` (self), to allow chaining.

**Side-effects**

* Inserts or replaces `sections[name]`. Ensures `name` is present in `order`.

---

### `pb.append(...) -> PromptBuilder`

Append more content to an existing section.

**Signature**

```python
append(
  name: str,
  more: SectionPayload,
  *,
  ordered: bool = False,
) -> PromptBuilder
```

**Parameters**

* `name`: target section id. If not present, behaves like `set(name, more, ...)`.
* `more`: payload rendered using the same rules as in `set`.

**Returns**

* `PromptBuilder` (self).

**Side-effects**

* Concatenates the newly rendered string to the existing section’s `content` with a newline.

---

### `pb.add_section(section: Section, *, replace: bool = True, copy: bool = True) -> PromptBuilder`

Insert a **prebuilt** `Section`.

**Parameters**

* `section`: a `Section` instance (may be shared/cached elsewhere).
* `replace`: if `False` and a section with the same name exists → **raises** `ValueError`.
* `copy`: when `True` (default), the section is **deep-copied** to prevent later external mutations from affecting the builder; set to `False` for maximum speed when you control the lifecycle.

**Returns**

* `PromptBuilder` (self).

**Side-effects / Errors**

* Adds or replaces `sections[section.name]`. Appends name to `order` if new.
* `ValueError` when `replace=False` and the key exists.

---

### `pb.add_sections(sections: Iterable[Section], *, replace: bool = True, copy: bool = True) -> PromptBuilder`

Bulk add `Section` instances.

**Parameters**

* `sections`: iterable of `Section`s.
* `replace`, `copy`: same semantics as `add_section`.

**Returns**

* `PromptBuilder` (self).

**Side-effects**

* Iteration order defines append order for **new** section names.

---

### `PromptBuilder.make_section(...) -> Section`

Factory to create a `Section` from a structured payload (same rendering rules as `set`), without inserting it into the builder.

**Signature**

```python
make_section(
  name: str,
  value: SectionPayload,
  *,
  title: Optional[str] = None,
  max_chars: Optional[int] = None,
  ordered: bool = False,
  include_if: Optional[Mapping[str, Any]] = None,
  header_size: int = 1,
) -> Section
```

**Parameters / Returns**

* Same as `set`, but returns a standalone `Section`. Useful for composing or caching sections externally.

---

### `pb.set_order(names: Iterable[str]) -> PromptBuilder`

Define explicit render order.

**Parameters**

* `names`: iterable of section names. Unknown names are ignored; any existing sections not listed are appended at the end in their insertion order.

**Returns**

* `PromptBuilder` (self).

**Side-effects**

* Replaces `order` with the resolved sequence.

---

### `pb.remove(name: str) -> PromptBuilder`

Remove a section.

**Parameters**

* `name`: section id to remove.

**Returns**

* `PromptBuilder` (self).

**Side-effects**

* Deletes from `sections` and removes from `order` if present.

---

### `pb.compile(...) -> str`

Compile all sections to a single Markdown string.

**Signature**

```python
compile(
  *,
  context: Optional[Mapping[str, Any]] = None,
  joiner: str = "\n\n",
  include_empty: bool = False,
) -> str
```

**Parameters**

* `context`: mapping for **variable substitution** and **include\_if** evaluation.

  * `None` → no substitution; sections with `include_if` are **excluded**.
  * `{}` → substitution runs; missing keys leave tokens unchanged.
* `joiner`: separator between sections in the final output.
* `include_empty`: when `True`, renders **header-only** sections (title line without content).

**Returns**

* The final Markdown string.

**Inclusion rules**

* A section is rendered if:

  1. `include_if` is empty/None **or** all its conditions pass against `context`, **and**
  2. `render()` returns non-empty, **or** `include_empty=True` and the section has a header.

---

### `pb.to_dict() -> Dict[str, Any]`

Serialize the builder to a Python dict.

**Returns**

```python
{
  "meta": dict,
  "order": list[str],
  "sections": {
    name: {
      "name": str,
      "content": str,
      "max_chars": Optional[int],
      "title": Optional[str],
      "include_if": Optional[dict],
      "header_size": int,
    },
    ...
  },
}
```

---

### `PromptBuilder.from_dict(data: Mapping[str, Any]) -> PromptBuilder`

Rehydrate a builder from a dict (inverse of `to_dict`).

**Parameters**

* `data`: dict with the structure shown above. Unknown keys are ignored.

**Returns**

* `PromptBuilder` instance.

---

### `pb.to_json(pretty: bool = True) -> str`

Serialize to JSON.

**Parameters**

* `pretty`: when `True` (default), indent for readability; when `False`, compact.

**Returns**

* JSON string (UTF-8 friendly with `ensure_ascii=False`).

---

### `PromptBuilder.from_json(source: str) -> PromptBuilder`

Deserialize from a JSON string.

**Parameters**

* `source`: JSON produced by `to_json()`.

**Returns**

* `PromptBuilder` instance.

**Errors**

* Raises `json.JSONDecodeError` if invalid JSON; may raise `KeyError`-like issues only if the structure is wildly off (internally handled leniently).

---

### `pb.to_yaml() -> str`

Serialize to YAML (requires `PyYAML`).

**Parameters**

* *None*

**Returns**

* YAML string.

**Errors**

* `ImportError` if `PyYAML` is not installed.

---

### `PromptBuilder.from_yaml(source: str) -> PromptBuilder`

Deserialize from YAML.

**Parameters**

* `source`: YAML string previously generated by `to_yaml()`.

**Returns**

* `PromptBuilder` instance.

**Errors**

* `ImportError` if `PyYAML` is not installed.
* `ValueError` if parsed YAML is not a mapping/dict.

---

## **Variable Substitution (Macros)**

Use `{{variable}}` to substitute values from `context`. Supports **dotted paths** and **literal blocks**.

**Rules**

* **Dotted lookup** — `{{user.locale}}` → `context["user"]["locale"]`
* **Content & titles** — substitution runs in both.
* **Context** — runs only if `context is not None` (use `{}` to enable with no values).
* **Missing keys** — tokens remain unchanged (no exceptions).
* **Literal blocks** — wrap substrings with `{{{ ... }}}` to **prevent** substitutions inside.
* **Whitespace tolerant** — `{{  user.locale  }}` is OK.

**Examples**

1. **Basic substitution**

```python
pb = PromptBuilder()
pb.set("objective", "Summarize: {{user.query}}", title="Objective", header_size=2)
pb.compile(context={"user": {"query": "Compare XGBoost and LightGBM"}})
# ->
# ## Objective
# - Summarize: Compare XGBoost and LightGBM
```

2. **Missing keys preserved**

```python
pb.set("meta", "User: {{user.name}} | Plan: {{app.plan}}", title="Meta", header_size=6)
pb.compile(context={"user": {"name": "Ana"}})
# ->
# ###### Meta
# - User: Ana | Plan: {{app.plan}}
```

3. **Literal protection**

```python
pb.set("note", "Render literally: {{{ {{not_a_var}} }}}", title="Note")
pb.compile(context={})
# ->
# # Note
# - Render literally: {{not_a_var}}
```

4. **Title substitution**

```python
pb.set("lang", "Use Brazilian Portuguese.", title="Language ({{user.locale}})", header_size=3)
pb.compile(context={"user": {"locale": "pt-BR"}})
# ->
# ### Language (pt-BR)
# - Use Brazilian Portuguese.
```

---

## **Conditional Sections (`include_if`)**

`include_if` is an **AND** matcher evaluated against `context`. If `context` is `None`, any section with conditions is excluded.

**Supported patterns**

* **Equality**: `{"user.locale": "pt-BR"}` — include if `context["user"]["locale"] == "pt-BR"`.
* **Truthy**: `{"flags.beta": True}` — include if the looked-up value is truthy.
* **Falsey**: `{"flags.beta": False}` — include if the looked-up value is falsey.
* **Membership (array/tuple/set)**: `{"user.role": ["admin", "owner"]}` — include if looked-up value is **one of** the listed values.

**Membership example**

```python
pb.set(
    "admin-tools",
    ["Manage users", "View audit logs"],
    title="Admin Tools", header_size=2,
    include_if={"user.role": ["admin", "owner"]},
)
pb.compile(context={"user": {"role": "owner"}})   # included
pb.compile(context={"user": {"role": "member"}})  # excluded
pb.compile(context={})                            # excluded
```

---

## **Examples**

### Basic usage

```python
pb = PromptBuilder()
pb.set("role", "You are a data analyst.", title="Role", header_size=1)
pb.set("objective", ["Find patterns", "Be concise"], title="Objective", header_size=2, ordered=True)
pb.set("constraints", {"avoid": ["jargon"], "style": "clear"}, title="Constraints")
print(pb.compile())
```

**Output**

```markdown
# Role
- You are a data analyst.

## Objective
1. Find patterns
2. Be concise

# Constraints
- avoid: jargon
- style: clear
```

### Appending content

```python
pb.append("constraints", {"tone": "professional"})
print(pb.compile())
```

**Output**

```markdown
# Constraints
- avoid: jargon
- style: clear
- tone: professional
```


### Add prebuilt sections

```python
sec = PromptBuilder.make_section(
  "policy",
  {"Safety": ["No PII", "No secrets"]},
  title="Policy", header_size=3, ordered=True
)
pb.add_section(sec)                 # copy=True (default), replace=True
pb.add_sections([sec], copy=True)   # bulk
```

### Header-only sections

```python
pb.set("empty", "", title="Empty Section", header_size=4)
print(pb.compile(include_empty=True))
# ->
# #### Empty Section
```

---

## **Best Practices**

* Use **`ordered=True`** for processes/workflows (contiguous numbering included).
* Keep sections small & composable; avoid heavy `append()` loops in hot paths.
* Prefer lists/tuples; sets are supported but sorted for determinism (slight overhead).
* Use `include_if` to gate content by locale/flags/roles without duplicating logic.
* Serialization:
  * Prefer **JSON** for speed; YAML is 3–10× slower to parse.
  * **Load at startup** and keep in memory; avoid per-request I/O.
* Performance: even \~100 KB prompts render in a few milliseconds; network/model latency dominates.
