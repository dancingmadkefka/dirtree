"""Controller-authored independent UTF-8 prefix oracle."""
import codecs
from dirtree.dirtree_llm import read_file_content


def test_utf8_prefix_matrix(tmp_path):
    source = tmp_path / 'unicode.txt'
    strings = ['', 'ASCII', 'é', '€', '😀', 'Aé€😀Z', '中文\r\ntext', 'e\u0301', 'αβγ', '😀é' * 10]
    for text in strings:
        data = text.encode('utf-8')
        source.write_bytes(data)
        for limit in range(len(data) + 2):
            truncated = len(data) > limit
            decoder = codecs.getincrementaldecoder('utf-8')()
            expected = decoder.decode(data[:limit], final=not truncated)
            if truncated:
                expected += '\n... [TRUNCATED]'
            assert read_file_content(source, limit, lambda *args: None) == (
                expected, len(expected.encode('utf-8'))
            ), (text, limit)
