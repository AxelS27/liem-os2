// Global State Tracking
let activeLogs = [];
let isHITLShowing = false;

// Polling interval
const API_INTERVAL = 1000;

document.addEventListener("DOMContentLoaded", () => {
    // Initial fetch and start interval
    fetchStatus();
    setInterval(fetchStatus, API_INTERVAL);
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
    const mcpContainer = document.getElementById("mcp-list");
    mcpContainer.innerHTML = "";
    
    servers.forEach(server => {
        const li = document.createElement("li");
        li.className = `mcp-item ${server.status}`;
        li.innerHTML = `
            <i class="fa-solid fa-link"></i>
            <span>${server.name} (${server.status})</span>
        `;
        mcpContainer.appendChild(li);
    });
}

function updateConsoleLogs(logs) {
    const logContainer = document.getElementById("log-lines");
    
    // Check if new logs arrived
    if (logs.length === activeLogs.length) return;

    // Append new lines
    const newLines = logs.slice(activeLogs.length);
    newLines.forEach(line => {
        const div = document.createElement("div");
        div.className = "log-line";
        div.innerHTML = parseLogFormatting(line);
        logContainer.appendChild(div);
    });

    activeLogs = [...logs];

    // Auto-scroll to bottom of console
    const consoleBody = document.getElementById("console-body");
    consoleBody.scrollTop = consoleBody.scrollHeight;
}

function parseLogFormatting(line) {
    // Style prefixes like [Axel], [VRAM], [User]
    const patterns = [
        { regex: /^(\[User\])(.*)$/, class: "prefix-user" },
        { regex: /^(\[Axel\])(.*)$/, class: "prefix-axel" },
        { regex: /^(\[Planner\])(.*)$/, class: "prefix-planner" },
        { regex: /^(\[VRAM\])(.*)$/, class: "prefix-vram" },
        { regex: /^(\[Scheduler\])(.*)$/, class: "prefix-scheduler" },
        { regex: /^(\[Validator\])(.*)$/, class: "prefix-validator" },
        { regex: /^(\[Recovery\])(.*)$/, class: "prefix-recovery" }
    ];

    for (const p of patterns) {
        const match = line.match(p.regex);
        if (match) {
            return `<strong class="${p.class}">${match[1]}</strong>${match[2]}`;
        }
    }
    return line;
}

async function checkHITLStatus() {
    try {
        const response = await fetch("/api/tasks");
        if (!response.ok) return;

        const tasks = await response.json();
        // Look for any active task in 'failed' status representing the loop failure
        const hitlTask = tasks.find(t => t.status === "failed" && t.task_id === "T-999");
        
        const card = document.getElementById("hitl-card");
        if (hitlTask && !isHITLShowing) {
            card.classList.remove("hidden");
            isHITLShowing = true;
            // Scroll to the bottom to focus on action
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
    const prompt = input.value.strip ? input.value.strip() : input.value;
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
