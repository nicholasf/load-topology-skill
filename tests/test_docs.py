from topology.docs import END_MARKER, START_MARKER, index_entries, render_docs, render_file_section, update_readme

SAMPLE_TOPOLOGY = """\
schema_version = 1
provider = "tailscale"

[[machines]]
name = "pond"
hostname = "pond"

[[machines]]
name = "hut"
hostname = "hut"

[[benchmarks]]
hostname = "pond"
model = "qwen3.8-27b:latest"
"""

SAMPLE_PLAYBOOK = """\
[[playbook]]
name = "start-pond-qwen"
aliases = ["wake pond up"]

  [[playbook.tasks]]
  hosts = "pond"
  command = "echo hi"
"""


def test_index_entries_finds_each_array_with_line_and_label(tmp_path):
    path = tmp_path / 'topology.toml'
    path.write_text(SAMPLE_TOPOLOGY)
    entries = index_entries(str(path))
    assert entries == [
        {'section': 'machines', 'line': 4, 'label': 'pond'},
        {'section': 'machines', 'line': 8, 'label': 'hut'},
        {'section': 'benchmarks', 'line': 12, 'label': 'pond'},
    ]


def test_index_entries_ignores_nested_array_of_tables(tmp_path):
    path = tmp_path / 'topology-playbook-pond.toml'
    path.write_text(SAMPLE_PLAYBOOK)
    entries = index_entries(str(path))
    # only the top-level [[playbook]] is indexed, not the nested [[playbook.tasks]]
    assert entries == [{'section': 'playbook', 'line': 1, 'label': 'start-pond-qwen'}]


def test_index_entries_empty_file_returns_empty_list(tmp_path):
    path = tmp_path / 'empty.toml'
    path.write_text('schema_version = 1\n')
    assert index_entries(str(path)) == []


def test_clean_value_strips_quotes():
    from topology.docs import _clean_value
    assert _clean_value('"pond"') == 'pond'


def test_clean_value_truncates_long_values():
    from topology.docs import _clean_value
    long_value = '"' + ('x' * 100) + '"'
    result = _clean_value(long_value, limit=10)
    assert len(result) == 10
    assert result.endswith('…')


def test_render_file_section_groups_by_section_with_links(tmp_path):
    path = tmp_path / 'topology.toml'
    path.write_text(SAMPLE_TOPOLOGY)
    out = render_file_section(str(path))
    assert '### `topology.toml`' in out
    assert '**machines** (2)' in out
    assert '[line 4](topology.toml#L4)' in out
    assert '[line 8](topology.toml#L8)' in out
    assert '**benchmarks** (1)' in out


def test_render_file_section_no_entries(tmp_path):
    path = tmp_path / 'empty.toml'
    path.write_text('schema_version = 1\n')
    out = render_file_section(str(path))
    assert '(no entries)' in out


def test_render_docs_wraps_in_markers(tmp_path):
    path = tmp_path / 'topology.toml'
    path.write_text(SAMPLE_TOPOLOGY)
    out = render_docs([str(path)])
    assert out.startswith(START_MARKER)
    assert out.rstrip().endswith(END_MARKER)
    assert '## File contents' in out


# ── update_readme ──────────────────────────────────────────────────────────────

def test_update_readme_creates_file_when_absent(tmp_path):
    readme = tmp_path / 'README.md'
    update_readme(str(readme), 'GENERATED\n')
    assert readme.read_text() == 'GENERATED\n'


def test_update_readme_appends_when_no_markers(tmp_path):
    readme = tmp_path / 'README.md'
    readme.write_text('# My repo\n\nSome hand-written content.\n')
    update_readme(str(readme), f'{START_MARKER}\nGENERATED\n{END_MARKER}\n')
    content = readme.read_text()
    assert 'Some hand-written content.' in content
    assert 'GENERATED' in content


def test_update_readme_replaces_existing_block(tmp_path):
    readme = tmp_path / 'README.md'
    readme.write_text(
        f'# My repo\n\nIntro text.\n\n{START_MARKER}\nOLD CONTENT\n{END_MARKER}\n\nFooter text.\n'
    )
    update_readme(str(readme), f'{START_MARKER}\nNEW CONTENT\n{END_MARKER}\n')
    content = readme.read_text()
    assert 'Intro text.' in content
    assert 'Footer text.' in content
    assert 'NEW CONTENT' in content
    assert 'OLD CONTENT' not in content
    assert content.count(START_MARKER) == 1
