"""Read-only preflight before stamping an existing create_all installation.

This checks tables, column types/nullability, indexes and referential/unique
constraints against the frozen baseline migration. It never stamps or alters data.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import MetaData, inspect  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from config import settings  # noqa: E402


class CaptureOperations:
    def __init__(self):
        self.metadata = MetaData()
        self.indexes = []

    def create_table(self, name, *columns):
        from sqlalchemy import Table

        Table(name, self.metadata, *columns)

    def create_index(self, name, table, columns):
        self.indexes.append((name, table, columns))


def compare(connection):
    spec = importlib.util.spec_from_file_location(
        "baseline", Path(__file__).resolve().parent.parent / "migrations/versions/0001_baseline.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    capture = CaptureOperations()
    migration.op = capture
    migration.upgrade()
    inspector = inspect(connection)
    issues = []
    for name, table in capture.metadata.tables.items():
        if not inspector.has_table(name):
            issues.append(f"Missing table: {name}")
            continue
        actual = {column["name"]: column for column in inspector.get_columns(name)}
        if set(actual) != set(table.columns.keys()):
            issues.append(f"Column names differ: {name}")
            continue
        for column in table.columns:
            observed = actual[column.name]
            if (
                observed["type"]._type_affinity is not column.type._type_affinity
                or observed["nullable"] != column.nullable
                or getattr(observed["type"], "length", None) != getattr(column.type, "length", None)
                or getattr(observed["type"], "timezone", None) != getattr(column.type, "timezone", None)
            ):
                issues.append(f"Column definition differs: {name}.{column.name}")
        expected_pk = [column.name for column in table.primary_key.columns]
        if inspector.get_pk_constraint(name)["constrained_columns"] != expected_pk:
            issues.append(f"Primary key differs: {name}")
        uniques = {tuple(entry["column_names"]) for entry in inspector.get_unique_constraints(name)}
        for column in table.columns:
            if column.unique and (column.name,) not in uniques:
                issues.append(f"Missing uniqueness: {name}.{column.name}")
        foreign_keys = inspector.get_foreign_keys(name)
        for constraint in table.foreign_key_constraints:
            element = next(iter(constraint.elements))
            if not any(
                entry["constrained_columns"] == [element.parent.name]
                and entry["referred_table"] == element.column.table.name
                and entry["referred_columns"] == [element.column.name]
                and entry.get("options", {}).get("ondelete") == constraint.ondelete
                for entry in foreign_keys
            ):
                issues.append(f"Foreign key differs: {name}.{element.parent.name}")
    for index_name, table_name, columns in capture.indexes:
        if inspector.has_table(table_name) and not any(
            entry["column_names"] == columns for entry in inspector.get_indexes(table_name)
        ):
            issues.append(f"Missing baseline index: {index_name}")
    return issues


async def main():
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            issues = await connection.run_sync(compare)
        if issues:
            print("Baseline mismatch; do not stamp:")
            for issue in issues:
                print(f"- {issue}")
            raise SystemExit(1)
        print("Baseline schema matches. Review a backup/restore before manually stamping 0001_baseline.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
