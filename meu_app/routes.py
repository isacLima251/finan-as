from flask import render_template, request, jsonify, redirect, url_for
from sqlalchemy import func, or_
from datetime import datetime, timedelta, date
from meu_app import app, db
from meu_app.models import Pedido, Gasto

@app.route("/")
def dashboard():
    # LÓGICA DE PERÍODO ATUALIZADA PARA O RESUMO
    periodo_selecionado = request.args.get('periodo', 'mes_atual')
    hoje = date.today()
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')
    data_inicio, data_fim = None, None

    if periodo_selecionado == 'maximo':
        pass # Não define datas, pegando todo o histórico
    elif periodo_selecionado == 'personalizado' and data_inicio_str and data_fim_str:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
        data_fim = datetime.combine(datetime.strptime(data_fim_str, '%Y-%m-%d'), datetime.max.time())
    elif periodo_selecionado == 'hoje': data_inicio = datetime.combine(hoje, datetime.min.time()); data_fim = datetime.combine(hoje, datetime.max.time())
    elif periodo_selecionado == 'ontem': ontem = hoje - timedelta(days=1); data_inicio = datetime.combine(ontem, datetime.min.time()); data_fim = datetime.combine(ontem, datetime.max.time())
    elif periodo_selecionado == 'ultimos_7_dias': data_inicio = datetime.combine(hoje - timedelta(days=6), datetime.min.time()); data_fim = datetime.combine(hoje, datetime.max.time())
    elif periodo_selecionado == 'mes_passado': primeiro_dia_mes_atual = hoje.replace(day=1); ultimo_dia_mes_passado = primeiro_dia_mes_atual - timedelta(days=1); primeiro_dia_mes_passado = ultimo_dia_mes_passado.replace(day=1); data_inicio = datetime.combine(primeiro_dia_mes_passado, datetime.min.time()); data_fim = datetime.combine(ultimo_dia_mes_passado, datetime.max.time())
    else: # Padrão: 'mes_atual'
        primeiro_dia_mes_atual = hoje.replace(day=1); data_inicio = datetime.combine(primeiro_dia_mes_atual, datetime.min.time()); data_fim = datetime.combine(hoje, datetime.max.time())

    def apply_date_filter(query, column):
        if data_inicio and data_fim:
            return query.filter(column.between(data_inicio, data_fim))
        return query

    # CÁLCULOS DO RESUMO ATUALIZADOS
    total_pago = apply_date_filter(db.session.query(func.sum(Pedido.valor)), Pedido.data_pagamento).filter(Pedido.status == 'Pago').scalar() or 0.0
    total_gasto = apply_date_filter(db.session.query(func.sum(Gasto.valor)), Gasto.data).scalar() or 0.0
    quantidade_vendas = apply_date_filter(db.session.query(func.count(Pedido.id)), Pedido.data_pagamento).filter(Pedido.status == 'Pago').scalar() or 0
    total_agendado = apply_date_filter(db.session.query(func.sum(Pedido.valor)), Pedido.data_venda).filter(Pedido.status == 'Agendado').scalar() or 0.0
    total_frustrado = apply_date_filter(db.session.query(func.sum(Pedido.valor)), Pedido.data_venda).filter(Pedido.status == 'Frustrado').scalar() or 0.0
    
    total_a_receber = db.session.query(func.sum(Pedido.valor)).filter(Pedido.status == 'A Receber', Pedido.data_vencimento >= datetime.utcnow()).scalar() or 0.0
    total_atrasado = db.session.query(func.sum(Pedido.valor)).filter(Pedido.status == 'A Receber', Pedido.data_vencimento < datetime.utcnow()).scalar() or 0.0

    lucro = total_pago - total_gasto
    roas = total_pago / total_gasto if total_gasto > 0 else 0
    margem = (lucro / total_pago) * 100 if total_pago > 0 else 0

    resumo_dados = {
        'pagos': total_pago, 'gastos': total_gasto, 'lucro': lucro,
        'a_receber': total_a_receber, 'frustrados': total_frustrado, 'atrasados': total_atrasado,
        'agendado': total_agendado,
        'quantidade_vendas': quantidade_vendas, 'roas': roas, 'margem': margem,
        'projecao': total_pago + total_a_receber + total_agendado
    }

    dia_pagamento = func.date(Pedido.data_pagamento)
    faturamento_query = db.session.query(
        dia_pagamento.label('dia'),
        func.sum(Pedido.valor).label('total')
    ).filter(
        Pedido.status == 'Pago',
        Pedido.data_pagamento.isnot(None)
    )
    faturamento_query = apply_date_filter(faturamento_query, Pedido.data_pagamento)
    faturamento_por_dia = faturamento_query.group_by(dia_pagamento).order_by(dia_pagamento).all()

    grafico_labels = []
    grafico_data = []
    for dia, total in faturamento_por_dia:
        if isinstance(dia, datetime):
            dia_formatado = dia.strftime('%d/%m/%Y')
        elif isinstance(dia, date):
            dia_formatado = dia.strftime('%d/%m/%Y')
        else:
            try:
                dia_formatado = datetime.strptime(str(dia), '%Y-%m-%d').strftime('%d/%m/%Y')
            except ValueError:
                dia_formatado = str(dia)
        grafico_labels.append(dia_formatado)
        grafico_data.append(float(total or 0))

    dia_gasto = func.date(Gasto.data)
    gastos_query = db.session.query(
        dia_gasto.label('dia'),
        func.sum(Gasto.valor).label('total')
    )
    gastos_query = apply_date_filter(gastos_query, Gasto.data)
    gastos_por_dia = gastos_query.group_by(dia_gasto).order_by(dia_gasto).all()

    grafico_gastos_labels = []
    grafico_gastos_data = []
    for dia, total in gastos_por_dia:
        if isinstance(dia, datetime):
            dia_formatado = dia.strftime('%d/%m/%Y')
        elif isinstance(dia, date):
            dia_formatado = dia.strftime('%d/%m/%Y')
        else:
            try:
                dia_formatado = datetime.strptime(str(dia), '%Y-%m-%d').strftime('%d/%m/%Y')
            except ValueError:
                dia_formatado = str(dia)
        grafico_gastos_labels.append(dia_formatado)
        grafico_gastos_data.append(float(total or 0))

    pagamentos_query = db.session.query(
        Pedido.metodo_pagamento,
        func.count(Pedido.id)
    ).filter(
        Pedido.status == 'Pago',
        Pedido.data_pagamento.isnot(None)
    )
    pagamentos_query = apply_date_filter(pagamentos_query, Pedido.data_pagamento)
    pagamentos_por_metodo = pagamentos_query.group_by(Pedido.metodo_pagamento).all()

    grafico_pagamentos_labels = []
    grafico_pagamentos_data = []
    for metodo, quantidade in pagamentos_por_metodo:
        grafico_pagamentos_labels.append(metodo or 'Não informado')
        grafico_pagamentos_data.append(int(quantidade or 0))

    print("grafico_labels:", grafico_labels)
    print("grafico_data:", grafico_data)
    print("grafico_gastos_labels:", grafico_gastos_labels)
    print("grafico_gastos_data:", grafico_gastos_data)
    print("grafico_pagamentos_labels:", grafico_pagamentos_labels)
    print("grafico_pagamentos_data:", grafico_pagamentos_data)

    return render_template(
        "dashboard.html",
        resumo=resumo_dados,
        periodo_selecionado=periodo_selecionado,
        data_inicio=data_inicio_str,
        data_fim=data_fim_str,
        grafico_labels=grafico_labels,
        grafico_data=grafico_data,
        grafico_gastos_labels=grafico_gastos_labels,
        grafico_gastos_data=grafico_gastos_data,
        grafico_pagamentos_labels=grafico_pagamentos_labels,
        grafico_pagamentos_data=grafico_pagamentos_data
    )


@app.route("/pedidos")
def listar_pedidos():
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 15

    status_filtro = request.args.get('status')
    termo_busca = request.args.get('busca')
    query = Pedido.query

    if status_filtro:
        if status_filtro == 'Atrasado':
            query = query.filter(Pedido.status == 'A Receber', Pedido.data_vencimento < datetime.utcnow())
        else:
            query = query.filter(Pedido.status == status_filtro)

    if termo_busca:
        query = query.filter(or_(
            Pedido.cliente.ilike(f'%{termo_busca}%'),
            Pedido.telefone.ilike(f'%{termo_busca}%')
        ))

    pagination = query.order_by(Pedido.data_venda.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
    pedidos_da_pagina = pagination.items

    for pedido in pedidos_da_pagina:
        if pedido.status == 'A Receber' and pedido.data_vencimento and pedido.data_vencimento < datetime.utcnow():
            pedido.status = 'Atrasado'

    return render_template(
        "pedidos.html",
        pedidos=pedidos_da_pagina,
        pagination=pagination,
        status_filtro=status_filtro,
        termo_busca=termo_busca
    )

# --- Restante do arquivo (rotas de salvar, webhook, etc.) sem alterações ---
@app.route('/salvar_observacao/<int:pedido_id>', methods=['POST'])
def salvar_observacao(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    nova_observacao = request.form.get('observacao')
    pedido.observacao = nova_observacao
    db.session.commit()
    return redirect(url_for('listar_pedidos'))

@app.route("/webhooks/braip", methods=['POST'])
def webhook_braip():
    dados = request.get_json()
    if not dados: return jsonify({"status": "erro"}), 400
    trans_code = dados.get('codigo_transacao') 
    if not trans_code: return jsonify({"status": "erro", "mensagem": "Código da transação ausente"}), 400
    pedido_existente = Pedido.query.filter_by(braip_trans_code=trans_code).first()
    status_braip = dados.get('status_compra_descricao')
    metodo_pagamento_braip = dados.get('metodo_pagamento') or dados.get('forma_pagamento') or dados.get('forma_pagamento_desc')
    if pedido_existente:
        pedido = pedido_existente
        if status_braip == 'Entregue': pedido.status = 'A Receber'; pedido.data_vencimento = datetime.utcnow() + timedelta(days=30)
        elif status_braip == 'Pagamento Confirmado': pedido.status = 'Pago'; pedido.data_pagamento = datetime.utcnow()
        elif status_braip in ['Estornado', 'Recusado', 'Cancelado']: pedido.status = 'Frustrado'
        if metodo_pagamento_braip:
            pedido.metodo_pagamento = metodo_pagamento_braip
    else:
        if status_braip != 'Aprovada': return jsonify({"status": "ok"}), 200
        pedido = Pedido(
            braip_trans_code=trans_code,
            cliente=dados.get('nome_cliente'),
            telefone=dados.get('cel_cliente'),
            valor=float(dados.get('valor_total')),
            status='Agendado',
            metodo_pagamento=metodo_pagamento_braip
        )
        db.session.add(pedido)
    db.session.commit()
    return jsonify({"status": "sucesso"}), 200

@app.route('/despesas')
def listar_despesas():
    gastos = Gasto.query.order_by(Gasto.data.desc()).all()
    return render_template('despesas.html', gastos=gastos)


@app.route('/adicionar_gasto', methods=['POST'])
def adicionar_gasto():
    valor_gasto = request.form.get('valor_gasto')
    categoria = request.form.get('categoria')
    if valor_gasto:
        try:
            valor_normalizado = float(str(valor_gasto).replace(',', '.'))
        except ValueError:
            return redirect(url_for('listar_despesas'))

        novo_gasto = Gasto(valor=valor_normalizado, categoria=categoria)
        db.session.add(novo_gasto)
        db.session.commit()
    return redirect(url_for('listar_despesas'))

@app.route('/atualizar_status/<int:pedido_id>', methods=['POST'])
def atualizar_status(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    novo_status = request.json.get('status')
    if novo_status not in ['Pago', 'Frustrado', 'Atrasado']: return jsonify({'status': 'erro'}), 400
    pedido.status = novo_status
    if novo_status == 'Pago': pedido.data_pagamento = datetime.utcnow()
    else: pedido.data_pagamento = None
    db.session.commit()
    return jsonify({'status': 'sucesso'})

@app.route('/criar_pedidos_massa')
def criar_pedidos_massa():
    for i in range(30):
        codigo_unico = f"MASSA_{i}_{datetime.utcnow().timestamp()}"
        pedido_teste = Pedido(braip_trans_code=codigo_unico, cliente=f'Cliente de Massa {i+1}', telefone='(11) 00000-0000', valor=10.00 + i, status='A Receber', data_vencimento=datetime.utcnow() + timedelta(days=i+1))
        db.session.add(pedido_teste)
    db.session.commit()
    return "30 pedidos de teste em massa criados com sucesso! <a href='/'>Voltar para o Painel</a>"

@app.route('/criar_pedido_antigo')
def criar_pedido_antigo():
    pedido_teste = Pedido.query.filter_by(braip_trans_code='TESTE_VENCIDO').first()
    if not pedido_teste:
        pedido_antigo = Pedido(braip_trans_code='TESTE_VENCIDO', cliente='Cliente Vencido de Teste', telefone='(99) 99999-9999', valor=50.00, status='A Receber', data_vencimento = datetime.utcnow() - timedelta(days=5))
        db.session.add(pedido_antigo); db.session.commit()
        return "Pedido de teste vencido criado com sucesso! <a href='/'>Voltar para o Painel</a>"
    return "Pedido de teste vencido já existe. <a href='/'>Voltar para o Painel</a>"
