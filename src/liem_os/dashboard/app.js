// Global State Tracking
let activeLogs = [];
let isHITLShowing = false;
let lastTasksJson = "";
let lastExecutionsJson = "";

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
        
        // Update Quota limits and fills
        const quota5hPercent = data.five_hour_limit > 0 ? (data.five_hour_tokens_used / data.five_hour_limit) * 100 : 0;
        const quotaWeeklyPercent = data.weekly_limit > 0 ? (data.weekly_tokens_used / data.weekly_limit) * 100 : 0;
        
        const q5hText = document.getElementById("quota-5h-text");
        const q5hFill = document.getElementById("quota-5h-fill");
        if (q5hText && q5hFill) {
            q5hText.innerText = `${quota5hPercent.toFixed(0)}% (${data.five_hour_tokens_used.toLocaleString()} / ${(data.five_hour_limit/1000).toFixed(0)}k)`;
            q5hFill.style.width = `${quota5hPercent}%`;
            if (quota5hPercent >= 85) q5hFill.style.backgroundColor = "var(--error-color)";
            else if (quota5hPercent >= 50) q5hFill.style.backgroundColor = "var(--warning-color)";
            else q5hFill.style.backgroundColor = "var(--accent-color)";
        }
        
        const qWeeklyText = document.getElementById("quota-weekly-text");
        const qWeeklyFill = document.getElementById("quota-weekly-fill");
        if (qWeeklyText && qWeeklyFill) {
            qWeeklyText.innerText = `${quotaWeeklyPercent.toFixed(0)}% (${data.weekly_tokens_used.toLocaleString()} / ${(data.weekly_limit/1000).toFixed(0)}k)`;
            qWeeklyFill.style.width = `${quotaWeeklyPercent}%`;
            if (quotaWeeklyPercent >= 85) qWeeklyFill.style.backgroundColor = "var(--error-color)";
            else if (quotaWeeklyPercent >= 50) qWeeklyFill.style.backgroundColor = "var(--warning-color)";
            else qWeeklyFill.style.backgroundColor = "var(--accent-color)";
        }



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

        // Update Tasks Table
        updateTasksTable();

        // Update Active Plans List
        updatePlanList();

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

    let renderedCount = 0;

    allAgents.forEach(agent => {
        const isActive = loadedModels.includes(agent.id);
        if (!isActive) return; // Only display loaded/active agents in the sidebar

        renderedCount++;
        const activeVram = agent.size;
        const currentContext = agentContexts[agent.id] || 0;
        const contextPercent = Math.min(100, (currentContext / agent.max_context) * 100);

        const li = document.createElement("li");
        li.className = "agent-item active";
        li.setAttribute("data-tooltip", `${agent.name} | VRAM: ${agent.size} GB | Max Context: ${(agent.max_context/1000).toFixed(0)}k tokens`);
        li.innerHTML = `
            <div class="agent-info">
                <div class="agent-name-row">
                    <span class="status-dot active"></span>
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

    // Also display any active models not predefined (e.g. claude-3-5-sonnet, gpt-4o)
    loadedModels.forEach(modelId => {
        const isPredefined = allAgents.some(agent => agent.id === modelId);
        if (isPredefined) return;

        renderedCount++;
        const modelName = modelId === "claude-3-5-sonnet" ? "Claude 3.5 Sonnet" : (modelId === "gpt-4o" ? "GPT-4o" : modelId);
        const size = modelId === "claude-3-5-sonnet" ? 2.4 : (modelId === "gpt-4o" ? 2.0 : 1.5);
        const maxContext = 200000;
        const currentContext = agentContexts[modelId] || 0;
        const contextPercent = Math.min(100, (currentContext / maxContext) * 100);

        const li = document.createElement("li");
        li.className = "agent-item active";
        li.setAttribute("data-tooltip", `${modelName} | VRAM: ${size} GB | Max Context: ${(maxContext/1000).toFixed(0)}k tokens`);
        li.innerHTML = `
            <div class="agent-info">
                <div class="agent-name-row">
                    <span class="status-dot active"></span>
                    <span class="agent-name">${modelName}</span>
                </div>
                <div class="context-progress-container">
                    <div class="context-label">
                        <span>Context: ${(currentContext/1000).toFixed(1)}k / ${(maxContext/1000).toFixed(0)}k</span>
                        <span>${contextPercent.toFixed(0)}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${contextPercent}%"></div>
                    </div>
                </div>
            </div>
            <span class="vram-badge">${size.toFixed(1)}GB</span>
        `;
        listContainer.appendChild(li);
    });

    if (renderedCount === 0) {
        listContainer.innerHTML = `<li style="color: var(--text-secondary); font-size: 11px; padding: 4px 0; text-align: center; list-style: none;">No active agents in VRAM</li>`;
    }
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

    if (tabId === "tab-security") {
        const metricsContainer = document.getElementById("security-metrics");
        if (metricsContainer && metricsContainer.innerHTML.trim() === "") {
            runSecurityScan();
        }
    }
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
                <span><i class="fa-regular fa-file-code"></i> ${skill.file}</span>
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

function createTaskRow(task, isActive) {
    const tr = document.createElement("tr");
    
    // Format Temp
    const tempVal = typeof task.temperature === 'number' ? task.temperature.toFixed(2) : task.temperature;
    
    // Format Payload / Objective
    const objective = task.payload && task.payload.objective ? task.payload.objective : "-";
    
    // Status Badge
    const statusClass = `task-status-badge ${task.status.toLowerCase()}`;
    const statusBadge = `<span class="${statusClass}">${task.status}</span>`;
    
    // Action Buttons based on status
    let actionsHtml = "";
    if (isActive) {
        if (task.status === "running" || task.status === "pending") {
            actionsHtml = `
                <div class="task-action-btns">
                    <button class="task-row-btn pause-btn" onclick="pauseTask('${task.task_id}')" title="Pause Task">
                        <i class="fa-solid fa-pause"></i> Pause
                    </button>
                    <button class="task-row-btn cancel-btn" onclick="cancelTask('${task.task_id}')" title="Cancel Task">
                        <i class="fa-solid fa-ban"></i> Cancel
                    </button>
                </div>
            `;
        } else if (task.status === "paused") {
            actionsHtml = `
                <div class="task-action-btns">
                    <button class="task-row-btn resume-btn" onclick="resumeTask('${task.task_id}')" title="Resume Task">
                        <i class="fa-solid fa-play"></i> Resume
                    </button>
                    <button class="task-row-btn cancel-btn" onclick="cancelTask('${task.task_id}')" title="Cancel Task">
                        <i class="fa-solid fa-ban"></i> Cancel
                    </button>
                </div>
            `;
        }
    } else {
        // Completed, Failed, Cancelled
        actionsHtml = `
            <div class="task-action-btns">
                <button class="task-row-btn cancel-btn" onclick="deleteTask('${task.task_id}')" title="Delete Task from History">
                    <i class="fa-solid fa-trash-can"></i> Delete
                </button>
            </div>
        `;
    }
    
    tr.innerHTML = `
        <td style="font-family: var(--font-mono); font-weight: 600;">${task.task_id}</td>
        <td style="font-family: var(--font-mono); color: var(--text-secondary);">${task.execution_id}</td>
        <td><strong style="color: var(--accent-color);">${task.target_agent}</strong></td>
        <td>${statusBadge}</td>
        <td style="text-align: center; font-family: var(--font-mono);">${task.retry_count}</td>
        <td style="text-align: center; font-family: var(--font-mono);">${tempVal}</td>
        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${objective}">${objective}</td>
        <td>${actionsHtml}</td>
    `;
    return tr;
}

async function updateTasksTable() {
    try {
        const response = await fetch("/api/tasks");
        if (!response.ok) return;
        const tasks = await response.json();
        
        // Skip DOM update if data is unchanged to prevent hover flickering
        const tasksJson = JSON.stringify(tasks);
        if (tasksJson === lastTasksJson) return;
        lastTasksJson = tasksJson;
        
        const tbody = document.getElementById("tasks-table-body");
        const historyTbody = document.getElementById("history-tasks-table-body");
        if (!tbody || !historyTbody) return;
        
        tbody.innerHTML = "";
        historyTbody.innerHTML = "";
        
        const activeTasks = tasks.filter(t => ["running", "pending", "paused"].includes(t.status.toLowerCase()));
        const historyTasks = tasks.filter(t => ["completed", "failed", "cancelled"].includes(t.status.toLowerCase()));
        
        // Render Active Tasks
        if (activeTasks.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-secondary); padding: 20px;">No active tasks. Run a simulation to start.</td></tr>`;
        } else {
            activeTasks.forEach(task => {
                tbody.appendChild(createTaskRow(task, true));
            });
        }
        
        // Render History Tasks
        if (historyTasks.length === 0) {
            historyTbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-secondary); padding: 20px;">No task history.</td></tr>`;
        } else {
            historyTasks.forEach(task => {
                historyTbody.appendChild(createTaskRow(task, false));
            });
        }
    } catch (e) {
        console.error("Error updating tasks table:", e);
    }
}

async function pauseTask(taskId) {
    try {
        const response = await fetch("/api/tasks/pause", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ task_id: taskId })
        });
        if (response.ok) {
            updateTasksTable();
        }
    } catch (e) {
        console.error("Error pausing task:", e);
    }
}

async function resumeTask(taskId) {
    try {
        const response = await fetch("/api/tasks/resume", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ task_id: taskId })
        });
        if (response.ok) {
            updateTasksTable();
        }
    } catch (e) {
        console.error("Error resuming task:", e);
    }
}

async function cancelTask(taskId) {
    try {
        const response = await fetch("/api/tasks/cancel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ task_id: taskId })
        });
        if (response.ok) {
            updateTasksTable();
        }
    } catch (e) {
        console.error("Error cancelling task:", e);
    }
}

async function clearAllTasks() {
    if (!confirm("Are you sure you want to clear all tasks and executions from the database?")) return;
    try {
        const response = await fetch("/api/tasks/clear", {
            method: "POST"
        });
        if (response.ok) {
            updateTasksTable();
            fetchStatus();
        }
    } catch (e) {
        console.error("Error clearing tasks:", e);
    }
}

async function resetFactory() {
    if (!confirm("WARNING: This will reset LIEM OS to factory defaults. All database records, settings, telemetry, loaded VRAM models, active providers, and generated simulation files (like finance_tool.py) will be cleared. Proceed?")) return;
    try {
        const response = await fetch("/api/system/reset", {
            method: "POST"
        });
        if (response.ok) {
            // Switch back to console tab
            switchTab('tab-console');
            // Clear current screen logs state
            activeLogs = [];
            document.getElementById("log-lines").innerHTML = "";
            // Reset active provider selector in DOM
            document.getElementById("provider-select").value = "antigravity";
            // Refresh
            fetchStatus();
            updateTasksTable();
        }
    } catch (e) {
        console.error("Error resetting factory defaults:", e);
    }
}

async function deleteTask(taskId) {
    if (!confirm(`Are you sure you want to delete task ${taskId} from history?`)) return;
    try {
        const response = await fetch("/api/tasks/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ task_id: taskId })
        });
        if (response.ok) {
            updateTasksTable();
            fetchStatus();
        }
    } catch (e) {
        console.error("Error deleting task:", e);
    }
}

async function updatePlanList() {
    try {
        const response = await fetch("/api/executions");
        if (!response.ok) return;
        const executions = await response.json();
        
        // Filter executions to only show ACTIVE plans (status is "running")
        const activeExecutions = executions.filter(exec => exec.status === "running");
        
        const execsJson = JSON.stringify(activeExecutions);
        if (execsJson === lastExecutionsJson) return;
        lastExecutionsJson = execsJson;
        
        const container = document.getElementById("plan-list");
        if (!container) return;
        
        container.innerHTML = "";
        if (activeExecutions.length === 0) {
            container.innerHTML = `<li class="plan-item" style="color: var(--text-secondary); font-size: 11px; padding: 4px 0;">No active plans</li>`;
            return;
        }
        
        activeExecutions.forEach(exec => {
            const li = document.createElement("li");
            li.className = "plan-item active";
            li.setAttribute("data-tooltip", `Plan: ${exec.execution_id} (${exec.status})`);
            
            li.innerHTML = `
                <i class="fa-solid fa-diagram-project" style="color: var(--success-color); margin-right: 8px;"></i>
                <span style="font-family: var(--font-mono); font-size: 11px;">${exec.execution_id}</span>
            `;
            container.appendChild(li);
        });
    } catch (e) {
        console.error("Error updating plan list:", e);
    }
}

// Security Guard Integration
async function runSecurityScan() {
    const btn = document.getElementById("btn-run-security");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Scanning...`;
    }

    const grid = document.getElementById("security-grid-container");
    const metrics = document.getElementById("security-metrics");
    
    if (grid) {
        grid.innerHTML = `<div class="log-system running-status"><span class="status-dot"></span><span>Auditing skills in progress...</span></div>`;
    }

    try {
        const response = await fetch("/api/security/scan");
        const data = await response.json();
        
        if (data.status === "success") {
            displaySecurityResults(data);
        } else {
            if (grid) grid.innerHTML = `<div class="log-system failed-status"><span class="status-dot"></span><span>Error: ${data.detail || "Failed to scan"}</span></div>`;
        }
    } catch (error) {
        console.error("Security scan error:", error);
        if (grid) grid.innerHTML = `<div class="log-system failed-status"><span class="status-dot"></span><span>Error connecting to server.</span></div>`;
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-shield-halved"></i> Run Scan`;
        }
    }
}

function displaySecurityResults(data) {
    const metricsContainer = document.getElementById("security-metrics");
    const gridContainer = document.getElementById("security-grid-container");
    
    if (!metricsContainer || !gridContainer) return;
    
    // Update metrics
    const overall = data.overall_status.toLowerCase();
    const overallIcon = overall === "safe" ? "fa-shield-check" : (overall === "warning" ? "fa-triangle-exclamation" : "fa-shield-xmark");
    
    metricsContainer.innerHTML = `
        <div class="security-metric-card ${overall}">
            <i class="fa-solid ${overallIcon}"></i>
            <div class="security-metric-details">
                <span class="security-metric-value" style="text-transform: uppercase;">${data.overall_status}</span>
                <span class="security-metric-label">System Security Status</span>
            </div>
        </div>
        <div class="security-metric-card">
            <i class="fa-solid fa-book-open" style="color: var(--accent-color);"></i>
            <div class="security-metric-details">
                <span class="security-metric-value">${data.metrics.total_skills}</span>
                <span class="security-metric-label">Total Skills Audited</span>
            </div>
        </div>
        <div class="security-metric-card">
            <i class="fa-solid fa-triangle-exclamation" style="color: var(--warning-color);"></i>
            <div class="security-metric-details">
                <span class="security-metric-value">${data.metrics.warning + data.metrics.vulnerable}</span>
                <span class="security-metric-label">Skills with Warnings/Vulnerabilities</span>
            </div>
        </div>
    `;

    // Update report list
    gridContainer.innerHTML = "";
    if (data.reports.length === 0) {
        gridContainer.innerHTML = `<div class="log-system completed-status"><span class="status-dot"></span><span>No skills found in the project root.</span></div>`;
        return;
    }

    data.reports.forEach(report => {
        const card = document.createElement("div");
        card.className = "security-card";
        
        const rec = report.recommendation.toLowerCase();
        const score = report.risk_score;
        const findings = report.findings || [];
        
        let statusClass = "safe";
        if (rec !== "safe" || score > 50) statusClass = "vulnerable";
        else if (score > 30) statusClass = "warning";
        
        let findingsHtml = "";
        if (findings.length > 0) {
            findings.forEach(finding => {
                const isHigh = finding.severity === "HIGH" || finding.severity === "CRITICAL";
                findingsHtml += `
                    <div class="security-finding-item ${isHigh ? 'vulnerable' : 'warning'}">
                        <div class="security-finding-header">
                            <span style="color: ${isHigh ? 'var(--error-color)' : 'var(--warning-color)'}; font-weight: 600;">
                                <i class="fa-solid fa-bug"></i> ${finding.category} (${finding.pattern})
                            </span>
                            <span style="font-size: 10px; color: var(--text-secondary);">${finding.severity} Severity</span>
                        </div>
                        <div class="security-finding-desc">${finding.explanation}</div>
                        ${finding.file ? `<div style="font-size: 10px; margin-bottom: 4px; color: var(--text-secondary);">File: <code>${finding.file}</code>${finding.line ? ` (Line ${finding.line})` : ''}</div>` : ''}
                        ${finding.code_snippet ? `<pre class="security-finding-code"><code>${escapeHtml(finding.code_snippet)}</code></pre>` : ''}
                    </div>
                `;
            });
        } else {
            findingsHtml = `<div style="font-size: 11px; color: var(--text-secondary); margin-top: 8px;"><i class="fa-solid fa-check" style="color: var(--success-color); margin-right: 4px;"></i> No vulnerabilities or roguish behaviors detected.</div>`;
        }

        card.innerHTML = `
            <div class="security-card-header">
                <span class="security-card-title">
                    <i class="fa-solid fa-folder-open" style="color: var(--accent-color);"></i> ${report.skill_name}
                </span>
                <span class="security-status-badge ${statusClass}">
                    Risk Score: ${score}/100
                </span>
            </div>
            <div style="font-size: 12px; color: var(--text-secondary);">Path: <code>${report.path}</code></div>
            ${findingsHtml}
        `;
        gridContainer.appendChild(card);
    });
}

function escapeHtml(text) {
    if (!text) return "";
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
