from job_hunter.cv_parser import extract_text


class _FakePage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text


class _FakeReader:
    def __init__(self, pages: list[str]):
        self.pages = [_FakePage(text) for text in pages]


def test_extract_text_joins_pages():
    reader = _FakeReader(["Page one content.", "Page two content."])
    assert extract_text("ignored.pdf", reader=reader) == "Page one content.\nPage two content."


def test_extract_text_handles_blank_pages():
    reader = _FakeReader(["Some text.", None, "More text."])
    assert extract_text("ignored.pdf", reader=reader) == "Some text.\n\nMore text."


def test_extract_text_strips_surrounding_whitespace():
    reader = _FakeReader(["  Padded content.  "])
    assert extract_text("ignored.pdf", reader=reader) == "Padded content."
