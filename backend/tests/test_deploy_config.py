"""Tests for the bits of configuration that only matter once this is deployed.

Both are cheap to get wrong and expensive to debug from a deploy log: a CORS
allowlist that quietly drops the frontend, and a database URL scheme the driver
refuses to load.
"""

import pytest

from database import normalise_database_url
from main import LOCAL_ORIGINS, allowed_origins


class TestAllowedOrigins:
    def test_local_dev_origins_are_always_present(self, monkeypatch):
        monkeypatch.delenv("FRONTEND_URL", raising=False)
        origins = allowed_origins()
        assert "http://localhost:5173" in origins
        assert "http://127.0.0.1:5173" in origins

    def test_unset_frontend_url_adds_nothing(self, monkeypatch):
        monkeypatch.delenv("FRONTEND_URL", raising=False)
        assert allowed_origins() == LOCAL_ORIGINS

    def test_empty_frontend_url_does_not_add_a_blank_origin(self, monkeypatch):
        """A blank entry would be a falsy origin the middleware could mishandle."""
        monkeypatch.setenv("FRONTEND_URL", "")
        assert "" not in allowed_origins()
        assert allowed_origins() == LOCAL_ORIGINS

    def test_frontend_url_is_added(self, monkeypatch):
        monkeypatch.setenv("FRONTEND_URL", "https://app.up.railway.app")
        assert "https://app.up.railway.app" in allowed_origins()

    def test_several_origins_can_be_comma_separated(self, monkeypatch):
        monkeypatch.setenv(
            "FRONTEND_URL", "https://one.example.com,https://two.example.com"
        )
        origins = allowed_origins()
        assert "https://one.example.com" in origins
        assert "https://two.example.com" in origins

    def test_whitespace_around_entries_is_ignored(self, monkeypatch):
        monkeypatch.setenv("FRONTEND_URL", " https://one.example.com , ")
        assert "https://one.example.com" in allowed_origins()
        assert " https://one.example.com " not in allowed_origins()

    def test_trailing_slash_is_stripped(self, monkeypatch):
        """A browser never sends a trailing slash on Origin, so one in the config
        would silently fail to match."""
        monkeypatch.setenv("FRONTEND_URL", "https://app.up.railway.app/")
        assert "https://app.up.railway.app" in allowed_origins()

    def test_setting_frontend_url_does_not_evict_localhost(self, monkeypatch):
        monkeypatch.setenv("FRONTEND_URL", "https://app.up.railway.app")
        origins = allowed_origins()
        assert "http://localhost:5173" in origins

    def test_wildcard_is_not_used(self, monkeypatch):
        monkeypatch.setenv("FRONTEND_URL", "https://app.up.railway.app")
        assert "*" not in allowed_origins()


class TestDatabaseUrlNormalisation:
    def test_legacy_postgres_scheme_is_upgraded(self):
        """SQLAlchemy 2 has no `postgres` dialect and raises NoSuchModuleError."""
        assert normalise_database_url("postgres://u:p@h:5432/db") == (
            "postgresql://u:p@h:5432/db"
        )

    def test_modern_scheme_is_left_alone(self):
        url = "postgresql://u:p@h:5432/db"
        assert normalise_database_url(url) == url

    def test_credentials_and_query_string_survive(self):
        got = normalise_database_url(
            "postgres://user:p%40ss@host.internal:5432/railway?sslmode=require"
        )
        assert got == (
            "postgresql://user:p%40ss@host.internal:5432/railway?sslmode=require"
        )

    def test_a_driver_qualified_scheme_is_untouched(self):
        url = "postgresql+psycopg2://u:p@h/db"
        assert normalise_database_url(url) == url

    @pytest.mark.parametrize("url", ["postgresql://h/db", "sqlite:///x.db"])
    def test_other_schemes_pass_through(self, url):
        assert normalise_database_url(url) == url

    def test_the_normalised_url_actually_loads_a_dialect(self):
        """The point of the rewrite: the result must be usable by create_engine."""
        from sqlalchemy import create_engine

        create_engine(normalise_database_url("postgres://u:p@h:5432/db"))
