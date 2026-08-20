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
    
    <!-- 🚨 MOTOR DE TEMA CLARO/ESCURO 🚨 -->
    <script>
        tailwind.config = { darkMode: 'class', theme: { extend: { fontFamily: { sans: ['Inter', 'sans-serif'] }, colors: { brand: { 500: '#ff4757', 600: '#e04050' } } } } };
        if (localStorage.getItem('theme') === 'dark') { document.documentElement.classList.add('dark'); }
    </script>

    <style>
        body { font-family: 'Inter', sans-serif; transition: background-color 0.3s, color 0.3s; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        .card-enter { animation: slideIn 0.3s ease-out forwards; }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body class="bg-slate-100 dark:bg-[#0b1120] text-slate-800 dark:text-slate-100 flex flex-col h-screen overflow-hidden transition-colors duration-300">

    <!-- HEADER LOGÍSTICA -->
    <header class="bg-slate-900 dark:bg-slate-950 text-white h-24 flex items-center justify-between px-8 shadow-xl shrink-0 z-10 relative border-b border-transparent dark:border-slate-800 transition-colors">
        <div class="absolute inset-0 opacity-10 overflow-hidden pointer-events-none">
            <i class="ph-fill ph-map-pin text-[150px] absolute -right-10 -top-10"></i>
        </div>
        
        <div class="relative z-10 flex items-center">
            <!-- 🚨 LOGO INJETADA AQUI 🚨 -->
            <div id="header-logo-container" class="w-14 h-14 bg-brand-500 rounded-2xl flex items-center justify-center mr-4 shadow-lg shadow-brand-500/30 overflow-hidden">
                <i id="header-logo-letra" class="ph-bold ph-moped text-3xl text-white"></i>
                <img id="header-logo-img" src="" class="w-full h-full object-cover hidden">
            </div>
            <div>
                <h1 class="text-2xl font-black tracking-tight">Central de Expedição e Despacho</h1>
                <p class="text-[10px] text-brand-400 font-bold uppercase tracking-widest mt-0.5 flex items-center">
                    <span class="w-2 h-2 rounded-full bg-brand-400 animate-pulse mr-2"></span> Integração Uber / 99 / Frota Própria
                </p>
            </div>
        </div>
        
        <div class="relative z-10 flex items-center space-x-4">
            <div class="bg-slate-800/80 backdrop-blur border border-slate-700 px-4 py-2.5 rounded-xl flex items-center shadow-inner hidden md:flex">
                <div class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse mr-2"></div>
                <span class="text-xs font-bold text-slate-300 tracking-wider">Auto-Refresh Ativo</span>
            </div>
            
            <button onclick="toggleTheme()" class="bg-white/10 hover:bg-white/20 border border-white/10 text-white p-3.5 rounded-xl transition-colors active:scale-95 shadow-sm" title="Mudar Tema">
                <i id="theme-icon" class="ph-bold ph-moon text-xl"></i>
            </button>

            <button onclick="buscarPedidosLogistica()" class="bg-white/10 hover:bg-white/20 border border-white/10 text-white p-3.5 rounded-xl transition-colors active:scale-95 shadow-sm" title="Atualizar Agora">
                <i class="ph-bold ph-arrows-clockwise text-xl"></i>
            </button>
            <a href="/gestao" class="bg-red-500/20 hover:bg-red-500/40 text-red-400 p-3.5 rounded-xl transition-colors active:scale-95 border border-red-500/20 flex items-center" title="Sair da Expedição">
                <i class="ph-bold ph-sign-out text-xl"></i>
            </a>
        </div>
    </header>

    <!-- KANBAN BOARD -->
    <main class="flex-1 flex overflow-hidden p-4 md:p-8 space-x-4 md:space-x-8">
        
        <!-- COLUNA 1: PRONTOS PARA DESPACHO -->
        <section class="flex-1 flex flex-col bg-white dark:bg-slate-900 rounded-[2rem] border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden transition-colors">
            <div class="p-6 bg-amber-50 dark:bg-amber-500/10 border-b border-amber-100 dark:border-amber-500/20 flex justify-between items-center shrink-0 transition-colors">
                <h2 class="font-black text-lg text-amber-900 dark:text-amber-400 flex items-center tracking-tight">
                    <i class="ph-fill ph-package text-amber-500 mr-2 text-2xl"></i> Aguardando Saída
                </h2>
                <span class="bg-amber-500 text-white px-3 py-1 rounded-lg text-sm font-black shadow-sm" id="badge-prontos">0</span>
            </div>
            <div class="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 bg-slate-50/50 dark:bg-slate-900/50 no-scrollbar relative transition-colors" id="lista-prontos">
                <div class="flex flex-col items-center justify-center h-full text-slate-300 dark:text-slate-600 opacity-50">
                    <i class="ph-bold ph-spinner animate-spin text-5xl mb-4"></i>
                    <p class="font-bold text-sm uppercase tracking-widest">Buscando Pedidos...</p>
                </div>
            </div>
        </section>

        <!-- COLUNA 2: EM ROTA (Com o Cliente) -->
        <section class="flex-1 flex flex-col bg-white dark:bg-slate-900 rounded-[2rem] border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden transition-colors">
            <div class="p-6 bg-blue-50 dark:bg-blue-500/10 border-b border-blue-100 dark:border-blue-500/20 flex justify-between items-center shrink-0 transition-colors">
                <h2 class="font-black text-lg text-blue-900 dark:text-blue-400 flex items-center tracking-tight">
                    <i class="ph-fill ph-map-pin-line text-blue-500 mr-2 text-2xl"></i> Em Rota de Entrega
                </h2>
                <span class="bg-blue-600 text-white px-3 py-1 rounded-lg text-sm font-black shadow-sm" id="badge-rota">0</span>
            </div>
            <div class="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 bg-slate-50/50 dark:bg-slate-900/50 no-scrollbar relative transition-colors" id="lista-rota">
                <div class="flex flex-col items-center justify-center h-full text-slate-300 dark:text-slate-600 opacity-50">
                    <i class="ph-fill ph-motorcycle text-6xl mb-4"></i>
                    <p class="font-bold text-sm uppercase tracking-widest">Nenhuma entrega ativa</p>
                </div>
            </div>
        </section>

    </main>

    <!-- SCRIPT DE EXPEDIÇÃO -->
    <script>
        document.addEventListener('DOMContentLoaded', async () => {
            buscarPedidosLogistica();
            try {
                const res = await fetch('/api/gestao/configuracoes'); 
                const configLoja = await res.json();
                
                if(configLoja.logo_url && configLoja.logo_url.trim() !== '' && configLoja.logo_url !== 'None') {
                    const letra = document.getElementById('header-logo-letra'); 
                    const img = document.getElementById('header-logo-img'); 
                    const container = document.getElementById('header-logo-container');
                    
                    img.onerror = function() { this.classList.add('hidden'); letra.classList.remove('hidden'); };
                    img.src = configLoja.logo_url; 
                    img.classList.remove('hidden');
                    letra.classList.add('hidden'); 
                    container.classList.remove('bg-brand-500'); 
                    container.classList.add('bg-white', 'border', 'border-slate-200');
                }
            } catch(e) {}
        });

        const themeIcon = document.getElementById('theme-icon');
        if (document.documentElement.classList.contains('dark') && themeIcon) themeIcon.classList.replace('ph-moon', 'ph-sun');

        function toggleTheme() {
            if (document.documentElement.classList.contains('dark')) {
                document.documentElement.classList.remove('dark');
                localStorage.setItem('theme', 'light');
                if(themeIcon) themeIcon.classList.replace('ph-sun', 'ph-moon');
            } else {
                document.documentElement.classList.add('dark');
                localStorage.setItem('theme', 'dark');
                if(themeIcon) themeIcon.classList.replace('ph-moon', 'ph-sun');
            }
        }

        setInterval(buscarPedidosLogistica, 5000);

        async function buscarPedidosLogistica() {
            try {
                const response = await fetch('/api/logistica/pedidos');
                const dados = await response.json();
                
                renderizarProntos(dados.prontos || []);
                renderizarEmRota(dados.em_rota || []);
                
                document.getElementById('badge-prontos').innerText = (dados.prontos || []).length;
                document.getElementById('badge-rota').innerText = (dados.em_rota || []).length;
            } catch (error) { console.error("Erro ao buscar dados logísticos:", error); }
        }

        function renderizarProntos(pedidos) {
            const container = document.getElementById('lista-prontos');
            if (pedidos.length === 0) {
                container.innerHTML = `<div class="h-full flex flex-col items-center justify-center text-slate-300 dark:text-slate-600 opacity-50 transition-colors"><i class="ph-fill ph-check-circle text-6xl mb-4"></i><p class="font-bold text-sm uppercase tracking-widest">Expedição Limpa</p></div>`;
                return;
            }

            container.innerHTML = pedidos.map(p => {
                const isRetirada = (p.tipo && p.tipo.includes('RETIRADA')) || (p.endereco && p.endereco.includes('Retirada'));
                const endLimpo = p.endereco ? p.endereco.replace(/'/g, "\\'") : '';

                return `
                    <div class="card-enter bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5 rounded-2xl shadow-sm hover:shadow-md transition-all relative overflow-hidden">
                        <div class="absolute left-0 top-0 bottom-0 w-1 ${isRetirada ? 'bg-purple-500' : 'bg-amber-400'}"></div>
                        <div class="flex justify-between items-start mb-3 pl-2">
                            <div>
                                <span class="bg-slate-100 dark:bg-slate-900 text-slate-600 dark:text-slate-400 px-2 py-1 rounded text-[10px] font-black uppercase tracking-widest mr-2 border border-slate-200 dark:border-slate-700 shadow-inner">#${p.senha_diaria || p.id}</span>
                                <span class="${isRetirada ? 'bg-purple-50 dark:bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-200 dark:border-purple-500/20' : 'bg-orange-50 dark:bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-200 dark:border-orange-500/20'} px-2 py-1 rounded text-[10px] font-black uppercase tracking-widest border shadow-sm">${isRetirada ? 'Retirada' : 'Delivery'}</span>
                            </div>
                        </div>
                        <div class="pl-2 mb-4">
                            <h3 class="font-black text-slate-800 dark:text-white text-lg mb-1 tracking-tight">${p.cliente}</h3>
                            <p class="text-xs font-bold text-slate-500 dark:text-slate-400 flex items-start leading-snug">
                                <i class="ph-fill ph-map-pin text-brand-500 mr-1.5 mt-0.5 text-base"></i> ${p.endereco}
                            </p>
                        </div>
                        <div class="pl-2">
                            ${isRetirada ? `
                                <button onclick="concluirRetirada(${p.id})" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-black py-3 rounded-xl flex items-center justify-center transition-colors text-xs uppercase tracking-widest shadow-md">
                                    <i class="ph-fill ph-check-circle mr-2 text-lg"></i> Cliente Retirou
                                </button>
                            ` : `
                                <div class="space-y-2">
                                    <div class="flex space-x-2">
                                        <button onclick="copilotoDespacho(${p.id}, 'Uber', '${endLimpo}')" id="btn-uber-${p.id}" class="flex-1 bg-black hover:bg-slate-800 text-white font-black py-3 rounded-xl flex items-center justify-center transition-colors text-[10px] uppercase tracking-widest shadow-md"><i class="ph-fill ph-car-profile mr-1 text-base"></i> Uber</button>
                                        <button onclick="copilotoDespacho(${p.id}, '99', '${endLimpo}')" id="btn-99-${p.id}" class="flex-1 bg-yellow-400 hover:bg-yellow-500 text-black font-black py-3 rounded-xl flex items-center justify-center transition-colors text-[10px] uppercase tracking-widest shadow-md"><i class="ph-fill ph-car-profile mr-1 text-base"></i> 99</button>
                                    </div>
                                    <button onclick="despacharMotoboyProprio(${p.id})" id="btn-proprio-${p.id}" class="w-full bg-amber-500 hover:bg-amber-600 text-white font-black py-3 rounded-xl flex items-center justify-center transition-colors text-[10px] uppercase tracking-widest shadow-md"><i class="ph-fill ph-moped mr-2 text-lg"></i> Motoboy da Casa</button>
                                    <button onclick="window.open('/motoboy?pedido=${p.senha_diaria || p.id}&end=${encodeURIComponent(endLimpo)}', '_blank')" class="w-full bg-slate-800 dark:bg-slate-900 hover:bg-slate-700 text-slate-300 font-bold py-2 mt-2 rounded-xl flex items-center justify-center transition-colors text-[10px] uppercase tracking-widest shadow-inner border border-transparent dark:border-slate-700"><i class="ph-bold ph-qr-code mr-1"></i> Enviar Link do GPS</button>
                                </div>
                            `}
                        </div>
                    </div>`;
            }).join('');
        }

        function renderizarEmRota(pedidos) {
            const container = document.getElementById('lista-rota');
            if (pedidos.length === 0) {
                container.innerHTML = `<div class="h-full flex flex-col items-center justify-center text-slate-300 dark:text-slate-600 opacity-50 transition-colors"><i class="ph-fill ph-motorcycle text-6xl mb-4"></i><p class="font-bold text-sm uppercase tracking-widest">Nenhuma entrega ativa</p></div>`;
                return;
            }

            container.innerHTML = pedidos.map(p => {
                const endLimpo = p.endereco ? p.endereco.replace(/'/g, "\\'") : '';
                return `
                <div class="card-enter bg-slate-900 dark:bg-slate-800 text-white border border-slate-800 dark:border-slate-700 p-5 rounded-2xl shadow-lg relative overflow-hidden transition-colors">
                    <div class="absolute left-0 top-0 bottom-0 w-1 bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.8)]"></div>
                    <div class="flex justify-between items-start mb-3 pl-2">
                        <div>
                            <span class="bg-slate-800 dark:bg-slate-900 text-slate-300 px-2 py-1 rounded text-[10px] font-black uppercase tracking-widest mr-2 border border-slate-700 shadow-inner">#${p.senha_diaria || p.id}</span>
                            <span class="bg-blue-500/20 text-blue-400 border border-blue-500/30 px-2 py-1 rounded text-[10px] font-black uppercase tracking-widest"><i class="ph-fill ph-motorcycle mr-1"></i> A Caminho</span>
                        </div>
                    </div>
                    <div class="pl-2 mb-4">
                        <h3 class="font-black text-white text-lg mb-1 tracking-tight">${p.cliente}</h3>
                        <p class="text-xs font-medium text-slate-400 flex items-start leading-snug"><i class="ph-fill ph-map-pin text-brand-500 mr-1.5 mt-0.5 text-base"></i> ${p.endereco}</p>
                    </div>
                    <div class="flex space-x-2 pl-2">
                        <button onclick="abrirGPS('${endLimpo}')" class="bg-slate-700 hover:bg-slate-600 text-white font-black py-3 px-4 rounded-xl flex items-center justify-center transition-colors text-xs shadow-md"><i class="ph-fill ph-navigation-arrow text-blue-400 text-lg"></i></button>
                        <button onclick="marcarComoEntregue(${p.id})" class="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-black py-3 rounded-xl flex items-center justify-center transition-colors text-xs uppercase tracking-widest shadow-md border border-blue-500"><i class="ph-bold ph-check-circle mr-2 text-lg"></i> Entregue</button>
                    </div>
                </div>`;
            }).join('');
        }

        function abrirGPS(endereco) {
            if(!endereco || endereco.includes('Retirada')) return alert("Endereço inválido para GPS.");
            const enderecoLimpo = endereco.replace('Endereço: ', '').trim();
            window.open(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(enderecoLimpo)}`, '_blank');
        }

        async function copilotoDespacho(pedidoId, plataforma, enderecoFormatado) {
            const isUber = plataforma === 'Uber';
            const enderecoLimpo = enderecoFormatado.replace('Endereço: ', '').trim();
            try { await navigator.clipboard.writeText(enderecoLimpo); } catch(e) {}

            if (isUber) window.location.href = `uber://?action=setPickup&pickup=my_location&dropoff[formatted_address]=${encodeURIComponent(enderecoLimpo)}`;
            else { alert("Endereço copiado! 📋\nA 99 vai abrir."); window.location.href = "taxis99://"; }

            setTimeout(async () => {
                if(!confirm(`Já pediu a corrida na ${plataforma} para este cliente?`)) return;
                try {
                    const res = await fetch(`/api/logistica/pedidos/${pedidoId}/despachar`, {
                        method: 'PUT', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ nome_motoboy: `App Parceiro (${plataforma})` })
                    });
                    if(res.ok) buscarPedidosLogistica(); 
                } catch(e) { alert("Falha de conexão."); }
            }, 4000);
        }

        async function despacharMotoboyProprio(pedidoId) {
            const nomeMotoboy = prompt("Nome do Motoboy:", "Motoboy Próprio");
            if (nomeMotoboy === null) return;
            try {
                const res = await fetch(`/api/logistica/pedidos/${pedidoId}/despachar`, {
                    method: 'PUT', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ nome_motoboy: nomeMotoboy })
                });
                if(res.ok) buscarPedidosLogistica(); 
            } catch(e) { alert("Falha de conexão."); }
        }

        async function concluirRetirada(pedidoId) {
            if(!confirm("Confirmar que o cliente retirou o pedido?")) return;
            try {
                const res = await fetch(`/api/logistica/pedidos/${pedidoId}/entregar`, { method: 'PUT' });
                if(res.ok) buscarPedidosLogistica(); 
            } catch(e) {}
        }

        async function marcarComoEntregue(pedidoId) {
            if(!confirm("Confirmar que foi entregue?")) return;
            try {
                const res = await fetch(`/api/logistica/pedidos/${pedidoId}/entregar`, { method: 'PUT' });
                if(res.ok) buscarPedidosLogistica(); 
            } catch(e) {}
        }
    </script>
</body>
</html>
