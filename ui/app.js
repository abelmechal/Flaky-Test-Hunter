const $ = (selector) => document.querySelector(selector);
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const runButton = $("#runButton");
const runAgain = $("#runAgain");
const results = $("#results");
const progressBar = $("#progressBar");
const progressTitle = $("#progressTitle");
const progressTime = $("#progressTime");
const progressSteps = [...document.querySelectorAll(".progress-steps span")];
const errorToast = $("#errorToast");
let timer;
let startedAt;
let scenarios = [];
let selectedScenarioId;

async function loadFixture() {
  const response = await fetch("/api/fixture");
  const data = await response.json();
  scenarios = data.scenarios;
  selectedScenarioId = data.selected_id;
  renderScenarioGrid();
  selectScenario(selectedScenarioId);
}

function renderScenarioGrid() {
  const grid = $("#scenarioGrid");
  grid.innerHTML = "";
  scenarios.forEach((scenario, index) => {
    const button = document.createElement("button");
    button.className = "scenario-button";
    button.dataset.scenarioId = scenario.id;
    button.innerHTML = `
      <span class="scenario-top">
        <span class="scenario-index">0${index + 1}</span>
        <span class="severity ${scenario.severity.toLowerCase()}">${scenario.severity}</span>
      </span>
      <strong>${scenario.label}</strong>
      <small>${scenario.suite}</small>
    `;
    button.addEventListener("click", () => selectScenario(scenario.id));
    grid.appendChild(button);
  });
}

function selectScenario(id) {
  selectedScenarioId = id;
  const scenario = scenarios.find((item) => item.id === id);
  if (!scenario) return;
  document.querySelectorAll(".scenario-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.scenarioId === id);
  });
  $("#issueId").textContent = scenario.issue.issue_id;
  $("#testName").textContent = scenario.issue.test_name.replace(" > ", " › ");
  $("#expectedFailure").textContent = scenario.issue.expected_failure;
  $("#recentRuns").textContent = scenario.issue.run_count_recent;
  $("#stepCount").textContent = scenario.issue.steps.length;
  $("#severity").textContent = scenario.severity;
  results.classList.add("hidden");
  setProgress(0, "Ready to investigate", 0);
  setAgent("diagnostician", "Ready", "Waiting for diagnosis request", false);
  setAgent("reproducer", "Ready", "Waiting for delegated plan", false);
}

function setAgent(agent, state, task, active = false) {
  const stateNode = $(`#${agent}State`);
  const card = stateNode.closest(".agent-card");
  stateNode.textContent = state;
  stateNode.classList.toggle("running", active);
  card.querySelector(".agent-task span").textContent = task;
  card.querySelector(".agent-task").classList.toggle("active", active);
}

function setProgress(index, title, percent) {
  progressTitle.textContent = title;
  progressBar.style.width = `${percent}%`;
  progressSteps.forEach((step, i) => step.classList.toggle("active", i <= index));
}

function startTimer() {
  startedAt = Date.now();
  clearInterval(timer);
  timer = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startedAt) / 1000);
    progressTime.textContent = `00:${String(elapsed).padStart(2, "0")}`;
  }, 250);
}

function renderHistory(history) {
  const visual = $("#historyVisual");
  visual.innerHTML = "";
  history.items.forEach((item, index) => {
    const bar = document.createElement("span");
    bar.className = item.reproduced ? "fail" : "pass";
    bar.style.height = `${34 + ((index * 17) % 30)}px`;
    bar.style.animationDelay = `${index * 50}ms`;
    bar.title = `${item.reproduced ? "Failed" : "Passed"} · ${item.timestamp}`;
    visual.appendChild(bar);
  });
  $("#failCount").textContent = history.fail_count;
  $("#passCount").textContent = history.pass_count;
}

function renderResult(data) {
  $("#verificationBadge").textContent = data.run.live_browserbase
    ? "Live session completed"
    : "Local fallback completed";
  $("#delegationProof").textContent = data.run.delegated
    ? "Multi-agent delegation verified"
    : data.run.live_browserbase
      ? "Serverless Reproducer verified"
      : "Safe local fallback verified";
  const reproduced = data.verification.reproduced;
  $("#browserScenario").textContent = selectedScenarioId.replaceAll("-", " ").toUpperCase();
  $("#browserPath").textContent = `${selectedScenarioId}.demo / verification`;
  $("#browserTitle").textContent = data.verification.browser_title;
  $("#browserDetail").textContent = data.verification.browser_detail;
  $("#expectedElement").textContent = data.verification.expected_element;
  $("#elementStatus").textContent = reproduced ? "NOT FOUND" : "FOUND";
  $("#elementEvidence").classList.toggle("found", !reproduced);
  $("#resultStatus").textContent = reproduced ? "Failure reproduced" : "Failure not reproduced";
  $("#resultStatus").classList.toggle("red", reproduced);
  $("#resultStatus").style.color = reproduced ? "" : "var(--green)";
  $("#failedStep").textContent = data.verification.failed_step
    ? `Step ${data.verification.failed_step} of ${data.verification.total_steps}`
    : "Plan completed";
  $("#duration").textContent = `${(data.run.duration_ms / 1000).toFixed(1)}s`;
  $("#confidence").textContent = `${data.diagnosis.confidence}%`;
  $("#confidenceBar").style.width = `${data.diagnosis.confidence}%`;
  $("#conclusion").textContent = data.diagnosis.conclusion;
  $("#recommendation").textContent = data.diagnosis.recommendation;
  $("#diagnosisLabel").textContent = data.diagnosis.classification.toUpperCase();
  $("#diagnosisLabel").className = `diagnosis-label ${
    data.diagnosis.classification === "Likely regression"
      ? "regression"
      : data.diagnosis.classification === "Inconclusive"
        ? "inconclusive"
        : ""
  }`;
  $("#browserProof").textContent = reproduced
    ? "Browser failure reproduced"
    : "Browser verification passed";
  const mixed = data.history.pass_count > 0 && data.history.fail_count > 0;
  $("#historyBadge").textContent = mixed
    ? "Mixed outcomes"
    : data.history.fail_count > 0
      ? "Consistent failures"
      : "Consistent passes";
  $("#historyProof").textContent = mixed
    ? "Mixed historical outcomes found"
    : data.history.fail_count > 0
      ? "Deterministic failure pattern found"
      : "Stable passing history found";
  const sessionLink = $("#sessionLink");
  if (data.verification.session_url) {
    sessionLink.href = data.verification.session_url;
    sessionLink.classList.remove("hidden");
  } else {
    sessionLink.classList.add("hidden");
  }
  renderHistory(data.history);
  results.classList.remove("hidden");
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function runDiagnosis() {
  errorToast.classList.add("hidden");
  results.classList.add("hidden");
  runButton.disabled = true;
  runButton.querySelector("strong").textContent = "Diagnosis running…";
  startTimer();
  setAgent("diagnostician", "Running", "Parsing Sentry issue and building repro plan", true);
  setAgent("reproducer", "Ready", "Waiting for delegated plan", false);
  setProgress(0, "Ingesting Sentry issue", 12);

  const scenario = scenarios.find((item) => item.id === selectedScenarioId);
  const request = fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: selectedScenarioId }),
  });
  await wait(650);
  setProgress(1, `Repro plan frozen · ${scenario.issue.steps.length} steps`, 30);
  await wait(650);
  setAgent("diagnostician", "Delegated", "Repro plan sent to Agent 02", false);
  setAgent("reproducer", "Running", "Executing live Browserbase session", true);
  setProgress(2, "Browserbase is verifying the failure", 56);
  await wait(900);
  setProgress(3, "Comparing recent pass/fail history", 78);

  try {
    const response = await request;
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Diagnosis failed");
    setAgent("reproducer", "Complete", data.verification.notes, false);
    setAgent("diagnostician", "Complete", "Evidence classified and recommendation prepared", false);
    setProgress(4, `Diagnosis complete · ${data.diagnosis.classification}`, 100);
    clearInterval(timer);
    progressTime.textContent = `${(data.run.duration_ms / 1000).toFixed(1)}s`;
    renderResult(data);
  } catch (error) {
    clearInterval(timer);
    setProgress(2, "Diagnosis could not complete", 56);
    setAgent("reproducer", "Error", "Reproducer request failed", false);
    errorToast.textContent = error.message;
    errorToast.classList.remove("hidden");
  } finally {
    runButton.disabled = false;
    runButton.querySelector("strong").textContent = "Run live diagnosis";
  }
}

runButton.addEventListener("click", runDiagnosis);
runAgain.addEventListener("click", runDiagnosis);
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && !runButton.disabled) runDiagnosis();
});

loadFixture().catch(() => {
  $("#issueId").textContent = "Fixture unavailable";
});
