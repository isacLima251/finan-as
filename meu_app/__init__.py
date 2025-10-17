from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os

base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, '..', 'pedidos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


def ensure_sqlite_column(table_name: str, column_name: str, column_definition: str) -> None:
    """Ensure an SQLite column exists before running the application.

    SQLite does not support `ALTER TABLE ...` operations that are automatically
    triggered by SQLAlchemy's ``create_all`` when a column is added to an
    existing model. When the schema changes we need to manually add the new
    column so that queries referencing it do not fail.
    """

    with db.engine.connect() as connection:
        existing_columns = {
            row[1] for row in connection.execute(text(f"PRAGMA table_info({table_name})"))
        }

        if column_name not in existing_columns:
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"))


from meu_app import models  # noqa: E402,F401
from meu_app import routes  # noqa: E402,F401

with app.app_context():
    db.create_all()
    ensure_sqlite_column("pedido", "metodo_pagamento", "VARCHAR(50)")
