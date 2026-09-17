from datetime import datetime as RealDatetime
from pathlib import Path

import pytest

import dirtree.dirtree_llm as llm


MARKER = '\n... [TRUNCATED]'


def quiet(*args, **kwargs):
    pass


@pytest.fixture(autouse=True)
def frozen_datetime(monkeypatch):
    class FrozenDatetime:
        @classmethod
        def now(cls):
            return RealDatetime(2031, 2, 3, 4, 5, 6)

    monkeypatch.setattr(llm, 'datetime', FrozenDatetime)


@pytest.mark.parametrize('data,limit,expected', [
    (b'', 0, ''),
    (b'x', 0, MARKER),
    (b'a' * 10000, 7, 'a' * 7 + MARKER),
    ('AéZ'.encode('utf-8'), 2, 'A' + MARKER),
    ('AéZ'.encode('utf-8'), 3, 'Aé' + MARKER),
    ('A€Z'.encode('utf-8'), 2, 'A' + MARKER),
    ('A€Z'.encode('utf-8'), 3, 'A' + MARKER),
    ('A😀Z'.encode('utf-8'), 2, 'A' + MARKER),
    ('A😀Z'.encode('utf-8'), 3, 'A' + MARKER),
    ('A😀Z'.encode('utf-8'), 4, 'A' + MARKER),
    ('A😀Z'.encode('utf-8'), 5, 'A😀' + MARKER),
    ('é😀'.encode('utf-8'), 6, 'é😀'),
    (b'\xc3\xa9\xff', 2, 'é' + MARKER),
    (b'\xc3\xa9A\xff', 3, 'éA' + MARKER),
    (b'A\xffXYZ', 3, 'AÿX' + MARKER),
    (b'A\xe2Qtail', 2, 'Aâ' + MARKER),
    (b'\xed\xa0\x80tail', 3, '\xed\xa0\x80' + MARKER),
    (b'\xc0\xaftail', 2, '\xc0\xaf' + MARKER),
    (b'A\xe2\x82', 3, 'Aâ\x82'),
    (b'caf\xe9', 20, 'café'),
])
def test_bounded_reads_and_decoding(tmp_path, monkeypatch, data, limit, expected):
    source = tmp_path / 'sample.txt'
    source.write_bytes(data)
    original_open = Path.open
    requests = []
    received = []

    class ObservedReader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def read(self, size=-1):
            requests.append(size)
            assert 0 <= size <= limit + 1, 'unbounded or oversized read'
            assert sum(requests) <= limit + 1, 'aggregate read budget exceeded'
            chunk = self.stream.read(size)
            received.append(len(chunk))
            return chunk

    def observed_open(path, mode='r', *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        if path == source:
            assert mode == 'rb'
            return ObservedReader(stream)
        return stream

    monkeypatch.setattr(Path, 'open', observed_open)
    assert llm.read_file_content(source, limit, quiet) == (
        expected, len(expected.encode('utf-8'))
    )
    assert requests
    assert sum(received) == min(len(data), limit + 1)


def test_negative_limit_rejected_before_open(tmp_path, monkeypatch):
    source = tmp_path / 'sample.txt'
    source.write_bytes(b'synthetic')
    calls = []
    original_open = Path.open

    def observed_open(path, *args, **kwargs):
        calls.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', observed_open)
    with pytest.raises(ValueError):
        llm.read_file_content(source, -1, quiet)
    assert calls == []


def prepare(tmp_path, content='synthetic é\n'):
    root = tmp_path / 'project'
    root.mkdir()
    source = root / 'sample.txt'
    source.write_bytes(content.encode('utf-8'))
    output = tmp_path / 'exports'
    return root, source, output


def generate(root, source, output, tree=None):
    return llm.generate_llm_export(
        root_dir=root,
        tree_lines=tree if tree is not None else ['project', '└── sample.txt'],
        paths_in_tree_for_llm_check=[source],
        max_llm_file_size=100000,
        llm_content_extensions_set={'txt'},
        cli_exclude_patterns=[],
        smart_dir_excludes=[],
        smart_file_excludes_for_llm=[],
        interactive_dir_excludes_llm=set(),
        log_func=quiet,
        output_dir=output,
        add_file_marker=True,
    )


def candidate(output, index):
    suffix = '' if index == 0 else '_{}'.format(index)
    return output / ('dirtree_export_project_20310203_040506' + suffix + '.md')


def test_existing_export_and_repeated_timestamp_preserved(tmp_path):
    root, source, output = prepare(tmp_path)
    output.mkdir()
    existing = candidate(output, 0)
    sentinel = b'\x00\xffsynthetic existing export\r\n'
    existing.write_bytes(sentinel)
    first, size, count = generate(root, source, output)
    assert first is not None and first != existing
    assert (size, count) == (len(source.read_bytes()), 1)
    first_bytes = first.read_bytes()
    source.write_bytes(b'changed synthetic source')
    second, size, count = generate(root, source, output)
    assert second is not None and second not in {existing, first}
    assert (size, count) == (len(source.read_bytes()), 1)
    assert existing.read_bytes() == sentinel
    assert first.read_bytes() == first_bytes
    assert b'changed synthetic source' in second.read_bytes()


def test_collision_exhaustion_is_bounded_and_preserves_all_files(tmp_path, monkeypatch):
    root, source, output = prepare(tmp_path)
    output.mkdir()
    snapshots = {}
    for index in range(100):
        path = candidate(output, index)
        snapshots[path] = b'\xffsynthetic-' + str(index).encode('ascii')
        path.write_bytes(snapshots[path])
    original_open = Path.open
    attempts = []

    def observed_open(path, mode='r', *args, **kwargs):
        if path.parent == output:
            attempts.append((path, mode))
        return original_open(path, mode, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', observed_open)
        result = generate(root, source, output)
    assert result == (None, 0, 0)
    assert attempts == [(candidate(output, index), 'x') for index in range(100)]
    assert set(output.iterdir()) == set(snapshots)
    for path, data in snapshots.items():
        assert path.read_bytes() == data


def test_exclusive_creation_handles_racing_creator(tmp_path, monkeypatch):
    root, source, output = prepare(tmp_path)
    original_open = Path.open
    attempts = []
    raced_path = candidate(output, 0)
    sentinel = b'synthetic concurrent export\x00\xff'

    def racing_open(path, mode='r', *args, **kwargs):
        if path.parent == output:
            attempts.append((path, mode))
            if len(attempts) == 1:
                with original_open(path, 'wb') as stream:
                    stream.write(sentinel)
        return original_open(path, mode, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', racing_open)
        exported, size, count = generate(root, source, output)
    assert exported == candidate(output, 1)
    assert attempts == [(raced_path, 'x'), (exported, 'x')]
    assert raced_path.read_bytes() == sentinel
    assert (size, count) == (len(source.read_bytes()), 1)


@pytest.mark.parametrize('tree_run,source_run', [(7, 4), (3, 9), (0, 0), (2, 2)])
def test_public_export_fences_and_verbatim_content(tmp_path, tree_run, source_run):
    content = '  synthetic é\r\n' + '`' * source_run + '\r\ninline `' + 'x  \n\n'
    root, source, output = prepare(tmp_path, content)
    clean_tree = ['project', '└── name' + '`' * tree_run + '.txt']
    tree = ['\x1b[32m' + clean_tree[0] + '\x1b[0m [LLM✓]', clean_tree[1]]
    exported, size, count = generate(root, source, output, tree)
    assert exported is not None
    markdown = exported.read_bytes().decode('utf-8')
    tree_fence = '`' * max(3, tree_run + 1)
    source_fence = '`' * max(3, source_run + 1)
    assert '\n## Directory Structure\n' + tree_fence + '\n' + '\n'.join(clean_tree) + '\n' + tree_fence + '\n' in markdown
    assert '### `sample.txt`\n\n' + source_fence + 'txt\n' + content + '\n' + source_fence + '\n' in markdown
    assert markdown.startswith('\u200b<!-- DIRTREE_GENERATED_FILE -->\n# Directory Tree for: project\n')
    assert 'Generated on: 2031-02-03 04:05:06\n' in markdown
    assert '\n## File Contents\n' in markdown
    assert (size, count) == (len(content.encode('utf-8')), 1)


@pytest.mark.parametrize('extension,hint', [
    ('py`', ''),
    ('py hint', ''),
    ('pyé', ''),
    ('py+_-09', 'py+_-09'),
    ('py', 'py'),
])
@pytest.mark.parametrize('explicit_extensions', [False, True])
@pytest.mark.parametrize('content', ['hello', '  hello é\r\n```\r\ninline `x  \n\n'])
def test_public_export_language_hint_allowlist(tmp_path, extension, hint, explicit_extensions, content):
    root, original_source, output = prepare(tmp_path, content)
    source = original_source.rename(root / ('sample.' + extension))
    tree = ['project', '└── ' + source.name]
    exported, size, count = llm.generate_llm_export(
        root_dir=root,
        tree_lines=tree,
        paths_in_tree_for_llm_check=[source],
        max_llm_file_size=100000,
        llm_content_extensions_set={extension} if explicit_extensions else None,
        cli_exclude_patterns=[],
        smart_dir_excludes=[],
        smart_file_excludes_for_llm=[],
        interactive_dir_excludes_llm=set(),
        log_func=quiet,
        output_dir=output,
        add_file_marker=True,
    )
    assert exported is not None
    markdown = exported.read_bytes().decode('utf-8')
    fence = '````' if '```' in content else '```'
    heading = '### `' + source.name + '`\n\n'
    block = markdown.split(heading, 1)[1]
    assert block == fence + hint + '\n' + content + '\n' + fence + '\n'
    assert '\n## Directory Structure\n```\n' + '\n'.join(tree) + '\n```\n' in markdown
    assert source.read_bytes() == content.encode('utf-8')
    assert (size, count) == (len(content.encode('utf-8')), 1)
