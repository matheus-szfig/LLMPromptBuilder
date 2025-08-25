from __future__ import annotations
from dataclasses import dataclass, field
from collections import OrderedDict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union
from copy import deepcopy
import re
import json

# Optional YAML support
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

# -----------------------------
# Prompt Builder — modular, concise, composable with nested lists (dict-style),
# JSON/YAML I/O, and conditional sections
# -----------------------------

SectionPayload = Union[str, Iterable[Any], Mapping[str, Any]]


# ---- Utilities ---------------------------------------------------------------

def _lookup(path: str, data: Mapping[str, Any]) -> Any:
    """Dotted-path lookup, e.g., _lookup('user.locale', ctx)."""
    cur: Any = data
    for part in path.split('.'):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _conditions_match(conds: Mapping[str, Any], context: Optional[Mapping[str, Any]]) -> bool:
    """
    Evaluate simple include_if conditions against context.

    Supported shapes:
      {"user.locale": "pt-BR"}          -> equality
      {"flags.beta": True}              -> truthy
      {"user.role": ["admin","owner"]}  -> membership
    If context is None and conditions exist, returns False.
    """
    if not conds:
        return True
    if context is None:
        return False
    for key, expected in conds.items():
        actual = _lookup(key, context)
        if isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        elif expected is True:
            if not bool(actual):
                return False
        elif expected is False:
            if bool(actual):
                return False
        else:
            if actual != expected:
                return False
    return True


# Precompiled regexes (micro-optimization)
_TRIPLE = re.compile(r"\{\{\{(.*?)\}\}\}", re.DOTALL)
_DOUBLE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_PROT = re.compile(r"\uE000(\d+)\uE000")

def _apply_macros(text: str, context: Mapping[str, Any]) -> str:
    """Very small mustache-like {{var}} with dotted paths and {{{escape}}} blocks."""
    if not text:
        return text
    protected: List[str] = []

    def protect_store(m: re.Match) -> str:
        protected.append(m.group(1))
        return f"\uE000{len(protected)-1}\uE000"

    # Protect triple-brace blocks from interpolation
    text = _TRIPLE.sub(protect_store, text)

    def repl(m: re.Match) -> str:
        key = m.group(1).strip()
        val = _lookup(key, context)
        return str(val) if val is not None else m.group(0)

    text = _DOUBLE.sub(repl, text)

    def unprotect(m: re.Match) -> str:
        idx = int(m.group(1))
        return protected[idx]

    text = _PROT.sub(unprotect, text)
    return text


# ---- Nested rendering (dict-first design) -----------------------------------

def _is_nested_structure(x: Any) -> bool:
    return isinstance(x, (Mapping, list, tuple, set))


def _bullet_label(idx: int, ordered: bool) -> str:
    """Per-level numbering (no contiguous numbering across nested levels)."""
    return f"{idx}." if ordered else "-"


def _render_mapping_at_level(
    d: Mapping[str, Any],
    level: int,
    *,
    ordered: bool,
) -> List[str]:
    """
    Render a mapping where each key is a labeled node.
    Each key becomes a sibling at the current level.
    """
    lines: List[str] = []
    indent = "  " * level
    for idx, (k, v) in enumerate(d.items(), start=1):
        bullet = _bullet_label(idx, ordered)
        k_str = str(k).strip()
        if _is_nested_structure(v):
            lines.append(f"{indent}{bullet} {k_str}")
            lines.extend(_render_nested(v, level + 1, ordered=ordered))
        elif v is None:
            lines.append(f"{indent}{bullet} {k_str}")
        else:
            lines.append(f"{indent}{bullet} {k_str}: {str(v).strip()}")
    return lines


def _render_sequence_at_level(
    seq: Iterable[Any],
    level: int,
    *,
    ordered: bool,
) -> List[str]:
    """
    Render a sequence. Special cases:
      - Single-key dicts are treated as labeled parents: {"Preprocess": [...]}
      - Pair style still supported: ["Label", children]
      - Other mappings in the sequence with >1 key expand as labeled siblings at this level
    """
    lines: List[str] = []
    indent = "  " * level

    # Stabilize sets to deterministic order
    if isinstance(seq, set):
        seq_list = sorted(seq, key=lambda x: str(x))
    else:
        seq_list = list(seq)

    for idx, item in enumerate(seq_list, start=1):
        bullet = _bullet_label(idx, ordered)

        # 1) Single-key dict shorthand: {"Preprocess": ["Clean", "Normalize"]}
        if isinstance(item, Mapping) and len(item) == 1:
            (k, v), = item.items()
            k_str = str(k).strip()
            if _is_nested_structure(v):
                lines.append(f"{indent}{bullet} {k_str}")
                lines.extend(_render_nested(v, level + 1, ordered=ordered))
            elif v is None:
                lines.append(f"{indent}{bullet} {k_str}")
            else:
                lines.append(f"{indent}{bullet} {k_str}: {str(v).strip()}")
            continue

        # 2) Pair style: ["Label", children]
        if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
            label = item[0].strip()
            children = item[1] if len(item) > 1 else None
            lines.append(f"{indent}{bullet} {label}")
            if _is_nested_structure(children):
                lines.extend(_render_nested(children, level + 1, ordered=ordered))
            elif children is not None:
                # Non-nested child: render as simple text line (first bullet at child level)
                child_indent = "  " * (level + 1)
                child_bullet = _bullet_label(1, ordered)
                lines.append(f"{child_indent}{child_bullet} {str(children).strip()}")
            continue

        # 3) Generic mapping with multiple keys: render each key as siblings under this slot
        if isinstance(item, Mapping):
            lines.append(f"{indent}{bullet}")  # placeholder node
            lines.extend(_render_mapping_at_level(item, level + 1, ordered=ordered))
            continue

        # 4) Nested sequence without a label — anonymous group under this slot
        if isinstance(item, (list, tuple, set)):
            lines.append(f"{indent}{bullet}")
            lines.extend(_render_sequence_at_level(item, level + 1, ordered=ordered))
            continue

        # 5) Plain scalar
        s = str(item).strip()
        if s:
            lines.append(f"{indent}{bullet} {s}")

    return lines


def _render_nested(
    value: Any,
    level: int = 0,
    *,
    ordered: bool = False,
) -> List[str]:
    """Render nested structures with dict-first, label-and-children semantics (per-level numbering)."""
    if isinstance(value, str):
        bullet = _bullet_label(1, ordered)
        return [f"{'  ' * level}{bullet} {value.strip()}"]

    if isinstance(value, Mapping):
        return _render_mapping_at_level(value, level, ordered=ordered)

    if isinstance(value, (list, tuple, set)):
        return _render_sequence_at_level(value, level, ordered=ordered)

    # Fallback scalars
    bullet = _bullet_label(1, ordered)
    return [f"{'  ' * level}{bullet} {str(value).strip()}"]


def _coerce_to_str(value: SectionPayload, *, ordered: bool = False, contiguous_order: bool = False) -> str:
    """
    Render payloads to concise strings with unlimited (practical) nesting.

    NOTE: contiguous_order is deprecated and ignored. Numbering is per-level.
    """
    if isinstance(value, str):
        # Normalize excessive blank lines
        s = re.sub(r"\n{3,}", "\n\n", value.strip())
        return s
    if isinstance(value, (Mapping, list, tuple, set)):
        return "\n".join(_render_nested(value, ordered=ordered))
    return str(value).strip()


# ---- Core dataclasses --------------------------------------------------------

@dataclass
class Section:
    name: str
    content: str = ""
    max_chars: Optional[int] = None
    # 'title' acts as the HEADER TEXT (title). If it already starts with '#',
    # it's treated as a full Markdown header (explicit). Otherwise, we render
    # '#'*header_size + ' ' + title.
    title: Optional[str] = None
    include_if: Optional[Mapping[str, Any]] = None

    # Header level for Markdown headers when 'title' is a plain title (1..6).
    header_size: int = 1

    def _header(self, context: Optional[Mapping[str, Any]]) -> Optional[str]:
        """Compute the header line based on title and header_size."""
        if not self.title:
            return None

        header_text = _apply_macros(self.title, context) if (context is not None) else self.title
        stripped = header_text.lstrip()

        # If user passed explicit Markdown like "# Role", use as-is.
        if stripped.startswith("#"):
            return header_text

        # Otherwise, compose Markdown header with selected level.
        lvl = max(1, min(6, int(self.header_size or 1)))
        return f"{'#' * lvl} {header_text}".strip()

    def render(self, context: Optional[Mapping[str, Any]] = None) -> str:
        s = self.content.strip()
        if self.max_chars and len(s) > self.max_chars:
            s = s[: self.max_chars].rstrip() + "…"

        # Apply macros to content when context is provided (even if it's an empty dict)
        if context is not None and ("{{" in s or "{{{" in s):
            s = _apply_macros(s, context)

        header = self._header(context)

        if header:
            # If content is empty, return "" (compile() with include_empty handles header-only)
            return f"{header}\n{s}" if s else ""
        return s


@dataclass
class PromptBuilder:
    sections: "OrderedDict[str, Section]" = field(default_factory=OrderedDict)
    meta: Dict[str, Any] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)

    # ---- Section management ----
    def set(
        self,
        name: str,
        value: SectionPayload,
        *,
        title: Optional[str] = None,
        max_chars: Optional[int] = None,
        ordered: bool = False,
        include_if: Optional[Mapping[str, Any]] = None,
        contiguous_order: bool = False,  # deprecated, ignored
        header_size: int = 1,
    ) -> "PromptBuilder":
        rendered = _coerce_to_str(value, ordered=ordered, contiguous_order=contiguous_order)
        section = Section(
            name=name,
            content=rendered,
            max_chars=max_chars,
            title=title,
            include_if=include_if,
            header_size=header_size,
        )
        self.sections[name] = section
        if name not in self.order:
            self.order.append(name)
        return self

    def append(self, name: str, more: SectionPayload, *, ordered: bool = False, contiguous_order: bool = False) -> "PromptBuilder":
        existing = self.sections.get(name)
        if not existing:
            return self.set(name, more, ordered=ordered, contiguous_order=contiguous_order)
        added = _coerce_to_str(more, ordered=ordered, contiguous_order=contiguous_order)
        new_content = (existing.content + "\n" + added).strip()
        self.sections[name] = Section(
            name=name,
            content=new_content,
            max_chars=existing.max_chars,
            title=existing.title,
            include_if=existing.include_if,
            header_size=existing.header_size,
        )
        return self

    def add_section(self, section: Section, *, replace: bool = True, copy: bool = True) -> "PromptBuilder":
        """
        Insert or replace a fully-formed Section.

        Args:
            section: Section instance to add.
            replace: If False and a section with the same name exists, raise ValueError.
            copy: If True (default), deepcopy the Section to avoid external mutations.

        Returns:
            self
        """
        s = deepcopy(section) if copy else section
        exists = s.name in self.sections
        if exists and not replace:
            raise ValueError(f"Section '{s.name}' already exists; set replace=True to overwrite.")
        self.sections[s.name] = s
        if not exists:
            self.order.append(s.name)
        return self

    def add_sections(self, sections: Iterable[Section], *, replace: bool = True, copy: bool = True) -> "PromptBuilder":
        """Bulk add Section instances. Iteration order defines append order for new names."""
        for sec in sections:
            self.add_section(sec, replace=replace, copy=copy)
        return self

    @staticmethod
    def make_section(
        name: str,
        value: SectionPayload,
        *,
        title: Optional[str] = None,
        max_chars: Optional[int] = None,
        ordered: bool = False,
        include_if: Optional[Mapping[str, Any]] = None,
        contiguous_order: bool = False,  # deprecated, ignored
        header_size: int = 1,
    ) -> Section:
        """
        Convenience factory: builds a Section from structured payload,
        using the same rendering rules as `set()`.
        """
        rendered = _coerce_to_str(value, ordered=ordered, contiguous_order=contiguous_order)
        return Section(
            name=name,
            content=rendered,
            max_chars=max_chars,
            title=title,
            include_if=include_if,
            header_size=header_size,
        )

    def set_order(self, names: Iterable[str]) -> "PromptBuilder":
        self.order = [n for n in names if n in self.sections]
        for n in self.sections:
            if n not in self.order:
                self.order.append(n)
        return self

    def remove(self, name: str) -> "PromptBuilder":
        self.sections.pop(name, None)
        self.order = [n for n in self.order if n != name]
        return self

    # ---- Compile ----
    def compile(
        self,
        *,
        context: Optional[Mapping[str, Any]] = None,
        joiner: str = "\n\n",
        include_empty: bool = False,
    ) -> str:
        parts: List[str] = []
        for name in self.order:
            sec = self.sections[name]
            if sec.include_if and not _conditions_match(sec.include_if, context):
                continue

            rendered = sec.render(context=context)

            if rendered:
                parts.append(rendered)
            elif include_empty:
                # Show header/title even if content is empty when include_empty=True
                header = sec._header(context)
                parts.append(header if header is not None else "")

        # If include_empty=True, preserve intentional empties (don't filter)
        if include_empty:
            return joiner.join(parts)

        # Otherwise, drop empty strings
        return joiner.join(p for p in parts if p)

    # ---- I/O helpers ----
    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": self.meta,
            "order": list(self.order),
            "sections": {
                k: {
                    "name": v.name,
                    "content": v.content,
                    "max_chars": v.max_chars,
                    "title": v.title,
                    "include_if": v.include_if,
                    "header_size": v.header_size,
                } for k, v in self.sections.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PromptBuilder":
        pb = cls()
        pb.meta = dict(data.get("meta", {}))
        for name, sd in data.get("sections", {}).items():
            pb.sections[name] = Section(
                name=sd.get("name", name),
                content=sd.get("content", ""),
                max_chars=sd.get("max_chars"),
                title=sd.get("title"),
                include_if=sd.get("include_if"),
                header_size=sd.get("header_size", 1),
            )
        pb.order = list(data.get("order", list(pb.sections.keys())))
        return pb

    def to_json(self, pretty: bool = True) -> str:
        """
        Serialize the PromptBuilder to a JSON string.

        Args:
            pretty (bool): If True (default), format the output with indentation
                for readability. If False, produce compact JSON.

        Returns:
            str: A JSON representation of the prompt builder, including metadata,
            section order, and section contents.
        """
        return json.dumps(self.to_dict(), indent=4 if pretty else None, ensure_ascii=False)

    @classmethod
    def from_json(cls, source: str) -> "PromptBuilder":
        """
        Deserialize a PromptBuilder instance from a JSON string.

        Args:
            source (str): JSON string previously generated by `to_json()`.

        Returns:
            PromptBuilder: A new instance reconstructed from the JSON definition.
        """
        return cls.from_dict(json.loads(source))

    def to_yaml(self) -> str:
        """
        Serialize the PromptBuilder to a YAML string.

        Requires the `PyYAML` package to be installed.

        Returns:
            str: A YAML representation of the prompt builder, including metadata,
            section order, and section contents.

        Raises:
            ImportError: If PyYAML is not installed.
        """
        if yaml is None:
            raise ImportError("PyYAML is not installed. Run `pip install pyyaml`.")
        return yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, source: str) -> "PromptBuilder":
        """
        Deserialize a PromptBuilder instance from a YAML string.

        Args:
            source (str): YAML string previously generated by `to_yaml()`.

        Returns:
            PromptBuilder: A new instance reconstructed from the YAML definition.

        Raises:
            ImportError: If PyYAML is not installed.
            ValueError: If the YAML content does not represent a mapping/dict.
        """
        if yaml is None:
            raise ImportError("PyYAML is not installed. Run `pip install pyyaml`.")
        data = yaml.safe_load(source) or {}
        if not isinstance(data, Mapping):
            raise ValueError("YAML does not represent a mapping/dict")
        return cls.from_dict(data)
