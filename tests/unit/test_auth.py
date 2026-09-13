from app.auth.api_keys import digest_key, generate_key


def test_generated_key_is_verifiable_without_storing_raw_secret() -> None:
    raw, prefix, digest = generate_key()
    assert raw.startswith(f"crawl_{prefix}_")
    assert digest == digest_key(raw)
    assert raw.encode() not in digest
