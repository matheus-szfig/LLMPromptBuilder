# tests/test_prompt_builder.py
import re
import pytest
from hypothesis import given, strategies as st
from prompt_builder import PromptBuilder, Section

def test_basic_set_compile():
    pb = PromptBuilder()
    pb.set("role", "You are a data analyst.", title="Role", header_size=1)
    pb.set("objective", ["Find patterns", "Be concise"], title="Objective", header_size=2, ordered=True)

    out = pb.compile()
    assert "# Role" in out
    assert "## Objective" in out
    assert "1. Find patterns" in out
    assert "2. Be concise" in out

def test_per_level_numbering_no_contiguous():
    pb = PromptBuilder()
    pb.set("workflow", [
        "Collect data",
        {"Preprocess": ["Clean", "Normalize"]},
        "Analyze",
    ], title="Workflow", header_size=2, ordered=True)

    out = pb.compile()
    # Parent level numbered 1..n
    assert "1. Collect data" in out
    assert "2. Preprocess" in out
    # Child level restarts at 1 (no contiguous numbering)
    assert re.search(r"\n\s+1\. Clean", out)
    assert re.search(r"\n\s+2\. Normalize", out)

def test_include_if_membership():
    pb = PromptBuilder()
    pb.set("admin-tools", ["Manage users", "Audit logs"],
           title="Admin Tools", header_size=3,
           include_if={"user.role": ["admin", "owner"]})

    out_owner = pb.compile(context={"user": {"role": "owner"}})
    assert "Admin Tools" in out_owner

    out_member = pb.compile(context={"user": {"role": "member"}})
    assert "Admin Tools" not in out_member

    out_none = pb.compile(context=None)
    assert "Admin Tools" not in out_none

def test_macros_in_title_and_content_and_literal_block():
    pb = PromptBuilder()
    pb.set("lang", "Use {{user.lang}}.", title="Language ({{user.lang}})", header_size=3)
    pb.set("note", "Literal: {{{ {{not_a_var}} }}}", title="Note")

    out = pb.compile(context={"user": {"lang": "pt-BR"}})
    assert "### Language (pt-BR)" in out
    assert "Use pt-BR." in out
    assert "Literal:  {{not_a_var}}" in out  # triple braces protect

def test_append_and_auto_create():
    pb = PromptBuilder()
    pb.append("constraints", {"avoid": ["jargon", "cursing"]}, ordered=False)
    pb.append("constraints", {"style": "clear"}, ordered=False)
    out = pb.compile()
    assert "constraints" in pb.sections  # section created by append
    assert "- avoid\n  - jargon\n  - cursing" in out
    assert "- style: clear" in out

def test_add_section_copy_semantics():
    base = Section(name="policy", content="- No secrets", title="Policy", header_size=4)
    pb = PromptBuilder().add_section(base, copy=True)
    base.content = "MUTATED"  # should NOT affect builder when copy=True
    out = pb.compile()
    assert "MUTATED" not in out
    assert "No secrets" in out

def test_json_roundtrip_same_output():
    pb = PromptBuilder()
    pb.set("role", "You are {{user.role}}.", title="Role", header_size=1)
    original = pb.compile(context={"user": {"role": "tester"}})

    js = pb.to_json()
    pb2 = PromptBuilder.from_json(js)
    roundtripped = pb2.compile(context={"user": {"role": "tester"}})
    assert original == roundtripped

def test_yaml_roundtrip_if_available():
    yaml = pytest.importorskip("yaml")
    pb = PromptBuilder()
    pb.set("title", "X", title="T", header_size=2)
    y = pb.to_yaml()
    pb2 = PromptBuilder.from_yaml(y)
    assert pb2.compile() == pb.compile()

def test_max_chars_truncation():
    pb = PromptBuilder()
    pb.set("long", "A" * 10, title="Long", max_chars=5)
    out = pb.compile()
    assert "AAAAA…" in out

def test_remove_and_set_order():
    pb = PromptBuilder()
    pb.set("a", "A", title="A")
    pb.set("b", "B", title="B")
    pb.set_order(["b", "a"])
    out = pb.compile()
    assert out.index("# B") < out.index("# A")
    pb.remove("a")
    out2 = pb.compile()
    assert "# A" not in out2

@given(st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5))
def test_lists_render_without_errors(xs):
    pb = PromptBuilder()
    pb.set("s", xs, title="S", ordered=True)
    out = pb.compile()
    assert "S" in out