<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Despacho e Logística | Art's Burguer</title>
    
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />

    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/@phosphor-icons/web"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    
    <style>
        body { font-family: 'Inter', sans-serif; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        .card-enter { animation: slideIn 0.3s ease-out forwards; }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body class="bg-slate-100 flex flex-col h-screen text-slate-800 overflow-hidden">

    <!-- HEADER LOGÍSTICA -->
    <header class="bg-slate-900 text-white h-24 flex items-center justify-between px-8 shadow-xl shrink-0 z-10 relative">
        <div class="absolute inset-0 opacity-10 overflow-hidden pointer-events-none">
            <i class="ph-fill ph-map-pin text-[150px] absolute -right-10 -top-10"></i>
        </div>
        
        <div class="relative z-10 flex items-center">
            <div class="w-14 h-14 bg-brand-500 rounded-2xl flex items-center justify-center mr-4 shadow-lg shadow-brand-500/30">
                <i class="ph-bold ph-moped text-3xl text-white"></i>
            </div>
            <div>
                <h1 class="text-2xl font-black tracking-tight">Central de Expedição e Despacho</h1>
                <p class="text-[10px] text-brand-400 font-bold uppercase tracking-widest mt-0.5 flex items-center">
                    <span class="w-2 h-2 rounded-full bg-brand-400 animate-pulse mr-2"></span>
                    Monitoramento em Tempo Real
                </p>
            </div>
        </div>
        
        <div class="relative z-10 flex items-center space-x-4">
            <div class="bg-slate-800/80 backdrop-blur border border-slate-700 px-4 py-2.5 rounded-xl flex items-center shadow-inner hidden md:flex">
                <div class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse mr-2"></div>
                <span class="text-xs font-bold text-slate-300 tracking-wider">Sincronizado</span>
            </div>
            <button onclick="carregarPedidos()" class="bg-white/10 hover:bg-white/20 border border-white/10 text-white p-3.5 rounded-xl transition-colors active:scale-95 shadow-sm" title="Atualizar Agora">
                <i class="ph-bold ph-arrows-clockwise text-xl"></i>
            </button>
            <button onclick="window.close()" class="bg-red-500/20 hover:bg-red-500/40 text-red-400 p-3.5 rounded-xl transition-colors active:scale-95 border border-red-500/20" title="Sair da Expedição">
                <i class="ph-bold ph-x text-xl"></i>
            </button>
        </div>
    </header>

    <!-- KANBAN BOARD -->
    <main class="flex-1 flex overflow-hidden p-4 md:p-8 space-x-4 md:space-x-8">
        
        <!-- COLUNA 1: PRONTOS PARA DESPACHO (Aguardando Entregador) -->
        <section class="flex-1 flex flex-col bg-white rounded-[2rem] border border-slate-200 shadow-sm overflow-hidden">
            <div class="p-6 bg-amber-50 border-b border-amber-100 flex justify-between items-center shrink-0">
                <h2 class="font-black text-lg text-amber-900 flex items-center tracking-tight">
                    <i class="ph-fill ph-package text-amber-500 mr-2 text-2xl"></i> Prontos para Despacho
                </h2>
                <span class="bg-amber-500 text-white px-3 py-1 rounded-lg text-sm font-black shadow-sm" id="contador-prontos">0</span>
            </div>
            <div class="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 bg-slate-50/50 no-scrollbar relative" id="lista-prontos">
                <!-- CARDS INJETADOS AQUI -->
                <div class="flex flex-col items-center justify-center h-full text-slate-300 opacity-50">
                    <i class="ph-bold ph-spinner animate-spin text-5xl mb-4"></i>
                    <p class="font-bold text-sm uppercase tracking-widest">Buscando Pedidos...</p>
                </div>
            </div>
        </section>

        <!-- COLUNA 2: EM ROTA (Com o Cliente) -->
        <section class="flex-1 flex flex-col bg-white rounded-[2rem] border border-slate-200 shadow-sm overflow-hidden">
            <div class="p-6 bg-blue-50 border-b border-blue-100 flex justify-between items-center shrink-0">
                <h2 class="font-black text-lg text-blue-900 flex items-center tracking-tight">
                    <i class="ph-fill ph-motorcycle text-blue-500 mr-2 text-2xl"></i> Em Rota de Entrega
                </h2>
                <span class="bg-blue-600 text-white px-3 py-1 rounded-lg text-sm font-black shadow-sm" id="contador-rota">0</span>
            </div>
            <div class="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 bg-slate-50/50 no-scrollbar relative" id="lista-rota">
                <!-- CARDS INJETADOS AQUI -->
                <div class="flex flex-col items-center justify-center h-full text-slate-300 opacity-50">
                    <i class="ph-fill ph-motorcycle text-6xl mb-4"></i>
                    <p class="font-bold text-sm uppercase tracking-widest">Nenhuma entrega ativa</p>
                </div>
            </div>
        </section>

    </main>

    <!-- SCRIPT DE EXPEDIÇÃO -->
    <script>
        // Inicia a tela carregando os pedidos e configurando o Auto-Refresh
        document.addEventListener('DOMContentLoaded', () => {
            carregarPedidos();
            // Atualiza a tela a cada 10 segundos automaticamente
            setInterval(carregarPedidos, 10000);
        });

        async function carregarPedidos() {
            try {
                const res = await fetch('/api/logistica/pedidos');
                const data = await res.json();
                
                renderizarProntos(data.prontos);
                renderizarEmRota(data.em_rota);
                
                document.getElementById('contador-prontos').innerText = data.prontos.length;
                document.getElementById('contador-rota').innerText = data.em_rota.length;
            } catch(e) {
                console.error("Falha ao buscar pedidos da logística.");
            }
        }

        function renderizarProntos(pedidos) {
            const container = document.getElementById('lista-prontos');
            if(pedidos.length === 0) {
                container.innerHTML = `<div class="flex flex-col items-center justify-center h-full text-slate-300 opacity-50"><i class="ph-fill ph-check-circle text-6xl mb-4"></i><p class="font-bold text-sm uppercase tracking-widest">Expedição Limpa</p></div>`;
                return;
            }
            
            container.innerHTML = pedidos.map(p => `
                <div class="card-enter bg-white border border-slate-200 p-5 rounded-2xl shadow-sm hover:shadow-md transition-shadow relative overflow-hidden">
                    <div class="absolute left-0 top-0 bottom-0 w-1 bg-amber-400"></div>
                    
                    <div class="flex justify-between items-start mb-3 pl-2">
                        <div>
                            <span class="bg-slate-100 text-slate-600 px-2 py-1 rounded text-[10px] font-black uppercase tracking-widest mr-2 border border-slate-200 shadow-inner">#${p.senha_diaria}</span>
                            <span class="${p.tipo === 'DELIVERY' ? 'bg-purple-50 text-purple-700 border-purple-200' : 'bg-orange-50 text-orange-700 border-orange-200'} px-2 py-1 rounded text-[10px] font-black uppercase tracking-widest border shadow-sm">${p.tipo}</span>
                        </div>
                    </div>
                    
                    <div class="pl-2">
                        <h3 class="font-black text-slate-800 text-lg mb-1 tracking-tight">${p.cliente}</h3>
                        <p class="text-xs font-bold text-slate-500 mb-5 flex items-start leading-snug">
                            <i class="ph-fill ph-map-pin text-brand-500 mr-1.5 mt-0.5 text-base"></i> 
                            ${p.endereco}
                        </p>
                    </div>
                    
                    <div class="flex space-x-2 pl-2">
                        <div class="relative flex-1">
                            <i class="ph-bold ph-helmet absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400"></i>
                            <input type="text" id="motoboy-${p.id}" placeholder="Nome do Entregador" class="w-full pl-9 pr-3 py-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold outline-none focus:border-amber-500 transition-colors shadow-inner" ${p.tipo === 'RETIRADA' ? 'disabled value="Cliente Retira no Balcão"' : ''}>
                        </div>
                        <button onclick="despacharPedido(${p.id}, '${p.tipo}')" class="bg-amber-500 hover:bg-amber-600 text-white px-5 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-transform active:scale-95 shadow-md flex items-center justify-center">
                            <i class="ph-bold ph-paper-plane-tilt text-base md:mr-1"></i> <span class="hidden md:inline">Despachar</span>
                        </button>
                    </div>
                </div>
            `).join('');
        }

        function renderizarEmRota(pedidos) {
            const container = document.getElementById('lista-rota');
            if(pedidos.length === 0) {
                container.innerHTML = `<div class="flex flex-col items-center justify-center h-full text-slate-300 opacity-50"><i class="ph-fill ph-motorcycle text-6xl mb-4"></i><p class="font-bold text-sm uppercase tracking-widest">Nenhuma entrega ativa</p></div>`;
                return;
            }
            
            container.innerHTML = pedidos.map(p => `
                <div class="card-enter bg-slate-900 text-white border border-slate-800 p-5 rounded-2xl shadow-lg relative overflow-hidden">
                    <div class="absolute left-0 top-0 bottom-0 w-1 bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.8)]"></div>
                    
                    <div class="flex justify-between items-start mb-3 pl-2">
                        <div>
                            <span class="bg-slate-800 text-slate-300 px-2 py-1 rounded text-[10px] font-black uppercase tracking-widest mr-2 border border-slate-700 shadow-inner">#${p.senha_diaria}</span>
                            <span class="bg-blue-500/20 text-blue-400 border border-blue-500/30 px-2 py-1 rounded text-[10px] font-black uppercase tracking-widest"><i class="ph-fill ph-motorcycle mr-1"></i> A Caminho</span>
                        </div>
                    </div>
                    
                    <div class="pl-2">
                        <h3 class="font-black text-white text-lg mb-1 tracking-tight">${p.cliente}</h3>
                        <p class="text-xs font-medium text-slate-400 mb-5 flex items-start leading-snug">
                            <i class="ph-fill ph-map-pin text-brand-500 mr-1.5 mt-0.5 text-base"></i> 
                            ${p.endereco}
                        </p>
                    </div>
                    
                    <button onclick="concluirEntrega(${p.id})" class="w-full ml-2 bg-blue-600 hover:bg-blue-500 text-white py-4 rounded-xl text-xs font-black uppercase tracking-widest transition-transform active:scale-95 shadow-lg flex items-center justify-center border border-blue-500">
                        <i class="ph-bold ph-check-circle text-lg mr-2"></i> Baixar Entrega (Concluído)
                    </button>
                </div>
            `).join('');
        }

        async function despacharPedido(id, tipo) {
            let nomeMotoboy = "Balcão";
            
            if(tipo !== 'RETIRADA') {
                const input = document.getElementById(`motoboy-${id}`);
                if(!input.value.trim()) {
                    // Efeito visual de erro no input
                    input.classList.add('border-red-500', 'bg-red-50', 'placeholder-red-400');
                    setTimeout(() => input.classList.remove('border-red-500', 'bg-red-50', 'placeholder-red-400'), 1500);
                    return;
                }
                nomeMotoboy = input.value.trim();
            }

            const btn = event.currentTarget;
            const iconOriginal = btn.innerHTML;
            btn.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-lg"></i>';

            try {
                const res = await fetch(`/api/logistica/pedidos/${id}/despachar`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ nome_motoboy: nomeMotoboy })
                });
                if(res.ok) {
                    carregarPedidos();
                } else {
                    btn.innerHTML = iconOriginal;
                }
            } catch(e) { 
                alert("Erro de conexão com o banco de dados."); 
                btn.innerHTML = iconOriginal;
            }
        }

        async function concluirEntrega(id) {
            if(!confirm("Atenção: Confirmar que a mercadoria foi entregue ao cliente com sucesso? A venda será finalizada e sairá desta tela.")) return;
            
            const btn = event.currentTarget;
            btn.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-lg mr-2"></i> Baixando...';

            try {
                const res = await fetch(`/api/logistica/pedidos/${id}/entregar`, { method: 'PUT' });
                if(res.ok) {
                    carregarPedidos();
                } else {
                    btn.innerHTML = '<i class="ph-bold ph-check-circle text-lg mr-2"></i> Baixar Entrega (Concluído)';
                }
            } catch(e) { 
                alert("Erro de conexão."); 
                btn.innerHTML = '<i class="ph-bold ph-check-circle text-lg mr-2"></i> Baixar Entrega (Concluído)';
            }
        }
    </script>
</body>
</html>
