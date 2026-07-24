import re

from vmt.cogs.transcribe import (
    EMBED_FIELD_LIMIT,
    PAGE_CHAR_LIMIT,
    fits_in_fields,
    split_into_pages,
)


def squash(text):
    # whitespace at page boundaries gets trimmed, so compare without it
    return re.sub(r"\s+", "", text)


def test_short_text_is_one_page():
    assert split_into_pages("hello world", limit=100) == ["hello world"]


def test_text_exactly_at_limit_is_one_page():
    text = "a" * 100
    assert split_into_pages(text, limit=100) == [text]


def test_empty_text_is_one_empty_page():
    assert split_into_pages("", limit=100) == [""]
    assert split_into_pages("   ", limit=100) == [""]


def test_pages_respect_limit():
    text = "word " * 2000
    pages = split_into_pages(text, limit=100)
    assert all(len(page) <= 100 for page in pages)


def test_breaks_on_whitespace_never_mid_word():
    text = "banana " * 500
    pages = split_into_pages(text, limit=50)
    for page in pages:
        assert all(token == "banana" for token in page.split())


def test_no_content_lost():
    text = "the quick brown fox jumps over the lazy dog " * 300
    pages = split_into_pages(text, limit=137)
    assert squash("".join(pages)) == squash(text)


def test_monster_word_gets_hard_split():
    text = "a" * 250
    pages = split_into_pages(text, limit=100)
    assert pages == ["a" * 100, "a" * 100, "a" * 50]


def test_monster_word_between_normal_words():
    text = "hi " + "b" * 150 + " bye"
    pages = split_into_pages(text, limit=100)
    assert squash("".join(pages)) == squash(text)
    assert all(len(page) <= 100 for page in pages)


def test_page_count_math():
    # 10 words of 9 chars each incl separator, 3 fit per 29-char page
    text = " ".join(["12345678"] * 10)
    pages = split_into_pages(text, limit=29)
    assert len(pages) == 4
    assert pages[0] == "12345678 12345678 12345678"


def test_default_limit_is_page_char_limit():
    text = "word " * 3000
    pages = split_into_pages(text)
    assert all(len(page) <= PAGE_CHAR_LIMIT for page in pages)
    assert len(pages) > 1


def test_page_limit_leaves_embed_headroom():
    # description caps at 4096 and the whole embed at 6000, the label plus
    # title plus footer need to fit alongside a full page. our title and
    # footer are short strings, 256 + 512 is way more than they ever use
    label_overhead = len("**Translation (Into PT-BR)**\n\n")
    assert PAGE_CHAR_LIMIT + label_overhead <= 4096
    assert PAGE_CHAR_LIMIT + label_overhead + 256 + 512 <= 6000


def test_fits_in_fields_short_transcript():
    assert fits_in_fields("short and sweet")


def test_fits_in_fields_boundary():
    assert fits_in_fields("a" * EMBED_FIELD_LIMIT)
    assert not fits_in_fields("a" * (EMBED_FIELD_LIMIT + 1))


def test_fits_in_fields_long_translation_forces_paging():
    assert fits_in_fields("short", "also short")
    assert not fits_in_fields("short", "b" * (EMBED_FIELD_LIMIT + 1))


def test_fits_in_fields_ignores_missing_translation():
    assert fits_in_fields("a" * EMBED_FIELD_LIMIT, None)
