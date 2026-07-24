from vmt.cache import Cache, checksum_of

AUDIO = b"fake-ogg-bytes"


async def test_transcript_cache_miss_then_hit(db):
    cache = Cache(db)
    checksum = checksum_of(AUDIO)

    assert await cache.get_transcript(checksum) is None

    await cache.store_transcript(checksum, "hello world", "elevenlabs", 4.2)
    assert await cache.get_transcript(checksum) == ("hello world", "elevenlabs")

    # different audio bytes do not hit the same entry
    assert await cache.get_transcript(checksum_of(b"other-bytes")) is None


async def test_checksum_is_sha256_hex_of_bytes(db):
    checksum = checksum_of(AUDIO)
    assert len(checksum) == 64
    assert checksum == checksum_of(AUDIO)
    assert checksum != checksum_of(AUDIO + b"x")


async def test_translation_cache_keyed_by_checksum_and_lang(db):
    cache = Cache(db)
    checksum = checksum_of(AUDIO)

    assert await cache.get_translation(checksum, "DE") is None

    await cache.store_translation(checksum, "DE", "hallo welt")
    await cache.store_translation(checksum, "FR", "bonjour le monde")

    assert await cache.get_translation(checksum, "DE") == "hallo welt"
    assert await cache.get_translation(checksum, "FR") == "bonjour le monde"
    assert await cache.get_translation(checksum, "ES") is None
    assert await cache.get_translation(checksum_of(b"other"), "DE") is None


async def test_translation_cache_overwrite(db):
    cache = Cache(db)
    checksum = checksum_of(AUDIO)

    await cache.store_translation(checksum, "DE", "v1")
    await cache.store_translation(checksum, "DE", "v2")
    assert await cache.get_translation(checksum, "DE") == "v2"
