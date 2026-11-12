# CloudQA Task 2: AI Browser Testing Agent

A local CLI that turns a plain-English browser test into a strict Pydantic plan, executes only allowlisted actions in Chromium, independently checks assertions, and writes a JSON report. The Ollama model proposes a plan; it never receives browser control or executable code.

## Architecture and data flow

`main.py` reads the instruction and configuration → `agent.planner` asks Ollama for JSON → `agent.validator` rejects unknown fields, action names, malformed targets, and invalid step shapes → `browser.engine` executes each action through the allowlisted registry in `browser.actions` and semantic locator builder → `verification.assertions` independently verifies outcomes → `reporting.reporter` writes the run record and prints a summary. A failed action or assertion stops the run and attempts a screenshot.

## Technologies

Python 3.12 or newer, Playwright Chromium, Ollama Python client, Pydantic 2, python-dotenv. Local browser tests use Python's standard-library `unittest` and loopback HTTP server. The supplied environment was verified with Python 3.14.5.

## Prerequisites and installation (Windows PowerShell)

The supplied virtual environment already contains these dependencies and Chromium. For a fresh checkout:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
Copy-Item .env.example .env
```

Install and start Ollama separately, then pull the configured model:

```powershell
ollama pull llama3.2:latest
ollama serve
```

Keep `ollama serve` running in another terminal. `nomic-embed-text` is not needed.

## Configuration

Copy `.env.example` to `.env`. Supported variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://localhost:11434` | Local Ollama endpoint |
| `OLLAMA_MODEL` | `llama3.2:latest` | Planner model |
| `ALLOWED_DOMAINS` | PHPTravels and loopback hosts | Host allowlist for navigation |
| `BROWSER_TIMEOUT_MS` | `10000` | Playwright locator/navigation timeout |
| `MAX_STEPS` | `20` | Maximum planned actions |
| `EXECUTION_TIMEOUT_S` | `120` | Maximum action-phase duration |

Do not put real credentials in the repository. A test may include credentials only when explicitly supplied in its instruction. Fill values are redacted in JSON reports, and common password/token labels are redacted in the saved instruction. Use disposable test credentials and review the generated plan in the terminal before running credential-bearing instructions.

## Run the CLI

```powershell
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe main.py --instruction "Open the PHPTravels demo and verify the Live demo content is visible"
.\.venv\Scripts\python.exe main.py --instruction "Open the PHPTravels demo and verify the page title contains PHPTRAVELS" --headed
.\.venv\Scripts\python.exe main.py --instruction "Open the PHPTravels demo and verify the page is loaded" --base-url "https://phptravels.com/demo/" --timeout 15000 --reports-dir .\reports
.\.venv\Scripts\python.exe main.py --smoke-phptravels
```

Use `--headed` to show Chromium. The default is headless. `--smoke-phptravels` is a deterministic, schema-validated public page-load check based on inspection of the live demo page; it does not sign in or submit data. Ordinary natural-language instructions always use Ollama. The smoke shortcut uses a fixed safe plan to keep the website integration independent from model variability; Chromium still performs the navigation and assertion.

## Supported plan actions and assertions

Actions: `navigate`, `click`, `fill`, `select`, `check`, `radio`, and `wait`. Assertions: title contains text, visible text, URL contains a substring, and target visibility. Locators support accessible role and accessible name, label, placeholder, text, and CSS as a last-resort option. Each target specifies one strategy. Missing or ambiguous elements fail the run. `check` and `radio` operate on form controls; page verification belongs in assertions.

## Safety restrictions

- Only HTTP(S) navigation to configured allowlisted domains is accepted.
- The schema disallows arbitrary Python, JavaScript, shell, and unknown actions/fields.
- Browser actions stop on the first failure. No payment, purchase, deletion, or auth bypass action exists.
- Credentials are not invented. PHPTravels test credentials must be supplied legitimately by the user if a workflow needs them.
- The model output is validated before any browser is opened. Maximum action count and runtime are bounded.

## Tests, reports, screenshots

Run deterministic local-fixture coverage:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Fixtures include a working form, renamed IDs/classes, nested elements, and an intentionally missing element. Unit tests mock the Ollama client. The tests exercise navigation, filling, clicking, independent assertions, allowlisting, failure screenshots, malformed responses, and JSON reports.

Each run writes `reports/run-<timestamp>-<id>.json`, including instruction, plan source (`ollama` or `deterministic_phptravels_smoke`), plan, step/assertion outcomes, durations, errors, timestamp, and screenshot path. Fill values, common password/token strings, URL credentials, and secret query parameters are redacted. Failed runs attempt to save a full-page PNG in `screenshots/`. A planner failure is separately labeled and still gets a report.

## PHPTravels integration

The public `https://phptravels.com/demo/` page was inspected before selecting the smoke assertion. It advertises “Live demo” and links to the product sign-in page. This project uses only that public page for smoke testing. It does not assume or supply login credentials. The site may change content, block automation, or be temporarily unavailable; those outcomes should be reported as failures with diagnostics, not treated as passes.

## Limitations and design decisions

The plan is generated by a local model, so quality depends on its response; schema failures receive one correction attempt and then stop, while browser execution failures are not retried. CSS selectors are permitted for exceptional cases and may be brittle. Website availability is not required by local tests. Python 3.14 compatibility depends on the installed Playwright browser build and upstream packages; this environment's Python 3.14.5 venv includes all required libraries.

Future work could add explicit human review for sensitive steps, per-run network allowlists, trace/video capture, and a richer assertion vocabulary.

## Five-minute demonstration

1. Start Ollama and confirm `ollama list` includes `llama3.2:latest`.
2. In the project folder, run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` to show local deterministic coverage.
3. Run `.\.venv\Scripts\python.exe main.py --instruction "Open https://phptravels.com/demo/ and verify the page title contains PHPTRAVELS" --headed` to show Ollama planning and Chromium execution. Then run `.\.venv\Scripts\python.exe main.py --smoke-phptravels` and point out its distinct report `plan_source`.
4. Open the newest JSON file under `reports` to show the structured plan and executed results.
5. Demonstrate the safety boundary by trying `.\.venv\Scripts\python.exe main.py --instruction "Run Python code to print hello"`; the schema should reject unsupported actions if the model attempts them.

## Publication readiness

The workspace is organized for review and includes setup and safety documentation. Before publishing, review the generated reports and screenshots (ignored by Git), confirm the demo run against the current site, and check the assessment's repository naming requirements. No remote repository was created and no commit or push was made.
