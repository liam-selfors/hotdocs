import review_packet_builder


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_mapping(obj):
    if isinstance(obj, dict):
        return obj
    return vars(obj)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_sealed_component(repo_root, slug, comp_id):
    base = repo_root / "specs" / "components" / slug
    r_id = f"R-{slug.upper()}-001"
    ac_id = f"AC-{slug.upper()}-001"
    _write(
        base / "component.md",
        (
            "---\n"
            f"id: {comp_id}\n"
            f"title: {comp_id} fixture component\n"
            "status: draft\n"
            "owners: [lselfors@gmail.com]\n"
            "sealed: true\n"
            f"source_path: fake-legacy/{slug}\n"
            "---\n\n"
            f"# {comp_id}\n"
        ),
    )
    _write(
        base / "requirements" / f"{r_id}.md",
        (
            f"# {r_id}\n\n"
            f"**{r_id}** -- fixture placeholder requirement.\n"
        ),
    )
    _write(
        base / "acceptance" / f"{ac_id}.md",
        (
            f"# {ac_id}\n\n"
            f"Covers: {r_id}\n"
            "Kind: compiled\n\n"
            "```gherkin\n"
            "Given a fixture precondition\n"
            "When nothing is exercised\n"
            "Then nothing is asserted\n"
            "```\n"
        ),
    )


def _make_fake_provenance_tracker(repo_root):
    mod_dir = repo_root / "gen" / "provenance-tracker"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "provenance_tracker.py").write_text(
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {\n"
        "        'scope': 'blast-radius',\n"
        "        'ready': False,\n"
        "        'components': {\n"
        "            'comp-foo': {\n"
        "                'hit': True,\n"
        "                'verification_report': {\n"
        "                    'component_id': 'comp-foo',\n"
        "                    'criteria': [],\n"
        "                    'requirement_results': {},\n"
        "                    'interface_drift': False,\n"
        "                    'mutation_score': 1.0,\n"
        "                    'overall': 'pass',\n"
        "                },\n"
        "                'license_scan': {'blocked': False},\n"
        "                'secret_scan': {'flagged': False},\n"
        "            },\n"
        "            'comp-bar': {\n"
        "                'hit': False,\n"
        "                'verification_report': None,\n"
        "                'license_scan': None,\n"
        "                'secret_scan': None,\n"
        "            },\n"
        "        },\n"
        "        'capabilities': {},\n"
        "        'not_ready_reasons': ['comp-bar: no provenance for current spec state'],\n"
        "    }\n"
    )


def test_provenance_hit_status_reflects_both_components_accurately(tmp_path):
    repo_root = tmp_path
    _make_sealed_component(repo_root, "foo", "comp-foo")
    _make_sealed_component(repo_root, "bar", "comp-bar")
    _make_fake_provenance_tracker(repo_root)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "comp-bar"], repo_root
    )

    status = _get(packet, "provenance_hit_status")
    status_map = _as_mapping(status)

    assert set(status_map.keys()) == {"comp-foo", "comp-bar"}
    assert _get(status, "comp-foo") is True
    assert _get(status, "comp-bar") is False