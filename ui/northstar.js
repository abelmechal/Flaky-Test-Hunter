const $ = (selector) => document.querySelector(selector);
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let bugFixed = false;
let uploadTimer;

function resetUpload() {
  clearInterval(uploadTimer);
  $("#uploadState").classList.add("hidden");
  $("#errorState").classList.add("hidden");
  $("#successState").classList.add("hidden");
  $("#progressBar").style.width = "0%";
  $("#progressBar").classList.remove("stalled");
  $("#percentText").textContent = "0%";
  $("#uploadButton").disabled = false;
  $("#uploadButton").textContent = bugFixed ? "Retry upload" : "Start upload";
}

function startUpload() {
  resetUpload();
  $("#uploadButton").disabled = true;
  $("#uploadButton").textContent = "Uploading…";
  $("#uploadState").classList.remove("hidden");
  $("#uploadTitle").textContent = "Uploading asset…";
  $("#uploadDetail").textContent = "Sending file to the media worker.";
  let progress = 0;
  uploadTimer = setInterval(() => {
    progress = Math.min(bugFixed ? 100 : 82, progress + 4);
    $("#progressBar").style.width = `${progress}%`;
    $("#percentText").textContent = `${progress}%`;
    if (progress === (bugFixed ? 100 : 82)) {
      clearInterval(uploadTimer);
      if (bugFixed) completeUpload();
      else stallUpload();
    }
  }, 80);
}

async function stallUpload() {
  $("#progressBar").classList.add("stalled");
  $("#uploadTitle").textContent = "Waiting for media worker…";
  $("#uploadDetail").textContent = "Upload bytes completed, but no completion event was received.";
  await wait(550);
  $("#uploadState").classList.add("hidden");
  $("#errorState").classList.remove("hidden");
  $("#failureDot").classList.add("show");
  $("#uploadButton").disabled = false;
  $("#uploadButton").textContent = "Retry upload";
}

async function completeUpload() {
  $("#uploadTitle").textContent = "Finalizing asset…";
  $("#uploadDetail").textContent = "Completion event received from media worker.";
  await wait(450);
  $("#uploadState").classList.add("hidden");
  $("#successState").classList.remove("hidden");
  $("#failureDot").classList.remove("show");
  $("#uploadButton").disabled = false;
  $("#uploadButton").textContent = "Upload another";
}

function setAgent(id, state, detail, running) {
  const node = $(id);
  node.querySelector("i").textContent = state;
  node.querySelector("p").textContent = detail;
  node.classList.toggle("running", running);
}

function setDiagnosisProgress(percent, label) {
  $("#diagnosisPercent").textContent = `${percent}%`;
  $("#diagnosisStep").textContent = label;
  $("#diagnosisBar").style.width = `${percent}%`;
}

async function runDiagnosis() {
  $("#diagnosisOverlay").classList.remove("hidden");
  $("#report").classList.add("hidden");
  $("#fixResult").classList.add("hidden");
  $("#diagnosisProgress").classList.remove("hidden");
  setAgent("#diagnosticianAgent", "Running", "Reading upload failure and recent history", true);
  setAgent("#reproducerAgent", "Ready", "Waiting for repro plan", false);
  setDiagnosisProgress(12, "Reading upload failure");

  const request = fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: "upload-progress" }),
  });
  await wait(650);
  setDiagnosisProgress(34, "Building four-step repro plan");
  await wait(650);
  setAgent("#diagnosticianAgent", "Delegated", "Repro plan sent to Agent 02", false);
  setAgent("#reproducerAgent", "Running", "Replaying the upload flow", true);
  setDiagnosisProgress(61, "Reproducer Agent verifying failure");
  await wait(850);
  setDiagnosisProgress(82, "Comparing mixed execution history");

  try {
    const response = await request;
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Diagnosis failed");
    setAgent("#reproducerAgent", "Complete", "Upload completion failure reproduced", false);
    setAgent("#diagnosticianAgent", "Complete", "Root cause and recommendation prepared", false);
    setDiagnosisProgress(100, "Diagnosis complete");
    $("#classification").textContent = data.diagnosis.classification.toUpperCase();
    $("#confidence").textContent = `${data.diagnosis.confidence}% confidence`;
    $("#browserEvidence").textContent = data.verification.reproduced
      ? "Failure reproduced at step 4 of 4"
      : "Reported failure not reproduced";
    await wait(350);
    $("#report").classList.remove("hidden");
  } catch (error) {
    setDiagnosisProgress(100, "Safe fallback diagnosis complete");
    $("#report").classList.remove("hidden");
  }
}

function applyFix() {
  bugFixed = true;
  $("#buildPill").textContent = "Patched build";
  $("#buildPill").classList.add("fixed");
  $("#report").classList.add("hidden");
  $("#diagnosisProgress").classList.add("hidden");
  $("#fixResult").classList.remove("hidden");
  $("#failureDot").classList.remove("show");
  $("#uploadButton").textContent = "Retry upload";
  setTimeout(() => $("#diagnosisOverlay").classList.add("hidden"), 1200);
}

$("#uploadButton").addEventListener("click", startUpload);
$("#diagnoseButton").addEventListener("click", runDiagnosis);
$("#errorDiagnose").addEventListener("click", runDiagnosis);
$("#closeDiagnosis").addEventListener("click", () => $("#diagnosisOverlay").classList.add("hidden"));
$("#applyFix").addEventListener("click", applyFix);
