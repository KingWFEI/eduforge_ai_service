"""add chinese column comments

Revision ID: f2a7c9d8e1b4
Revises: d1e2f3a4b5c6
Create Date: 2026-06-06 14:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models  # noqa: F401
from app.db.base import Base
from app.models.column_comments import get_column_comments


revision: str = "f2a7c9d8e1b4"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _reflected_columns() -> dict[str, dict[str, dict]]:
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())
    columns: dict[str, dict[str, dict]] = {}
    for table_name in get_column_comments(Base.metadata):
        if table_name not in table_names:
            continue
        columns[table_name] = {
            column["name"]: column
            for column in inspector.get_columns(table_name)
        }
    return columns


def _quote_identifier(identifier: str) -> str:
    return f"`{identifier.replace('`', '``')}`"


def _quote_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _mysql_column_rows() -> dict[str, dict[str, dict]]:
    bind = op.get_bind()
    rows_by_table: dict[str, dict[str, dict]] = {}
    for table_name in get_column_comments(Base.metadata):
        rows = bind.execute(
            sa.text(
                """
                SELECT
                    TABLE_NAME,
                    COLUMN_NAME,
                    COLUMN_TYPE,
                    DATA_TYPE,
                    IS_NULLABLE,
                    COLUMN_DEFAULT,
                    EXTRA,
                    CHARACTER_SET_NAME,
                    COLLATION_NAME,
                    COLUMN_COMMENT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table_name
                """
            ),
            {"table_name": table_name},
        ).mappings()
        table_rows = {row["COLUMN_NAME"]: dict(row) for row in rows}
        if table_rows:
            rows_by_table[table_name] = table_rows
    return rows_by_table


def _mysql_default_sql(row: dict) -> str:
    default = row["COLUMN_DEFAULT"]
    data_type = (row["DATA_TYPE"] or "").lower()
    extra = (row["EXTRA"] or "").lower()
    if default is None:
        return ""

    default_text = str(default)
    normalized = default_text.strip().strip("()").lower()
    if normalized in {"current_timestamp", "current_timestamp()", "now", "now()"}:
        return " DEFAULT CURRENT_TIMESTAMP"
    if "default_generated" in extra and not (
        default_text.startswith("'") or default_text.startswith('"')
    ):
        return f" DEFAULT {default_text}"
    if data_type in {
        "tinyint",
        "smallint",
        "mediumint",
        "int",
        "integer",
        "bigint",
        "decimal",
        "float",
        "double",
        "bit",
    }:
        return f" DEFAULT {default_text}"
    return f" DEFAULT {_quote_string(default_text)}"


def _mysql_extra_sql(row: dict) -> str:
    extra = row["EXTRA"] or ""
    parts: list[str] = []
    if "auto_increment" in extra.lower():
        parts.append("AUTO_INCREMENT")
    if "on update" in extra.lower():
        parts.append("ON UPDATE CURRENT_TIMESTAMP")
    return f" {' '.join(parts)}" if parts else ""


def _mysql_column_definition(row: dict, comment: str | None) -> str:
    definition = row["COLUMN_TYPE"]
    if row["CHARACTER_SET_NAME"]:
        definition += f" CHARACTER SET {row['CHARACTER_SET_NAME']}"
    if row["COLLATION_NAME"]:
        definition += f" COLLATE {row['COLLATION_NAME']}"
    definition += " NULL" if row["IS_NULLABLE"] == "YES" else " NOT NULL"
    definition += _mysql_default_sql(row)
    definition += _mysql_extra_sql(row)
    definition += f" COMMENT {_quote_string(comment or '')}"
    return definition


def _alter_mysql_comments(clear: bool = False) -> None:
    bind = op.get_bind()
    comments = get_column_comments(Base.metadata)
    rows_by_table = _mysql_column_rows()
    for table_name, column_comments in comments.items():
        table_rows = rows_by_table.get(table_name, {})
        for column_name, comment in column_comments.items():
            row = table_rows.get(column_name)
            if row is None:
                continue
            definition = _mysql_column_definition(row, None if clear else comment)
            bind.execute(
                sa.text(
                    "ALTER TABLE "
                    f"{_quote_identifier(table_name)} MODIFY COLUMN "
                    f"{_quote_identifier(column_name)} {definition}"
                )
            )


def _reflected_foreign_keys() -> list[dict]:
    inspector = sa.inspect(op.get_bind())
    foreign_keys: list[dict] = []
    for table_name in inspector.get_table_names():
        for foreign_key in inspector.get_foreign_keys(table_name):
            if not foreign_key.get("name"):
                continue
            foreign_keys.append(
                {
                    "name": foreign_key["name"],
                    "source_table": table_name,
                    "referent_table": foreign_key["referred_table"],
                    "local_cols": foreign_key["constrained_columns"],
                    "remote_cols": foreign_key["referred_columns"],
                    "options": foreign_key.get("options") or {},
                }
            )
    return foreign_keys


def _drop_foreign_keys(foreign_keys: list[dict]) -> None:
    for foreign_key in foreign_keys:
        op.drop_constraint(
            foreign_key["name"],
            foreign_key["source_table"],
            type_="foreignkey",
        )


def _restore_foreign_keys(foreign_keys: list[dict]) -> None:
    for foreign_key in foreign_keys:
        options = foreign_key["options"]
        op.create_foreign_key(
            foreign_key["name"],
            foreign_key["source_table"],
            foreign_key["referent_table"],
            foreign_key["local_cols"],
            foreign_key["remote_cols"],
            ondelete=options.get("ondelete"),
            onupdate=options.get("onupdate"),
        )


def _alter_comments(clear: bool = False) -> None:
    if op.get_bind().dialect.name == "mysql":
        _alter_mysql_comments(clear=clear)
        return

    comments = get_column_comments(Base.metadata)
    reflected = _reflected_columns()
    for table_name, column_comments in comments.items():
        table_columns = reflected.get(table_name, {})
        for column_name, comment in column_comments.items():
            column_info = table_columns.get(column_name)
            if column_info is None:
                continue
            op.alter_column(
                table_name,
                column_name,
                existing_type=column_info["type"],
                existing_nullable=column_info["nullable"],
                existing_server_default=column_info.get("default"),
                existing_comment=column_info.get("comment"),
                comment=None if clear else comment,
            )


def upgrade() -> None:
    foreign_keys = _reflected_foreign_keys()
    _drop_foreign_keys(foreign_keys)
    try:
        _alter_comments(clear=False)
    finally:
        _restore_foreign_keys(foreign_keys)


def downgrade() -> None:
    foreign_keys = _reflected_foreign_keys()
    _drop_foreign_keys(foreign_keys)
    try:
        _alter_comments(clear=True)
    finally:
        _restore_foreign_keys(foreign_keys)
