from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, '..', 'pedidos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

from meu_app import models  # noqa: E402,F401
from meu_app import routes  # noqa: E402,F401

with app.app_context():
    db.create_all()
