from flask import render_template, request, jsonify, redirect, url_for
from sqlalchemy import func, or_
from datetime import datetime, timedelta, date
from meu_app import app, db
from meu_app.models import Pedido, Gasto
import traceback  # Para depuração


@app.route("/")
def dashboard():
    try:  # Adicionado Try/Except para capturar erros inesperados
        page = request.args.get('page', 1, type=int)
        PER_PAGE = 15

        # Lógica de Filtros da Tabela (não afeta os KPIs do dashboard)
        status_filtro_tabela = request.args.get('status')
        termo_busca_tabela = request.args.get('busca')
        query_pedidos_tabela = Pedido.query
        if status_filtro_tabela:
            if status_filtro_tabela == 'Atrasado':
                query_pedidos_tabela = query_pedidos_tabela.filter(Pedido.status == 'A Receber', Pedido.data_vencimento < datetime.utcnow())
            else:
                query_pedidos_tabela = query_pedidos_tabela.filter(Pedido.status == status_filtro_tabela)
        if termo_busca_tabela:
            query_pedidos_tabela = query_pedidos_tabela.filter(or_(Pedido.cliente.ilike(f'%{termo_busca_tabela}%'), Pedido.telefone.ilike(f'%{termo_busca_tabela}%')))

        pagination = query_pedidos_tabela.order_by(Pedido.data_venda.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
        pedidos_da_pagina = pagination.items

        for pedido in pedidos_da_pagina:
            if pedido.status == 'A Receber' and pedido.data_vencimento and pedido.data_vencimento < datetime.utcnow():
                pedido.original_status = pedido.status  # Guarda o status original se precisar
                pedido.status = 'Atrasado'

        # LÓGICA DE PERÍODO PARA OS KPIs DO RESUMO - PADRÃO 'HOJE'
        periodo_selecionado = request.args.get('periodo', 'hoje')
        hoje = date.today()
        data_inicio_str = request.args.get('data_inicio')
        data_fim_str = request.args.get('data_fim')
        data_inicio, data_fim = None, None
        titulo_periodo = "Período Total"

        if periodo_selecionado == 'maximo':
            pass
        elif periodo_selecionado == 'personalizado' and data_inicio_str and data_fim_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
                data_fim = datetime.combine(datetime.strptime(data_fim_str, '%Y-%m-%d'), datetime.max.time())
                titulo_periodo = f"{data_inicio.strftime('%d/%m')} - {data_fim.strftime('%d/%m')}"
            except ValueError:
                periodo_selecionado = 'hoje'
                data_inicio = datetime.combine(hoje, datetime.min.time())
                data_fim = datetime.combine(hoje, datetime.max.time())
                titulo_periodo = "Hoje"
        elif periodo_selecionado == 'hoje':
            data_inicio = datetime.combine(hoje, datetime.min.time())
            data_fim = datetime.combine(hoje, datetime.max.time())
            titulo_periodo = "Hoje"
        elif periodo_selecionado == 'ontem':
            ontem = hoje - timedelta(days=1)
            data_inicio = datetime.combine(ontem, datetime.min.time())
            data_fim = datetime.combine(ontem, datetime.max.time())
            titulo_periodo = "Ontem"
        elif periodo_selecionado == 'ultimos_7_dias':
            data_inicio = datetime.combine(hoje - timedelta(days=6), datetime.min.time())
            data_fim = datetime.combine(hoje, datetime.max.time())
            titulo_periodo = "Últimos 7 dias"
        elif periodo_selecionado == 'mes_atual':
            primeiro_dia_mes_atual = hoje.replace(day=1)
            data_inicio = datetime.combine(primeiro_dia_mes_atual, datetime.min.time())
            data_fim = datetime.combine(hoje, datetime.max.time())
            titulo_periodo = "Este Mês"
        elif periodo_selecionado == 'mes_passado':
            primeiro_dia_mes_atual = hoje.replace(day=1)
            ultimo_dia_mes_passado = primeiro_dia_mes_atual - timedelta(days=1)
            primeiro_dia_mes_passado = ultimo_dia_mes_passado.replace(day=1)
            data_inicio = datetime.combine(primeiro_dia_mes_passado, datetime.min.time())
            data_fim = datetime.combine(ultimo_dia_mes_passado, datetime.max.time())
            titulo_periodo = "Mês Passado"
        else:
            periodo_selecionado = 'hoje'
            data_inicio = datetime.combine(hoje, datetime.min.time())
            data_fim = datetime.combine(hoje, datetime.max.time())
            titulo_periodo = "Hoje"

        # Função auxiliar para aplicar filtro de data
        def apply_date_filter(query, column):
            if data_inicio and data_fim:
                return query.filter(column.between(data_inicio, data_fim))
            return query

        # =================================================================
        # CÁLCULOS DOS KPIS - LÓGICA REVISADA E COM PRINTS
        # =================================================================
        # KPI QUE NÃO DEPENDE DO PERÍODO
        total_agendado_global = db.session.query(func.sum(Pedido.valor)).filter(Pedido.status == 'Agendado').scalar() or 0.0
        print(f"Agendado (Global): {total_agendado_global}")  # DEBUG PRINT

        # KPIs QUE DEPENDEM DO PERÍODO
        total_pago_periodo = apply_date_filter(db.session.query(func.sum(Pedido.valor)), Pedido.data_pagamento).filter(Pedido.status == 'Pago').scalar() or 0.0
        print(f"Pago (Periodo: {titulo_periodo}): {total_pago_periodo}")  # DEBUG PRINT

        total_frustrado_periodo = apply_date_filter(db.session.query(func.sum(Pedido.valor)), Pedido.data_venda).filter(Pedido.status == 'Frustrado').scalar() or 0.0
        print(f"Frustrado (Periodo: {titulo_periodo}): {total_frustrado_periodo}")  # DEBUG PRINT

        total_gasto_periodo = apply_date_filter(db.session.query(func.sum(Gasto.valor)), Gasto.data).scalar() or 0.0
        print(f"Gasto (Periodo: {titulo_periodo}): {total_gasto_periodo}")  # DEBUG PRINT

        quantidade_vendas_periodo = apply_date_filter(db.session.query(func.count(Pedido.id)), Pedido.data_pagamento).filter(Pedido.status == 'Pago').scalar() or 0
        print(f"Qtd Vendas (Periodo: {titulo_periodo}): {quantidade_vendas_periodo}")  # DEBUG PRINT

        # A RECEBER E ATRASADOS DO PERÍODO (usando data_venda como referência de origem)
        total_a_receber_periodo = apply_date_filter(db.session.query(func.sum(Pedido.valor)), Pedido.data_venda).filter(Pedido.status == 'A Receber', Pedido.data_vencimento >= datetime.utcnow()).scalar() or 0.0
        print(f"A Receber (Periodo: {titulo_periodo}): {total_a_receber_periodo}")  # DEBUG PRINT

        total_atrasado_periodo = apply_date_filter(db.session.query(func.sum(Pedido.valor)), Pedido.data_venda).filter(Pedido.status == 'A Receber', Pedido.data_vencimento < datetime.utcnow()).scalar() or 0.0
        print(f"Atrasado (Periodo: {titulo_periodo}): {total_atrasado_periodo}")  # DEBUG PRINT

        # KPIs DERIVADOS (USAM VALORES DO PERÍODO)
        lucro_periodo = total_pago_periodo - total_gasto_periodo
        roi_periodo = (lucro_periodo / total_gasto_periodo) if total_gasto_periodo > 0 else 0
        print(f"Lucro (Periodo: {titulo_periodo}): {lucro_periodo}")  # DEBUG PRINT
        print(f"ROI (Periodo: {titulo_periodo}): {roi_periodo}")  # DEBUG PRINT

        # Dicionário final para o template
        resumo_dados = {
            'agendado_total': total_agendado_global,
            'faturamento_liquido': total_pago_periodo,
            'gasto': total_gasto_periodo,
            'lucro': lucro_periodo,
            'roi': roi_periodo,
            'falta_receber': total_a_receber_periodo,  # <- MUDOU: Agora é do período
            'frutado': total_frustrado_periodo,
            'quantidade_vendas': quantidade_vendas_periodo,
            'atrasados': total_atrasado_periodo,      # <- MUDOU: Agora é do período
            'projecao': total_pago_periodo + total_a_receber_periodo + total_agendado_global
        }

        # Dados dos gráficos (PRECISAM SER RECALCULADOS COM A NOVA LÓGICA DE FILTRO)
        grafico_faturamento_resultado = apply_date_filter(db.session.query(func.date(Pedido.data_pagamento), func.sum(Pedido.valor)), Pedido.data_pagamento).filter(Pedido.status == 'Pago').group_by(func.date(Pedido.data_pagamento)).order_by(func.date(Pedido.data_pagamento)).all()
        grafico_labels = [item[0].strftime('%d/%m') for item in grafico_faturamento_resultado] if grafico_faturamento_resultado else []
        grafico_data = [float(item[1]) for item in grafico_faturamento_resultado] if grafico_faturamento_resultado else []
        print(f"Grafico Faturamento Labels: {grafico_labels}")  # DEBUG PRINT
        print(f"Grafico Faturamento Data: {grafico_data}")  # DEBUG PRINT

        # ...(Calcular dados para os outros gráficos de forma similar, usando apply_date_filter)...
        # Adicionar prints para os dados dos outros gráficos também

        context = {
            "pedidos": pedidos_da_pagina, "pagination": pagination, "resumo": resumo_dados,
            "periodo_selecionado": periodo_selecionado, "data_inicio": data_inicio_str, "data_fim": data_fim_str,
            "titulo_periodo": titulo_periodo,
            "grafico_labels": grafico_labels, "grafico_data": grafico_data
            # ... (passar dados dos outros gráficos para o template)
        }

        return render_template("dashboard.html", **context)

    except Exception as e:
        # Se ocorrer qualquer erro, mostre no terminal para depuração
        print(f"ERRO na rota dashboard: {e}")
        traceback.print_exc()
        # Você pode retornar uma página de erro aqui se preferir
        return f"Ocorreu um erro: {e}", 500


# --- Restante do arquivo (rotas listar_pedidos, salvar_observacao, webhook_braip, adicionar_gasto, atualizar_status, criar_pedidos_massa, criar_pedido_antigo, if __name__...) ---
# ... (COLE AQUI O RESTANTE DAS ROTAS QUE JÁ ESTÃO FUNCIONANDO) ...


@app.route("/pedidos")
def listar_pedidos():
    # Implementar a lógica da página de pedidos aqui (se já não estiver feita)
    # Similar à busca/filtro/paginação que estava antes na rota '/'
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 15
    status_filtro = request.args.get('status')
    termo_busca = request.args.get('busca')
    query = Pedido.query
    if status_filtro:
        if status_filtro == 'Atrasado':
            query = query.filter(
                Pedido.status == 'A Receber',
                Pedido.data_vencimento < datetime.utcnow(),
            )
        else:
            query = query.filter(Pedido.status == status_filtro)
    if termo_busca:
        query = query.filter(
            or_(
                Pedido.cliente.ilike(f'%{termo_busca}%'),
                Pedido.telefone.ilike(f'%{termo_busca}%'),
            )
        )

    pagination = query.order_by(Pedido.data_venda.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False
    )
    pedidos_da_pagina = pagination.items

    for pedido in pedidos_da_pagina:
        if (
            pedido.status == 'A Receber'
            and pedido.data_vencimento
            and pedido.data_vencimento < datetime.utcnow()
        ):
            pedido.status = 'Atrasado'

    return render_template(
        "pedidos.html",
        pedidos=pedidos_da_pagina,
        pagination=pagination,
    )


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
    if not dados:
        return jsonify({"status": "erro"}), 400

    trans_code = dados.get('codigo_transacao')
    if not trans_code:
        return jsonify({"status": "erro", "mensagem": "Código da transação ausente"}), 400

    pedido_existente = Pedido.query.filter_by(braip_trans_code=trans_code).first()
    status_braip = dados.get('status_compra_descricao')
    metodo_pagamento_braip = (
        dados.get('metodo_pagamento')
        or dados.get('forma_pagamento')
        or dados.get('forma_pagamento_desc')
    )

    if pedido_existente:
        pedido = pedido_existente
        if status_braip == 'Entregue':
            pedido.status = 'A Receber'
            pedido.data_vencimento = datetime.utcnow() + timedelta(days=30)
        elif status_braip == 'Pagamento Confirmado':
            pedido.status = 'Pago'
            pedido.data_pagamento = datetime.utcnow()
        elif status_braip in ['Estornado', 'Recusado', 'Cancelado']:
            pedido.status = 'Frustrado'
        if metodo_pagamento_braip:
            pedido.metodo_pagamento = metodo_pagamento_braip
    else:
        if status_braip != 'Aprovada':
            return jsonify({"status": "ok"}), 200

        pedido = Pedido(
            braip_trans_code=trans_code,
            cliente=dados.get('nome_cliente'),
            telefone=dados.get('cel_cliente'),
            valor=float(dados.get('valor_total')),
            status='Agendado',
            metodo_pagamento=metodo_pagamento_braip,
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
    if novo_status not in ['Pago', 'Frustrado', 'Atrasado']:
        return jsonify({'status': 'erro'}), 400

    pedido.status = novo_status
    if novo_status == 'Pago':
        pedido.data_pagamento = datetime.utcnow()
    else:
        pedido.data_pagamento = None

    db.session.commit()
    return jsonify({'status': 'sucesso'})


@app.route('/criar_pedidos_massa')
def criar_pedidos_massa():
    for i in range(30):
        codigo_unico = f"MASSA_{i}_{datetime.utcnow().timestamp()}"
        pedido_teste = Pedido(
            braip_trans_code=codigo_unico,
            cliente=f'Cliente de Massa {i + 1}',
            telefone='(11) 00000-0000',
            valor=10.00 + i,
            status='A Receber',
            data_vencimento=datetime.utcnow() + timedelta(days=i + 1),
        )
        db.session.add(pedido_teste)
    db.session.commit()
    return "30 pedidos de teste em massa criados com sucesso! <a href='/'>Voltar para o Painel</a>"


@app.route('/criar_pedido_antigo')
def criar_pedido_antigo():
    pedido_teste = Pedido.query.filter_by(braip_trans_code='TESTE_VENCIDO').first()
    if not pedido_teste:
        pedido_antigo = Pedido(
            braip_trans_code='TESTE_VENCIDO',
            cliente='Cliente Vencido de Teste',
            telefone='(99) 99999-9999',
            valor=50.00,
            status='A Receber',
            data_vencimento=datetime.utcnow() - timedelta(days=5),
        )
        db.session.add(pedido_antigo)
        db.session.commit()
        return "Pedido de teste vencido criado com sucesso! <a href='/'>Voltar para o Painel</a>"
    return "Pedido de teste vencido já existe. <a href='/'>Voltar para o Painel</a>"
