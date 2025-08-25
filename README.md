# **LLMPromptBuilder**

# **Overview**
The PromptBuilder is a Python utility designed to create **modular, concise, and composable prompts**. It allows you to structure your prompt into separate sections (e.g., _Role_, _Objective_, _Constraints_, _Domain Knowledge_, _Workflow_), control their ordering, and render them into a final string for use with LLMs.


This tool helps maintain clarity by keeping prompt parts organized and reusable, with support for:
- Modular sections
- Ordered (1., 2., 3.) and unordered (-) nested lists
- Dict-based nesting for parent–child lists (e.g., {"Preprocess": \["Clean", "Normalize"\]})
- Variable interpolation ({{var}} syntax)
- Conditional sections with include_if
- JSON and YAML import/export
- Section ordering and metadata


# **Core Classes**

## `Section`
A dataclass that represents an individual section of a prompt.

### **Attributes:**
- name _(str)_: Unique identifier for the section.
- content _(str)_: Section body text (auto-generated from structured input).
- max_chars _(Optional[int])_: Maximum number of characters allowed; truncates with ellipsis if exceeded.
- title _(Optional[str])_: Header or label for the section (e.g., # Role, ## Objective).
- include_if _(Optional[Mapping[str, Any]])_: Conditions for including this section, evaluated against context during compile().
- header_size _(int)_: Header size as an integer from 1 to 6, representing from markdown H1 to H6, defaults to 1.

### **Key Methods:**
#### `s.render`
Renders section into a string.

**Parameters:**
- context _(dict)_: Variables for substitution using {{var}} syntax.

## `PromptBuilder`
The main class used to build prompts.

**Attributes:**
- sections _(OrderedDict[str, Section])_: Holds all defined sections.
- meta _(dict)_: Metadata dictionary for custom information (e.g., owner, version).
- order _(list[str])_: Explicit order of section names for compilation.

## **Key Methods:**
Key methods used to design and compile prompts



### `pb.set`
Adds or replaces a section.

#### **Parameters:**
- name _(str)_: Section identifier.
- value _(SectionPayload)_: Content. Can be:
    - str
    - list/tuple/set → rendered as a bullet or numbered list
    - dict → rendered as key → nested children (e.g., {"Preprocess": \["Clean", "Normalize"\]})
- title _(Optional\[str\])_: A header string for the section.
- max_chars _(Optional\[int\])_: Truncates content if too long.
- ordered _(bool)_: Whether lists are numbered (True) or bulleted (False).
- include_if _(Optional\[Mapping\[str, Any\]\])_: Contextual conditions for including this section.
- header_size _(int)_: Header size as an integer from 1 to 6, representing from markdown H1 to H6, defaults to 1.

#### **Returns**
- PromptBuilder instance

---

### `pb.append`
Appends content to an existing section.

#### **Parameters:**
- name _(str)_: Target section.
- more _(SectionPayload)_: New content to append.
- ordered _(bool)_: Whether to render appended lists as ordered or unordered.
#### **Returns**
- PromptBuilder instance
#### **Example:**
```
pb.append("constraints", {"tone": "professional"})
```

---

### `pb.set_order`
Defines the rendering order of sections.

#### **Parameters:**
- names _(list\[str\])_: List of section names.
#### **Returns:**
- PromptBuilder instance
#### **Example:**
```python
pb.set_order(["role", "objective", "workflow"])
```

---

### `pb.remove`
Removes a section by name.

#### **Parameters:**
- name _(str)_: Name of the section to be removed.
#### **Returns:**
- PromptBuilder instance
#### **Example:**
```python
pb.remove("role")
```

---

### `pb.compile`
Compiles all sections into a final string.

#### **Parameters:**
- context _(dict)_: Variables for substitution using {{var}} syntax.
- joiner _(str)_: Separator between sections (default: "\n\n").
- include_empty _(bool)_: Whether to include sections with empty content.
#### **Returns:**
    A markdown string
#### **Example:**
```python
ctx={
    "user":{
        "lang": "pt-br"
    }
}

pb.compile(context=ctx)
```

---

### `pb.to_json`
Serializes a prompt into JSON.

#### **Parameters:**
- pretty _(bool)_: If True, JSON output is prettyfied
#### **Returns:**
- JSON string
#### **Example:**
```python
pb.to_json()
```

---

### `pb.from_json`
De-serializes a prompt from a JSON string.

#### **Parameters:**
- source _(str)_: The JSON to be de-serialized
#### **Returns:**
- PromptBuilder instance
#### **Example:**
```python
pb.from_json()
```

---

### `pb.to_yaml`
Serializes a prompt into YAML.
**This method has no parameters**
#### **Returns:**
- YAML string
#### **Example:**
```python
pb.to_yaml()
```

---

#### `pb.from_yaml`
De-serializes a prompt from a YAML string.

#### **Parameters:**
- source _(str)_: The YAML to be de-serialized
#### **Returns:**
- PromptBuilder instance
#### **Example:**
```python
pb.from_yaml()
```



## **Variable Substitution**
Use {{variable}} inside section content. Supports **nested lookup** using dotted paths.

**The code:**
```python
pb = PromptBuilder()
pb.set("objective", "Summarize: {{user.query}}", title="# Objective")
compiled = pb.compile(context={"user": {"query": "Compare XGBoost and LightGBM"}})
```

**Outputs:**
```markdown
# Objective
Summarize: Compare XGBoost and LightGBM
```



## **Examples**
### **Basic Usage**
```python
from prompt_builder import PromptBuilder

pb = PromptBuilder()

pb.set("role", "You are a data analyst.", title="# Role")
pb.set("objective", ["Find patterns", "Be concise"], title="# Objective", ordered=True)
pb.set("constraints", {"avoid": ["jargon"], "style": "clear"}, title="# Constraints")

print(pb.compile())
```

**Output:**
```markdown
# Role
You are a data analyst.

# Objective
1. Find patterns
2. Be concise

# Constraints
- avoid: jargon
- style: clear
```



#### **Appending Content**
```python
pb.append("constraints", {"tone": "professional"})
```

**Output:**
```markdown
# Role
You are a data analyst.

# Objective
1. Find patterns
2. Be concise

# Constraints
- avoid: jargon
- style: clear
- tone: professional
```



### **Nested Lists**
```python
pb.set("workflow", [
    "Collect data",
    {"Preprocess": ["Clean", "Normalize"]},
    "Analyze",
    {"Report": ["Draft", "Review"]},
    "Ship"
], title="# Workflow", ordered=True)
```

**Output:**
```markdown
# Workflow
1. Collect data
2. Preprocess
  3. Clean
  4. Normalize
5. Analyze
6. Report
  7. Draft
  8. Review
9. Ship
```



### **Conditional Sections**
```python
pb.set("lang",
       "Responda em português do Brasil.",
       title="# User Language",
       include_if={"user.locale": "pt-BR"})
```
This section will only be included if context["user"]["locale"] == "pt-BR" when compiling.
    


## **Best Practices**
- Use **ordered=True** for processes or workflows.
- Keep each section concise and modular.
- Use set_order to enforce consistent structure.
- Use `include_if` for context-specific sections without duplicating logic.
- Avoid heavy use of `append()`.
- Prefer lists/tuples over sets (sort sets for determinism = extra cost).
- Export/load prompt definitions with `to_json`/`from_json` or `to_yaml`/`from_yaml`.
    - If loading from serialized prompts in production:
        - Prefer JSON, YAML is ~3–10× slower to parse.
        - Load at startup(once) and keep in memory (IO read is slower than average building at runtime).

Unless you’re doing hundreds of prompt builds with prompts larger than 100KB per request or aiming for <30 ms end-to-end, building at runtime won’t be your bottleneck.