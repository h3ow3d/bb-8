"""Tests for redaction module."""
from __future__ import annotations

from app.redaction.redactor import (
    REDACTED,
    redact_dict,
    redact_list,
    redact_string,
    redact_text,
)

# A plausible-looking JWT for testing (not a real token)
_FAKE_JWT = (
    "******"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)

# A plausible-looking long base64 blob
_FAKE_B64 = "dGhpc2lzYWxvbmdiYXNlNjRzdHJpbmdmb3J0ZXN0aW5ncHVycG9zZXM="

# A plausible-looking hex string (32+ chars)
_FAKE_HEX = "a" * 33


class TestRedactString:
    def test_jwt_is_redacted(self):
        result, count = redact_string(_FAKE_JWT)
        assert result == REDACTED
        assert count == 1

    def test_long_base64_is_redacted(self):
        result, count = redact_string(_FAKE_B64)
        assert result == REDACTED
        assert count == 1

    def test_short_string_not_redacted(self):
        result, count = redact_string("hello")
        assert result == "hello"
        assert count == 0

    def test_normal_text_not_redacted(self):
        result, count = redact_string("my-pod-name")
        assert result == "my-pod-name"
        assert count == 0

    def test_long_hex_string_is_redacted(self):
        result, count = redact_string(_FAKE_HEX)
        assert result == REDACTED
        assert count == 1


class TestRedactDict:
    def test_sensitive_key_is_redacted(self):
        d = {"password": "mysecret123"}
        result, count = redact_dict(d)
        assert result["password"] == REDACTED
        assert count == 1

    def test_token_key_is_redacted(self):
        d = {"api_token": "some-value-here"}
        result, count = redact_dict(d)
        assert result["api_token"] == REDACTED
        assert count == 1

    def test_non_sensitive_key_preserved(self):
        d = {"name": "my-pod", "namespace": "default"}
        result, count = redact_dict(d)
        assert result["name"] == "my-pod"
        assert result["namespace"] == "default"
        assert count == 0

    def test_nested_dict_redacted(self):
        d = {"spec": {"password": "s3cr3t"}}
        result, count = redact_dict(d)
        assert result["spec"]["password"] == REDACTED
        assert count == 1

    def test_list_value_with_sensitive_key(self):
        d = {"credentials": "sensitive-data-here"}
        result, count = redact_dict(d)
        assert result["credentials"] == REDACTED
        assert count == 1


class TestRedactText:
    def test_password_in_text_redacted(self):
        text = 'password=' + 'mysecretvalue123'
        result, count = redact_text(text)
        assert "mysecretvalue123" not in result
        assert count > 0

    def test_non_sensitive_text_unchanged(self):
        text = "pod=my-pod namespace=default phase=Running"
        result, count = redact_text(text)
        assert result == text
        assert count == 0

    def test_multiline_text(self):
        text = "name=my-pod\npassword=secret123abc\nnamespace=default"
        result, count = redact_text(text)
        assert "secret123abc" not in result
        assert count >= 1


class TestRedactList:
    def test_list_of_dicts(self):
        items = [{"token": "abc123def456ghi"}, {"name": "pod"}]
        result, count = redact_list(items)
        assert result[0]["token"] == REDACTED
        assert result[1]["name"] == "pod"
        assert count == 1
