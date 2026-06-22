// Global State Tracking
let activeLogs = [];
let isHITLShowing = false;

// Polling interval
const API_INTERVAL = 1000;

document.addEventListener("DOMContentLoaded", () => {
    // Initial fetch and start interval
    fetchStatus();
    setInterval(fetchStatus, API_INTERVAL);
    loadRosterAndSkills();
});

async function fetchStatus() {
    try {
        const response = await fetch("/api/status");
        if (!response.ok) return;

        const data = await response.json();
        
        // Update Telemetry Widget Metrics
        document.getElementById("stat-cost").innerText = `$${data.total_cost_usd.toFixed(2)}`;
        document.getElementById("stat-tokens").innerText = data.total_tokens.toLocaleString();
        document.getElementById("stat-latency").innerText = `${data.avg_latency_sec.toFixed(1)}s`;

        // Update System State Status indicator
        const systemStatus = document.getElementById("system-status");
        const statusIndicator = systemStatus.querySelector(".status-indicator");
        const statusText = systemStatus.querySelector(".status-text");

        if (data.system_state === "running") {
            statusIndicator.className = "status-indicator running";
            statusText.innerText = "SYSTEM RUNNING";
        } else {
            statusIndicator.className = "status-indicator idle";
            statusText.innerText = "SYSTEM STANDBY";
        }

        // Update Agents VRAM & Context in Sidebar
        updateAgentList(data.loaded_models, data.agent_context);

        // Update MCP List
        updateMCPList(data.mcp_servers);

        // Update Live Console Logs
        updateConsoleLogs(data.logs);

        // Check active tasks for HITL gateway status
        checkHITLStatus();

        // Sync selected provider
        if (data.active_provider) {
            const selectEl = document.getElementById("provider-select");
            if (selectEl && selectEl.value !== data.active_provider) {
                selectEl.value = data.active_provider;
            }
        }

    } catch (error) {
        console.error("Error fetching status from LIEM engine:", error);
    }
}

function updateAgentList(loadedModels, agentContexts) {
    const listContainer = document.getElementById("agent-list");
    listContainer.innerHTML = "";

    // List of all domains
    const allAgents = [
        { id: "axel", name: "User Copilot (Axel)", size: 1.5, max_context: 128000 },
        { id: "planner", name: "Core Planner", size: 3.0, max_context: 128000 },
        { id: "router", name: "Core Router", size: 1.0, max_context: 64000 },
        { id: "scheduler", name: "Core Scheduler", size: 1.0, max_context: 64000 },
        { id: "backend_agent", name: "Backend Developer", size: 4.5, max_context: 128000 },
        { id: "qa_agent", name: "QA Tester", size: 3.0, max_context: 64000 }
    ];

    allAgents.forEach(agent => {
        const isActive = loadedModels.includes(agent.id);
        const activeVram = isActive ? agent.size : 0.0;
        const currentContext = agentContexts[agent.id] || 0;
        const contextPercent = Math.min(100, (currentContext / agent.max_context) * 100);

        const li = document.createElement("li");
        li.className = "agent-item";
        li.setAttribute("data-tooltip", `${agent.name} | VRAM: ${agent.size} GB | Max Context: ${(agent.max_context/1000).toFixed(0)}k tokens`);
        li.innerHTML = `
            <div class="agent-info">
                <div class="agent-name-row">
                    <span class="status-dot ${isActive ? 'active' : 'inactive'}"></span>
                    <span class="agent-name">${agent.name}</span>
                </div>
                <div class="context-progress-container">
                    <div class="context-label">
                        <span>Context: ${(currentContext/1000).toFixed(1)}k / ${(agent.max_context/1000).toFixed(0)}k</span>
                        <span>${contextPercent.toFixed(0)}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${contextPercent}%"></div>
                    </div>
                </div>
            </div>
            <span class="vram-badge">${activeVram.toFixed(1)}GB</span>
        `;
        listContainer.appendChild(li);
    });
}

function updateMCPList(servers) {
    // Update sidebar list
    const mcpContainer = document.getElementById("mcp-list");
    mcpContainer.innerHTML = "";
    
    servers.forEach(server => {
        const li = document.createElement("li");
        li.className = `mcp-item ${server.status}`;
        li.setAttribute("data-tooltip", `${server.name.toUpperCase()} Server (${server.status})`);
        li.innerHTML = `
            <i class="fa-solid fa-link"></i>
            <span>${server.name} (${server.status})</span>
        `;
        mcpContainer.appendChild(li);
    });
    
    // Update main MCP grid tab if visible
    const gridContainer = document.getElementById("mcp-grid-container");
    if (!gridContainer) return;
    gridContainer.innerHTML = "";
    
    servers.forEach(server => {
        const card = document.createElement("div");
        card.className = "registry-card";
        card.onclick = () => showMCPDetails(server);
        
        let toolsCount = 0;
        if (server.name === "filesystem") {
            toolsCount = 4;
        } else if (server.name === "github") {
            toolsCount = 3;
        } else if (server.name === "web-search") {
            toolsCount = 1;
        }
        
        card.innerHTML = `
            <div class="registry-card-header">
                <span class="registry-card-title">${server.name.toUpperCase()}</span>
                <span class="registry-card-badge connected">${server.status}</span>
            </div>
            <div class="registry-card-desc">Model Context Protocol server providing local filesystem tools, API queries, or web capabilities.</div>
            <div class="registry-card-footer">
                <span><i class="fa-solid fa-screwdriver-wrench"></i> ${toolsCount} tools exposed</span>
            </div>
        `;
        gridContainer.appendChild(card);
    });
}

function showMCPDetails(server) {
    let toolsList = [];
    if (server.name === "filesystem") {
        toolsList = [
            { name: "read_file", desc: "Reads file content from the local workspace." },
            { name: "write_file", desc: "Creates or modifies files inside sandbox paths." },
            { name: "list_dir", desc: "Lists all children inside a target directory." },
            { name: "grep_search", desc: "Performs ripgrep pattern queries inside project files." }
        ];
    } else if (server.name === "github") {
        toolsList = [
            { name: "get_pr", desc: "Queries open Pull Requests from the target repository." },
            { name: "create_issue", desc: "Submits bugs or tasks directly to github issues." },
            { name: "push_code", desc: "Pushes local commits to the remote main branch." }
        ];
    } else if (server.name === "web-search") {
        toolsList = [
            { name: "search_web", desc: "Performs web queries for real-time document search." }
        ];
    }
    
    let toolsHtml = toolsList.map(t => `
        <li style="margin-bottom: 10px;">
            <strong><code>${t.name}</code></strong>
            <p style="margin: 2px 0 0 0; color: var(--text-secondary); font-size: 12px;">${t.desc}</p>
        </li>
    `).join("");
    
    const html = `
        <div class="modal-section">
            <div class="modal-section-title">Protocol Server</div>
            <p>${server.name} (${server.status})</p>
        </div>
        <div class="modal-section">
            <div class="modal-section-title">Exposed Client Tools</div>
            <ul class="modal-list" style="margin-top: 8px;">
                ${toolsHtml}
            </ul>
        </div>
    `;
    showModal(`${server.name.toUpperCase()} Server`, "fa-server", html);
}

function updateConsoleLogs(logs) {
    const logContainer = document.getElementById("log-lines");
    
    // Check if new logs arrived
    if (logs.length === activeLogs.length) return;

    // Append new lines
    const newLines = logs.slice(activeLogs.length);
    newLines.forEach(line => {
        const lineTrim = line.trim();
        if (!lineTrim) return;

        let el;
        if (lineTrim.startsWith("[User]")) {
            // User Chat Bubble (Right Aligned)
            el = document.createElement("div");
            el.className = "bubble-user";
            el.innerText = lineTrim.substring(6).trim();
        } else if (lineTrim.startsWith("[Axel]")) {
            // Copilot Chat Bubble (Left Aligned)
            el = document.createElement("div");
            el.className = "bubble-copilot";
            el.innerHTML = `
                <div class="avatar-container">
                    <i class="fa-solid fa-robot"></i>
                </div>
                <div class="bubble-content">
                    <strong>Axel</strong>
                    <p>${lineTrim.substring(6).trim()}</p>
                </div>
            `;
        } else if (lineTrim.startsWith("[HITL]")) {
            // HITL Warning Chat Bubble (Left Aligned)
            el = document.createElement("div");
            el.className = "bubble-copilot";
            el.innerHTML = `
                <div class="avatar-container" style="background-color: rgba(231,76,60,0.1); border-color: rgba(231,76,60,0.3); color: var(--error-color);">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                </div>
                <div class="bubble-content">
                    <strong>HITL System</strong>
                    <p>${lineTrim.substring(6).trim()}</p>
                </div>
            `;
        } else {
            // System Log Line (Terminal Card Layout)
            el = document.createElement("div");
            
            // Determine status color class
            let statusClass = "status-log";
            
            if (lineTrim.includes("completed") || lineTrim.includes("PASSED") || lineTrim.includes("success") || lineTrim.includes("SUCCESSFUL")) {
                statusClass = "completed-status";
            } else if (lineTrim.includes("failed") || lineTrim.includes("FAILED") || lineTrim.includes("error") || lineTrim.includes("Error")) {
                statusClass = "failed-status";
            } else if (lineTrim.includes("running") || lineTrim.includes("Executing") || lineTrim.includes("loading") || lineTrim.includes("Requesting")) {
                statusClass = "running-status";
            } else if (lineTrim.includes("WARNING") || lineTrim.includes("warning") || lineTrim.includes("Escalation") || lineTrim.includes("breached")) {
                statusClass = "warning-status";
            }

            el.className = `log-system ${statusClass}`;
            el.innerHTML = `
                <span class="status-dot"></span>
                <span class="log-text">${lineTrim}</span>
            `;
        }

        logContainer.appendChild(el);
    });

    activeLogs = [...logs];

    // Auto-scroll to bottom of console
    const consoleBody = document.getElementById("console-body");
    consoleBody.scrollTop = consoleBody.scrollHeight;
}

// Tab Switching
function switchTab(tabId) {
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));
    
    const btn = document.getElementById(`btn-${tabId}`);
    if (btn) btn.classList.add("active");
    
    const content = document.getElementById(tabId);
    if (content) content.classList.add("active");
}

// Details Modal
function showModal(title, iconClass, bodyHtml) {
    document.getElementById("modal-title").innerText = title;
    document.getElementById("modal-icon").className = `fa-solid ${iconClass}`;
    document.getElementById("modal-body").innerHTML = bodyHtml;
    document.getElementById("details-modal").classList.add("active");
}

function closeModal() {
    document.getElementById("details-modal").classList.remove("active");
}

// Roster & Skills Loader
async function loadRosterAndSkills() {
    try {
        const agentsResponse = await fetch("/api/agents");
        if (agentsResponse.ok) {
            const agents = await agentsResponse.json();
            renderAgentsRoster(agents);
        }
        
        const skillsResponse = await fetch("/api/skills");
        if (skillsResponse.ok) {
            const skills = await skillsResponse.json();
            renderSkillsRegistry(skills);
        }
    } catch (e) {
        console.error("Error loading roster and skills:", e);
    }
}

function renderAgentsRoster(agents) {
    const container = document.getElementById("agents-grid-container");
    if (!container) return;
    container.innerHTML = "";
    
    agents.forEach(agent => {
        const card = document.createElement("div");
        card.className = "registry-card";
        card.onclick = () => showAgentDetails(agent);
        card.innerHTML = `
            <div class="registry-card-header">
                <span class="registry-card-title">${agent.name}</span>
                <span class="registry-card-badge ${agent.domain === 'Control Plane' ? 'control' : 'data'}">${agent.domain}</span>
            </div>
            <div class="registry-card-desc">${agent.desc}</div>
            <div class="registry-card-footer">
                <span><i class="fa-solid fa-microchip"></i> ${agent.vram_gb} GB VRAM</span>
                <span><i class="fa-solid fa-user-gear"></i> ${agent.role}</span>
            </div>
        `;
        container.appendChild(card);
    });
}

function showAgentDetails(agent) {
    const html = `
        <div class="modal-section">
            <div class="modal-section-title">Agent Name</div>
            <p>${agent.name}</p>
        </div>
        <div class="modal-section">
            <div class="modal-section-title">Role / Subsystem</div>
            <p>${agent.role}</p>
        </div>
        <div class="modal-section">
            <div class="modal-section-title">Execution Plane</div>
            <p>${agent.domain}</p>
        </div>
        <div class="modal-section">
            <div class="modal-section-title">VRAM Footprint</div>
            <p>${agent.vram_gb} GB VRAM (Scale-to-Zero offload active)</p>
        </div>
        <div class="modal-section">
            <div class="modal-section-title">Functional Description</div>
            <p>${agent.desc}</p>
        </div>
    `;
    showModal(agent.name, "fa-user-tie", html);
}

function renderSkillsRegistry(skills) {
    const container = document.getElementById("skills-grid-container");
    if (!container) return;
    container.innerHTML = "";
    
    if (skills.length === 0) {
        container.innerHTML = "<p style='color: var(--text-secondary); padding: 10px;'>No declarative Markdown skills found in the local /agents directory.</p>";
        return;
    }
    
    skills.forEach(skill => {
        const card = document.createElement("div");
        card.className = "registry-card";
        card.onclick = () => showSkillDetails(skill);
        card.innerHTML = `
            <div class="registry-card-header">
                <span class="registry-card-title">${skill.name}</span>
                <span class="registry-card-badge control">${skill.domain}</span>
            </div>
            <div class="registry-card-desc">${skill.description}</div>
            <div class="registry-card-footer">
                <span><i class="fa-regular fa-file-code"></i> agents/${skill.file}</span>
            </div>
        `;
        container.appendChild(card);
    });
}

function showSkillDetails(skill) {
    const html = `
        <div class="modal-section">
            <div class="modal-section-title">Skill Name</div>
            <p>${skill.name}</p>
        </div>
        <div class="modal-section">
            <div class="modal-section-title">Domain Scope</div>
            <p>${skill.domain}</p>
        </div>
        <div class="modal-section">
            <div class="modal-section-title">Source Path</div>
            <p><code>agents/${skill.file}</code></p>
        </div>
        <div class="modal-section">
            <div class="modal-section-title">System Role Focus</div>
            <p>${skill.description}</p>
        </div>
    `;
    showModal(skill.name, "fa-book-open", html);
}

async function checkHITLStatus() {
    try {
        const response = await fetch("/api/tasks");
        if (!response.ok) return;

        const tasks = await response.json();
        const hitlTask = tasks.find(t => t.status === "failed" && t.task_id === "T-999");
        
        const card = document.getElementById("hitl-card");
        if (hitlTask && !isHITLShowing) {
            card.classList.remove("hidden");
            isHITLShowing = true;
            const consoleBody = document.getElementById("console-body");
            consoleBody.scrollTop = consoleBody.scrollHeight;
        } else if (!hitlTask && isHITLShowing) {
            card.classList.add("hidden");
            isHITLShowing = false;
        }
    } catch (e) {
        console.error("Error checking task states:", e);
    }
}

async function sendPrompt(event) {
    event.preventDefault();
    const input = document.getElementById("prompt-input");
    const prompt = input.value ? input.value.trim() : "";
    if (!prompt) return;

    input.value = "";

    try {
        await fetch("/api/prompt", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: prompt })
        });
    } catch (e) {
        console.error("Error triggering prompt:", e);
    }
}

async function submitHITL(action) {
    try {
        await fetch("/api/hitl/action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ task_id: "T-999", action: action })
        });
        document.getElementById("hitl-card").classList.add("hidden");
        isHITLShowing = false;
    } catch (e) {
        console.error("Error submitting HITL action:", e);
    }
}

async function changeProvider(providerValue) {
    try {
        const response = await fetch("/api/provider", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ provider: providerValue })
        });
        if (response.ok) {
            await fetchStatus();
        }
    } catch (error) {
        console.error("Error setting active provider:", error);
    }
}
