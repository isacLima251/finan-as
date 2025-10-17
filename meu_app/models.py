from datetime import datetime

from meu_app import db


class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    braip_trans_code = db.Column(db.String(50), unique=True, nullable=False)
    data_venda = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cliente = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Agendado')
    data_vencimento = db.Column(db.DateTime, nullable=True)
    data_pagamento = db.Column(db.DateTime, nullable=True)
    observacao = db.Column(db.String(300), nullable=True)
    metodo_pagamento = db.Column(db.String(50), nullable=True)


class Gasto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    categoria = db.Column(db.String(80), nullable=True)
