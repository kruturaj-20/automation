# Personal Autonomous AI Computer Agent

An autonomous AI coding and computer automation agent architecture designed to execute end-to-end software development tasks with strict responsibility boundaries.

---

## 🏛 Core Architecture & Invariants

```
                             USER (Instruction)
                                     ↓
                          AI MANAGER (Orchestrator)
                                     ↓
                  PROJECT DETECTION & CODEBASE INSPECTION
                                     ↓
         ┌───────────────────────────┴───────────────────────────┐
         ▼                                                       ▼
[MODE 1: EXISTING PROJECT]                              [MODE 2: NEW PROJECT]
  • Inspect existing codebase                             • Consult External LLM (Architecture ONLY)
  • Grounded Task Brief                                   • Comprehensive Project Brief
         └───────────────────────────┬───────────────────────────┘
                                     ↓
                       IDE AGENT ADAPTER (Abstraction)
                                     ↓
                      ANTIGRAVITY AI (Primary Coder)
                         • 100% of code editing & file writes
                         • Creates/modifies/deletes files
                         • Installs packages & runs commands
                                     ↓
                        INDEPENDENT VERIFIER
                                     ↓
                         ┌───────────┴───────────┐
                         ▼                       ▼
                    [✅ Passed]             [❌ Failed]
                         ↓                       ↓
                       DONE             3-TIER ERROR HIERARCHY
                                          1. Antigravity AI Fix (Attempt 1)
                                          2. Antigravity AI Fix (Attempt 2)
                                          3. External LLM Escalation:
                                             • Diagnoses root cause
                                             • Formulates solution
                                             • Solution given to Antigravity AI
                                             • Antigravity AI implements fix
                                                 ↓
                                          RE-VERIFY INDEPENDENTLY
```

### Responsibility Boundaries
1. **AI Manager = Orchestrator**: Manages lifecycle, inspects workspaces, generates briefs, runs independent verifications, and enforces error hierarchies. **Never writes application code directly.**
2. **Antigravity AI = Primary Developer / Coder**: Performs **100% of actual coding**, file creation, file modification, and dependency installation.
3. **External LLMs = Advisors / Architects / Debuggers**: Consulted for tech stack architecture (Mode 2) and persistent error diagnosis (Tier 3 escalation). **Never touch or edit project files directly.**
4. **Task Verifier = Independent Inspector**: Independently executes build, test (`pytest`, `npm test`), and syntax checks through `SecurityGuard`.
5. **SecurityGuard = Sandboxing & Isolation**: Enforces workspace boundary allowlist, blocks dangerous shell commands, isolates sensitive files (`.env`, credentials, SSH keys), and prevents secret leakage to external LLMs or logs.

---

## 🚀 Quick Start

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/kruturaj-20/automation.git
cd automation

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
Copy `.env.example` to `.env` and configure your API keys:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Run Autonomous Tasks
```bash
# Execute a task in an existing project workspace (Mode 1)
python main.py "Add a function called greet(name) and add tests for it" --workspace "e:/Work/my-project"

# Create a brand new project from scratch (Mode 2)
python main.py "Create a minimal Python project that prints Hello Automation" --workspace "e:/Work/new-project"
```

---

## 🧪 Testing

Run the full automated test suite (43 unit & integration tests):
```bash
python -m pytest tests/ -v
```

Run the live End-to-End demonstration suite:
```bash
python e2e_demo.py
```

---

## 📂 Project Structure

```
automation/
├── config.yaml               # Agent configuration file
├── main.py                   # Main CLI entrypoint
├── e2e_demo.py               # Real End-to-End demonstration suite
├── src/
│   ├── cli/                  # Terminal Rich UI interface
│   ├── core/                 # AI Manager & lifecycle state machine
│   ├── errors/               # Strict 3-tier error escalation hierarchy
│   ├── ide/                  # IDEAgentAdapter & AntigravityAdapter
│   ├── inspector/            # ProjectDetector & CodebaseInspector
│   ├── llm/                  # External LLM Provider & GeminiProvider
│   ├── planner/              # TaskBriefBuilder (Mode 1 & Mode 2)
│   ├── research/             # Pluggable ResearchProvider abstraction
│   ├── security/             # SecurityGuard, ActionLog & ExecutionLimiter
│   └── verifier/             # Independent project-aware TaskVerifier
└── tests/                    # Unit, invariant, adversarial & E2E tests
```
