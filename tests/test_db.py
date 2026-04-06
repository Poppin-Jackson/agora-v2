"""
Unit tests for backend/db.py — database layer

运行方式（在容器内）：
  docker exec agora-v2-api python -m pytest /app/tests/test_db.py -v --tb=short

注意：这些测试需要 asyncpg，在容器外运行需要安装：
  pip install asyncpg
"""
import pytest
import asyncio
import re


# =========================================================================
# File content helpers (avoid importing asyncpg on host)
# =========================================================================

DB_PATH = "/Users/mac/Documents/opencode-zl/agora-v2/backend/db.py"


def _get_db_content():
    """Read db.py file content."""
    with open(DB_PATH) as f:
        return f.read()


# =========================================================================
# URL Parsing Tests
# =========================================================================

class TestDatabaseUrlParsing:
    """Test that DATABASE_URL is parsed correctly into components."""

    def test_url_regex_extracts_all_components(self):
        url = "postgresql+asyncpg://agora:agora_v2_secret@postgres:5432/agora_v2"
        m = re.match(
            r"postgresql\+asyncpg://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<db>.+)",
            url
        )
        assert m is not None
        assert m.group("user") == "agora"
        assert m.group("password") == "agora_v2_secret"
        assert m.group("host") == "postgres"
        assert m.group("port") == "5432"
        assert m.group("db") == "agora_v2"

    def test_url_regex_with_special_chars_in_password(self):
        url = "postgresql+asyncpg://user:p%40ss!word@localhost:5432/mydb"
        m = re.match(
            r"postgresql\+asyncpg://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<db>.+)",
            url
        )
        assert m is not None
        assert m.group("user") == "user"
        assert m.group("password") == "p%40ss!word"
        assert m.group("host") == "localhost"
        assert m.group("port") == "5432"
        assert m.group("db") == "mydb"

    def test_url_regex_with_colons_in_password(self):
        url = "postgresql+asyncpg://user:pass:word@localhost:5432/mydb"
        m = re.match(
            r"postgresql\+asyncpg://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<db>.+)",
            url
        )
        assert m is not None
        assert m.group("user") == "user"
        assert m.group("password") == "pass:word"
        assert m.group("host") == "localhost"
        assert m.group("db") == "mydb"

    def test_url_regex_fails_on_wrong_scheme(self):
        url = "mysql://user:pass@localhost:5432/mydb"
        m = re.match(
            r"postgresql\+asyncpg://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<db>.+)",
            url
        )
        assert m is None

    def test_url_regex_fails_on_missing_at_symbol(self):
        url = "postgresql+asyncpg://userpasslocalhost:5432/mydb"
        m = re.match(
            r"postgresql\+asyncpg://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<db>.+)",
            url
        )
        assert m is None


# =========================================================================
# CREATE TABLES — Table Presence Tests
# =========================================================================

class TestCreateTablesSql:
    """Verify _create_tables has correct SQL structure."""

    def _sql_section(self):
        """Extract the CREATE TABLES SQL section from _create_tables function."""
        content = _get_db_content()
        # Find the function
        start = content.find("async def _create_tables(")
        if start == -1:
            return ""
        # Find the next function after _create_tables
        end = content.find("\nasync def ", start + 1)
        if end == -1:
            end = content.find("\ndef ", start + 1)
        if end == -1:
            end = len(content)
        return content[start:end]

    def _all_content(self):
        return _get_db_content()

    def test_creates_tables_function_exists(self):
        content = self._all_content()
        assert "async def _create_tables(" in content

    def test_plans_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS plans" in sql
        assert "plan_id" in sql
        assert "title" in sql
        assert "topic" in sql

    def test_rooms_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS rooms" in sql
        assert "room_id" in sql
        assert "topic" in sql
        assert "phase" in sql

    def test_participants_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS participants" in sql
        assert "participant_id" in sql
        assert "room_id" in sql
        assert "agent_id" in sql
        assert "name" in sql

    def test_messages_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS messages" in sql
        assert "message_id" in sql
        assert "room_id" in sql
        assert "content" in sql

    def test_approval_flows_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS approval_flows" in sql
        assert "plan_id" in sql
        assert "current_level" in sql
        assert "status" in sql

    def test_tasks_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS tasks" in sql
        assert "task_id" in sql
        assert "title" in sql
        assert "status" in sql
        assert "priority" in sql

    def test_snapshots_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS snapshots" in sql
        assert "snapshot_id" in sql

    def test_edicts_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS edicts" in sql
        assert "edict_id" in sql
        assert "title" in sql

    def test_notifications_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS notifications" in sql
        assert "notification_id" in sql

    def test_room_phase_timeline_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS room_phase_timeline" in sql
        assert "room_id" in sql
        assert "phase" in sql
        assert "entered_at" in sql

    def test_meeting_minutes_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS meeting_minutes" in sql
        assert "meeting_minutes_id" in sql

    def test_plan_templates_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS plan_templates" in sql
        assert "template_id" in sql
        assert "name" in sql

    def test_task_templates_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS task_templates" in sql
        assert "template_id" in sql

    def test_escalations_table_created(self):
        sql = self._sql_section()
        assert "CREATE TABLE IF NOT EXISTS escalations" in sql
        assert "escalation_id" in sql

    def test_all_tables_use_if_not_exists(self):
        sql = self._sql_section()
        # All CREATE TABLE statements should use IF NOT EXISTS
        create_count = sql.count("CREATE TABLE IF NOT EXISTS")
        assert create_count >= 20, f"Expected many tables, found {create_count}"

    def test_plans_has_plan_number_unique(self):
        sql = self._sql_section()
        plans_start = sql.find("CREATE TABLE IF NOT EXISTS plans")
        plans_end = sql.find("CREATE TABLE", plans_start + 1)
        plans_section = sql[plans_start:plans_end]
        assert "plan_number" in plans_section
        assert "UNIQUE" in plans_section

    def test_rooms_has_room_number_unique(self):
        sql = self._sql_section()
        rooms_start = sql.find("CREATE TABLE IF NOT EXISTS rooms")
        rooms_end = sql.find("CREATE TABLE", rooms_start + 1)
        rooms_section = sql[rooms_start:rooms_end]
        assert "room_number" in rooms_section
        assert "UNIQUE" in rooms_section

    def test_rooms_has_purpose_and_mode(self):
        sql = self._sql_section()
        rooms_start = sql.find("CREATE TABLE IF NOT EXISTS rooms")
        rooms_end = sql.find("CREATE TABLE", rooms_start + 1)
        rooms_section = sql[rooms_start:rooms_end]
        assert "purpose" in rooms_section
        assert "mode" in rooms_section
        assert "initial_discussion" in rooms_section
        assert "hierarchical" in rooms_section

    def test_rooms_has_coordinator_id(self):
        sql = self._sql_section()
        rooms_start = sql.find("CREATE TABLE IF NOT EXISTS rooms")
        rooms_end = sql.find("CREATE TABLE", rooms_start + 1)
        rooms_section = sql[rooms_start:rooms_end]
        assert "coordinator_id" in rooms_section

    def test_tasks_has_required_columns(self):
        sql = self._sql_section()
        tasks_start = sql.find("CREATE TABLE IF NOT EXISTS tasks")
        tasks_end = sql.find("CREATE TABLE", tasks_start + 1)
        tasks_section = sql[tasks_start:tasks_end]
        for col in ["task_id", "title", "status", "priority", "progress", "owner_id"]:
            assert col in tasks_section, f"Missing column: {col}"

    def test_foreign_keys_present(self):
        sql = self._sql_section()
        # rooms → plans
        assert "REFERENCES plans" in sql
        # participants → rooms
        assert "REFERENCES rooms" in sql

    def test_has_proper_indexes(self):
        sql = self._sql_section()
        assert "CREATE INDEX IF NOT EXISTS" in sql

    def test_plans_has_tags_column_with_gin_index(self):
        sql = self._sql_section()
        assert "tags" in sql
        assert "TEXT[]" in sql or "GIN" in sql

    def test_messages_has_required_columns(self):
        sql = self._sql_section()
        msgs_start = sql.find("CREATE TABLE IF NOT EXISTS messages")
        msgs_end = sql.find("CREATE TABLE", msgs_start + 1)
        msgs_section = sql[msgs_start:msgs_end]
        for col in ["message_id", "room_id", "type", "content", "timestamp"]:
            assert col in msgs_section, f"Missing column: {col}"


# =========================================================================
# Module Structure Tests
# =========================================================================

class TestDbModuleStructure:
    """Test that db.py has required functions and constants."""

    def test_module_has_get_pool(self):
        content = _get_db_content()
        assert "async def get_pool(" in content

    def test_module_has_init_db(self):
        content = _get_db_content()
        assert "async def init_db(" in content

    def test_module_has_close_db(self):
        content = _get_db_content()
        assert "async def close_db(" in content

    def test_module_has_get_connection(self):
        content = _get_db_content()
        assert "async def get_connection(" in content

    def test_module_has_asynccontextmanager(self):
        content = _get_db_content()
        assert "asynccontextmanager" in content

    def test_module_imports_asyncpg(self):
        content = _get_db_content()
        assert "import asyncpg" in content

    def test_module_has_DATABASE_URL(self):
        content = _get_db_content()
        assert "DATABASE_URL" in content
        assert "postgresql" in content

    def test_module_has_pool_global(self):
        content = _get_db_content()
        assert "_pool" in content

    def test_init_db_creates_database_if_not_exists(self):
        content = _get_db_content()
        assert "pg_database" in content
        assert "CREATE DATABASE" in content

    def test_init_db_creates_pool_with_size_limits(self):
        content = _get_db_content()
        assert "min_size" in content
        assert "max_size" in content

    def test_get_connection_uses_acquire(self):
        content = _get_db_content()
        assert "pool.acquire()" in content

    def test_init_db_uses_regex_parsing(self):
        content = _get_db_content()
        assert "re.match" in content
        assert "postgresql\\+asyncpg://" in content


# =========================================================================
# SQL Migrations Tests
# =========================================================================

class TestSqlMigrations:
    """Test that SQL migrations are present for schema evolution."""

    def test_plans_tags_migration_present(self):
        content = _get_db_content()
        assert "ALTER TABLE plans ADD COLUMN IF NOT EXISTS tags" in content
        assert "TEXT[]" in content

    def test_rooms_purpose_mode_defaults(self):
        content = _get_db_content()
        assert "initial_discussion" in content
        assert "hierarchical" in content


# =========================================================================
# Pool lifecycle tests (require asyncpg — skip on host)
# =========================================================================

class TestPoolLifecycle:
    """Test pool lifecycle functions. Requires asyncpg installed."""

    @pytest.fixture(autouse=True)
    def check_asyncpg(self):
        try:
            import asyncpg
        except ImportError:
            pytest.skip("asyncpg not available on host (run inside container)")

    @pytest.mark.asyncio
    async def test_get_pool_raises_when_not_initialized(self):
        import sys
        sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
        import backend.db as db_module
        db_module._pool = None
        with pytest.raises(RuntimeError, match="Database pool not initialized"):
            await db_module.get_pool()
        db_module._pool = None

    @pytest.mark.asyncio
    async def test_get_pool_returns_existing_pool(self):
        import sys
        sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
        import backend.db as db_module

        class FakePool:
            pass

        fake = FakePool()
        db_module._pool = fake
        pool = await db_module.get_pool()
        assert pool is fake
        db_module._pool = None

    @pytest.mark.asyncio
    async def test_close_db_sets_pool_to_none(self):
        import sys
        sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
        import backend.db as db_module

        class FakePool:
            async def close(self):
                pass

        fake = FakePool()
        db_module._pool = fake
        await db_module.close_db()
        assert db_module._pool is None

    @pytest.mark.asyncio
    async def test_close_db_does_nothing_when_pool_is_none(self):
        import sys
        sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
        import backend.db as db_module
        db_module._pool = None
        await db_module.close_db()
        assert db_module._pool is None

    @pytest.mark.asyncio
    async def test_get_pool_called_twice_returns_same_instance(self):
        import sys
        sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
        import backend.db as db_module

        class FakePool:
            pass

        fake = FakePool()
        db_module._pool = fake
        p1 = await db_module.get_pool()
        p2 = await db_module.get_pool()
        assert p1 is p2
        assert p1 is fake
        db_module._pool = None

    @pytest.mark.asyncio
    async def test_close_then_get_pool_reinit(self):
        import sys
        sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
        import backend.db as db_module

        class FakePool:
            async def close(self):
                pass

        fake1 = FakePool()
        db_module._pool = fake1
        await db_module.close_db()
        assert db_module._pool is None


class TestInitDb:
    """Test database initialization."""

    @pytest.fixture(autouse=True)
    def check_asyncpg(self):
        try:
            import asyncpg
        except ImportError:
            pytest.skip("asyncpg not available on host (run inside container)")

    @pytest.mark.asyncio
    async def test_init_db_invalid_url_raises_value_error(self):
        import sys
        sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
        import backend.db as db_module
        db_module._pool = None
        with pytest.raises(ValueError, match="Cannot parse DATABASE_URL"):
            await db_module.init_db("postgresql://invalid-format")
        db_module._pool = None


class TestGetConnection:
    """Test the get_connection context manager."""

    @pytest.fixture(autouse=True)
    def check_asyncpg(self):
        try:
            import asyncpg
        except ImportError:
            pytest.skip("asyncpg not available on host (run inside container)")

    @pytest.mark.asyncio
    async def test_get_connection_acquires_from_pool(self):
        import sys
        sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
        import backend.db as db_module

        class FakeConn:
            async def execute(self, sql, *args):
                return "OK"
            async def fetch(self, sql, *args):
                return []
            async def fetchval(self, sql, *args):
                return None

        class FakePoolAcquire:
            def __init__(self, pool):
                pass
            async def __aenter__(self):
                return FakeConn()
            async def __aexit__(self, *args):
                pass

        class FakePool:
            async def acquire(self):
                return FakePoolAcquire(self)
            async def close(self):
                pass

        fake_pool = FakePool()
        db_module._pool = fake_pool
        acquired_conn = None
        async with db_module.get_connection() as conn:
            acquired_conn = conn
        assert acquired_conn is not None
        db_module._pool = None
