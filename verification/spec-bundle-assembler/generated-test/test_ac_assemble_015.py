import spec_bundle_assembler


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_component(
    repo_root,
    slug,
    title,
    depends_on,
    req_id,
    req_text,
    ac_id,
    gherkin,
    interface_library,
    interface_data=None,
):
    comp_dir = repo_root / "specs" / "components" / slug
    depends_str = "[]" if not depends_on else "[" + ", ".join(depends_on) + "]"
    _write(
        comp_dir / "component.md",
        f"""---
id: comp-{slug}
title: {title}
status: draft
owners: [team-a]
sealed: true
source_path: legacy/{slug}/
depends_on: {depends_str}
---

# {title}

## Purpose

{title} is a test fixture component.
""",
    )
    _write(
        comp_dir / "requirements" / f"{req_id}.md",
        f"""# {req_id}

**{req_id}** — {req_text}
""",
    )
    _write(
        comp_dir / "acceptance" / f"{ac_id}.md",
        f"""# {ac_id}

Covers: {req_id}
Kind: generated-test

```gherkin
{gherkin}
```
""",
    )
    _write(comp_dir / "interface" / "library.md", interface_library)
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    if interface_data:
        for name, content in interface_data.items():
            _write(comp_dir / "interface" / "data" / f"{name}.md", content)


def _write_glossary(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )


def _write_target(repo_root):
    _write_component(
        repo_root,
        "target",
        "Target",
        depends_on=["comp-bar"],
        req_id="R-TARGET-001",
        req_text="`use_bar()` MUST call comp-bar's `do_bar` function.",
        ac_id="AC-TARGET-001",
        gherkin="Given a target component\nWhen use_bar is called\nThen do_bar is invoked",
        interface_library="# Library\n\n```\nuse_bar() -> None\n```\n",
    )


def _get(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def test_resolves_unowned_type_to_its_real_owner(tmp_path):
    repo_root = tmp_path
    _write_glossary(repo_root)
    _write_target(repo_root)

    bar_interface = "# Library\n\n```\ndo_bar(w: Widget) -> None\n```\n"
    _write_component(
        repo_root,
        "bar",
        "Bar",
        depends_on=[],
        req_id="R-BAR-001",
        req_text="`do_bar(w)` MUST process the given widget.",
        ac_id="AC-BAR-001",
        gherkin="Given a widget w\nWhen do_bar(w) is called\nThen w is processed",
        interface_library=bar_interface,
    )

    widget_doc = "# `Widget`\n\nA widget type with fields `name` and `size`.\n"
    _write_component(
        repo_root,
        "baz",
        "Baz",
        depends_on=[],
        req_id="R-BAZ-001",
        req_text="`baz()` MUST exist.",
        ac_id="AC-BAZ-001",
        gherkin="Given nothing\nWhen baz() is called\nThen it succeeds",
        interface_library="# Library\n\n```\nbaz() -> None\n```\n",
        interface_data={"Widget": widget_doc},
    )

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-target", "AC-TARGET-001", repo_root
    )

    dep_interfaces = _get(bundle, "dependency_interfaces")
    assert dep_interfaces is not None
    bar_entry = dep_interfaces["comp-bar"]

    assert bar_interface in bar_entry
    assert "fields `name` and `size`" in bar_entry
    assert "comp-baz" in bar_entry
    assert "Widget" in bar_entry


def test_unresolved_type_is_skipped_silently(tmp_path):
    repo_root = tmp_path
    _write_glossary(repo_root)
    _write_target(repo_root)

    bar_interface = "# Library\n\n```\ndo_bar(g: Gadget) -> None\n```\n"
    _write_component(
        repo_root,
        "bar",
        "Bar",
        depends_on=[],
        req_id="R-BAR-001",
        req_text="`do_bar(g)` MUST process the given gadget.",
        ac_id="AC-BAR-001",
        gherkin="Given a gadget g\nWhen do_bar(g) is called\nThen g is processed",
        interface_library=bar_interface,
    )

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-target", "AC-TARGET-001", repo_root
    )

    dep_interfaces = _get(bundle, "dependency_interfaces")
    assert dep_interfaces is not None
    bar_entry = dep_interfaces["comp-bar"]

    assert bar_interface in bar_entry
    assert bar_entry.count("Gadget") == 1


def test_ambiguous_type_is_skipped_silently(tmp_path):
    repo_root = tmp_path
    _write_glossary(repo_root)
    _write_target(repo_root)

    bar_interface = "# Library\n\n```\ndo_bar(s: Sprocket) -> None\n```\n"
    _write_component(
        repo_root,
        "bar",
        "Bar",
        depends_on=[],
        req_id="R-BAR-001",
        req_text="`do_bar(s)` MUST process the given sprocket.",
        ac_id="AC-BAR-001",
        gherkin="Given a sprocket s\nWhen do_bar(s) is called\nThen s is processed",
        interface_library=bar_interface,
    )

    _write_component(
        repo_root,
        "baz",
        "Baz",
        depends_on=[],
        req_id="R-BAZ-001",
        req_text="`baz()` MUST exist.",
        ac_id="AC-BAZ-001",
        gherkin="Given nothing\nWhen baz() is called\nThen it succeeds",
        interface_library="# Library\n\n```\nbaz() -> None\n```\n",
        interface_data={"Sprocket": "# `Sprocket`\n\nBaz's version of Sprocket.\n"},
    )

    _write_component(
        repo_root,
        "qux",
        "Qux",
        depends_on=[],
        req_id="R-QUX-001",
        req_text="`qux()` MUST exist.",
        ac_id="AC-QUX-001",
        gherkin="Given nothing\nWhen qux() is called\nThen it succeeds",
        interface_library="# Library\n\n```\nqux() -> None\n```\n",
        interface_data={"Sprocket": "# `Sprocket`\n\nQux's version of Sprocket.\n"},
    )

    bundle = spec_bundle_assembler.assemble_criterion(
        "comp-target", "AC-TARGET-001", repo_root
    )

    dep_interfaces = _get(bundle, "dependency_interfaces")
    assert dep_interfaces is not None
    bar_entry = dep_interfaces["comp-bar"]

    assert bar_interface in bar_entry
    assert bar_entry.count("Sprocket") == 1