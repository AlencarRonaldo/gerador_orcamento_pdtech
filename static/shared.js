console.log("Shared.js v1.2 carregado");

// Theme Management
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        document.body.classList.remove('dark-mode');
    } else {
        document.body.classList.add('dark-mode');
    }
    updateThemeUI();
}

function toggleTheme() {
    const isDark = document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    updateThemeUI();
}

function updateThemeUI() {
    const isDark = document.body.classList.contains('dark-mode');
    const icon = document.getElementById('theme-icon');
    const text = document.getElementById('theme-text');
    if (icon) icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
    if (text) text.innerText = isDark ? 'Modo Claro' : 'Modo Escuro';
    window.dispatchEvent(new Event('themeChanged'));
}

// Sidebar Management
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    if (sidebar) sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('active');
}

function toggleSidebarCollapse() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    
    const isCollapsed = sidebar.classList.toggle('collapsed');
    localStorage.setItem('sidebar-collapsed', isCollapsed ? 'true' : 'false');
    
    // Update toggle icon
    const toggleIcon = sidebar.querySelector('.sidebar-toggle i');
    if (toggleIcon) {
        toggleIcon.className = isCollapsed ? 'fas fa-chevron-right' : 'fas fa-chevron-left';
    }
}

function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    
    // Check saved state
    const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
    if (isCollapsed) {
        sidebar.classList.add('collapsed');
    }
    
    const handleToggleVisibility = () => {
        const existingBtn = sidebar.querySelector('.sidebar-toggle');
        if (window.innerWidth > 1024) {
            if (!existingBtn) {
                const toggleBtn = document.createElement('div');
                toggleBtn.className = 'sidebar-toggle';
                toggleBtn.innerHTML = `<i class="fas fa-${sidebar.classList.contains('collapsed') ? 'chevron-right' : 'chevron-left'}"></i>`;
                toggleBtn.onclick = toggleSidebarCollapse;
                sidebar.appendChild(toggleBtn);
            }
        } else if (existingBtn) {
            existingBtn.remove();
        }
    };
    
    handleToggleVisibility();
    window.addEventListener('resize', handleToggleVisibility);

    // Wrap text nodes in nav-links for collapse support
    sidebar.querySelectorAll('.nav-link').forEach(link => {
        const textNodes = Array.from(link.childNodes).filter(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
        textNodes.forEach(node => {
            const span = document.createElement('span');
            span.textContent = node.textContent;
            node.replaceWith(span);
        });
    });
}

// Global API Handler (Auth Check)
async function apiFetch(url, options = {}) {
    try {
        const response = await fetch(url, options);
        
        if (response.status === 401) {
            console.warn("Sessão expirada ou não autorizado. Redirecionando para login...");
            window.location.href = "/login.html"; 
            return null;
        }

        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("text/html") && url.includes("/api/")) {
            console.warn("Recebido HTML em vez de JSON na API. Provável redirecionamento. Redirecionando para login...");
            window.location.href = "/login.html";
            return null;
        }

        return response;
    } catch (err) {
        console.error("Erro de conexão:", err);
        throw err;
    }
}

async function logout() {
    console.log("Iniciando processo de logout...");
    if (confirm("Deseja realmente sair do sistema?")) {
        try {
            await fetch('/api/logout', { method: 'POST' });
            console.log("Logout realizado com sucesso.");
        } catch (e) {
            console.error("Erro ao chamar logout da API:", e);
        }
        window.location.href = "/login.html";
    }
}

// Branding (Logo & Empresa)
async function loadBranding() {
    try {
        const res = await apiFetch('/api/config');
        if (!res) return;
        const data = await res.json();
        
        const logoContainers = document.querySelectorAll('.logo');
        logoContainers.forEach(container => {
            if (data.empresa_logo_b64) {
                let logoSrc = data.empresa_logo_b64;
                if (!logoSrc.startsWith('data:image')) {
                    logoSrc = 'data:image/png;base64,' + logoSrc;
                }
                
                if (container.closest('.sidebar')) {
                    container.innerHTML = `<img src="${logoSrc}" style="max-height: 50px; max-width: 100%; border-radius: 8px; object-fit: contain;">`;
                } else {
                    container.innerHTML = `<img src="${logoSrc}" style="max-height: 35px; border-radius: 4px;">`;
                }
            } else if (data.empresa_nome) {
                container.innerHTML = `<i class="fas fa-bolt"></i> <span>${data.empresa_nome}</span>`;
            }
        });
            
    } catch (e) {
        console.error("Erro ao carregar branding:", e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initSidebar();
    loadBranding();
    initPWA();
});

// PWA Support
function initPWA() {
    // Inject Meta Tags
    if (!document.querySelector('link[rel="manifest"]')) {
        const manifest = document.createElement('link');
        manifest.rel = 'manifest';
        manifest.href = '/manifest.json';
        document.head.appendChild(manifest);
    }
    
    if (!document.querySelector('meta[name="theme-color"]')) {
        const themeColor = document.createElement('meta');
        themeColor.name = 'theme-color';
        themeColor.content = '#3a7bd5';
        document.head.appendChild(themeColor);
    }

    const appleIcon = document.createElement('link');
    appleIcon.rel = 'apple-touch-icon';
    appleIcon.href = '/icon-512.png';
    document.head.appendChild(appleIcon);

    // Register Service Worker
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js').then(reg => {
                console.log('SW registrado:', reg.scope);
            }).catch(err => {
                console.error('Falha ao registrar SW:', err);
            });
        });
    }
}
