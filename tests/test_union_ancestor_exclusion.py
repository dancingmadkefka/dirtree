import fnmatch

import pytest

from dirtree.dirtree_llm import (
    generate_llm_export,
    should_include_content_for_llm,
)


CASES = [
    pytest.param(
        ['generated'], 'generated/report.txt', 'kept/keep.txt', False,
        id='ancestor-basename',
    ),
    pytest.param(
        ['src/generated'], 'src/generated/report.txt',
        'other/generated/keep.txt', False,
        id='root-relative-ancestor-only',
    ),
    pytest.param(
        ['cache-?'], 'src/cache-a/deep/report.txt',
        'src/cache-long/keep.txt', False,
        id='wildcard-basename',
    ),
    pytest.param(
        ['src/gen[0-9]'], 'src/gen2/deep/report.txt',
        'src/genx/keep.txt', False,
        id='wildcard-root-relative-ancestor',
    ),
    pytest.param(
        ['generated'], 'packages/service/generated/deeper/still/report.txt',
        'packages/service/kept/keep.txt', False,
        id='excluded-directory-nested-further',
    ),
    pytest.param(
        ['src/generated'], 'src/generated/deeper/still/report.txt',
        'src/kept/keep.txt', False,
        id='root-relative-excluded-directory-nested-further',
    ),
    pytest.param(
        ['generated'], 'src/generated-extra/report.txt',
        'src/kept/keep.txt', True,
        id='no-substring-matching',
    ),
    pytest.param(
        ['workspace'], 'src/report.txt', 'src/kept/keep.txt', True,
        id='root-basename-is-not-an-ancestor-candidate',
    ),
    pytest.param(
        ['.'], 'src/report.txt', 'src/kept/keep.txt', True,
        id='root-relative-dot-is-not-an-ancestor-candidate',
    ),
    pytest.param(
        ['outside-parent'], 'src/report.txt', 'src/kept/keep.txt', True,
        id='ancestor-outside-root-is-not-matched',
    ),
    pytest.param(
        ['build'], 'Build/report.txt', 'src/kept/keep.txt',
        not fnmatch.fnmatch('Build', 'build'),
        id='preserve-platform-fnmatch-case-behavior',
    ),
    pytest.param(
        ['report.txt'], 'src/report.txt', 'src/kept/keep.txt', False,
        id='existing-file-basename-match',
    ),
    pytest.param(
        ['src/report.txt'], 'src/report.txt', 'other/keep.txt', False,
        id='existing-file-root-relative-match',
    ),
    pytest.param(
        ['*.py'], 'src/report.py', 'src/kept/keep.txt', False,
        id='existing-file-wildcard-match',
    ),
]


def _log(*args, **kwargs):
    pass


def _make_files(tmp_path, candidate_relative, sibling_relative):
    root = tmp_path / 'outside-parent' / 'workspace'
    records = []
    for relative, content in [
        (candidate_relative, 'UNION_CANDIDATE_CONTENT\n'),
        (sibling_relative, 'UNION_SIBLING_CONTENT\n'),
        ('top.txt', 'UNION_ROOT_FILE_CONTENT\n'),
    ]:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode('utf-8'))
        records.append((path, content))
    return root, records


def _gate(path, root, patterns, extensions):
    return should_include_content_for_llm(
        file_path=path,
        root_dir=root,
        file_size=path.stat().st_size,
        max_llm_file_size=4096,
        llm_content_extensions_set=extensions,
        cli_exclude_patterns=patterns,
        smart_dir_excludes=[],
        smart_file_excludes_for_llm=[],
        interactive_dir_excludes_llm=set(),
        log_func=_log,
    )


@pytest.mark.parametrize(
    'patterns,candidate_relative,sibling_relative,candidate_included', CASES
)
def test_direct_gate_ancestor_exclusion(
    tmp_path, patterns, candidate_relative, sibling_relative, candidate_included
):
    root, records = _make_files(tmp_path, candidate_relative, sibling_relative)
    for (path, _), expected in zip(records, [candidate_included, True, True]):
        assert _gate(path, root, patterns, {'txt', 'py'}) is expected


@pytest.mark.parametrize(
    'patterns,candidate_relative,sibling_relative,candidate_included', CASES
)
def test_public_export_enforces_ancestor_exclusion(
    tmp_path, patterns, candidate_relative, sibling_relative, candidate_included
):
    root, records = _make_files(tmp_path, candidate_relative, sibling_relative)
    # Deliberately supply every file, including excluded descendants, without
    # relying on traversal or tree filtering to enforce content exclusions.
    export_path, content_bytes, included_count = generate_llm_export(
        root_dir=root,
        tree_lines=[path.relative_to(root).as_posix() for path, _ in records],
        paths_in_tree_for_llm_check=[path for path, _ in records],
        max_llm_file_size=4096,
        llm_content_extensions_set={'txt', 'py'},
        cli_exclude_patterns=patterns,
        smart_dir_excludes=[],
        smart_file_excludes_for_llm=[],
        interactive_dir_excludes_llm=set(),
        log_func=_log,
        output_dir=tmp_path / 'exports',
        add_file_marker=False,
    )
    assert export_path is not None
    markdown = export_path.read_text(encoding='utf-8')
    expected_flags = [candidate_included, True, True]
    assert included_count == sum(expected_flags)
    assert content_bytes == sum(
        len(content.encode('utf-8'))
        for (_, content), expected in zip(records, expected_flags)
        if expected
    )
    for (path, content), expected in zip(records, expected_flags):
        heading = f'### `{path.relative_to(root).as_posix()}`\n'
        assert (heading in markdown) is expected
        assert (content in markdown) is expected


@pytest.mark.parametrize(
    'extensions,expected',
    [({'txt'}, True), ({'py'}, False), (set(), False)],
)
def test_explicit_extension_rules_remain_unchanged(tmp_path, extensions, expected):
    root, records = _make_files(tmp_path, 'src/report.TXT', 'src/kept/keep.txt')
    candidate = records[0][0]
    assert _gate(candidate, root, ['unrelated'], extensions) is expected
    # An allowed extension must not override an excluded ancestor.
    assert _gate(candidate, root, ['src'], extensions) is False
