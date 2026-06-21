const $ = (selector) => document.querySelector(selector);
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const scenarios = {
  "upload-progress": {
    section:"Media",page:"New asset",eyebrow:"Media pipeline",title:"Upload a new asset",lead:"Files are processed and optimized automatically.",
    fields:[["File name","product-demo.mp4"],["Collection","Product launches"]],icon:"MP4",item:"product-demo.mp4",detail:"128.4 MB · H.264 video",
    action:"Start upload",running:"Uploading asset…",runningDetail:"Sending file to the media worker.",stall:82,
    error:"Upload stalled at 82%",errorDetail:"The completion event was never received from the media worker.",
    observed:"Upload completion state not visible within 5000ms",cause:"Race condition: the test waits on a UI timeout instead of the media worker's completion event.",
    fix:"Subscribe to the upload-completion event and render the final state only after the worker confirms processing.",
    success:"Upload complete",successDetail:"product-demo.mp4 is ready in Product launches."
  },
  "checkout-confirmation": {
    section:"Orders",page:"Checkout",eyebrow:"Payment pipeline",title:"Complete customer checkout",lead:"Authorize payment and create a confirmed order.",
    fields:[["Customer email","buyer@example.com"],["Order total","$213.93"]],icon:"PAY",item:"Order #NS-4821",detail:"Visa ending 4242 · Express checkout",
    action:"Submit payment",running:"Authorizing payment…",runningDetail:"Waiting for the confirmed order event.",stall:76,
    error:"Confirmation never appeared",errorDetail:"Payment succeeded, but #order-confirmation was not rendered.",
    observed:"Element #order-confirmation not visible within 5000ms",cause:"The UI renders from an authorization response before the confirmed order event arrives.",
    fix:"Await the confirmed order event and render confirmation from the durable order state.",
    success:"Order confirmed",successDetail:"Order #NS-4821 was created and the receipt is visible."
  },
  "login-redirect": {
    section:"Identity",page:"Sign in",eyebrow:"Authentication",title:"Sign in to Northstar",lead:"Authenticate and continue to the workspace dashboard.",
    fields:[["Work email","engineer@northstar.dev"],["Authentication","Organization SSO"]],icon:"SSO",item:"Northstar workspace",detail:"OAuth 2.0 · Production callback",
    action:"Sign in securely",running:"Authenticating…",runningDetail:"Callback succeeded; waiting for dashboard redirect.",stall:68,
    error:"Redirect failed",errorDetail:"Authentication succeeded, but #dashboard-shell never loaded.",
    observed:"Dashboard redirect missing after successful authentication",cause:"The callback handler drops the return path after exchanging the authorization code.",
    fix:"Preserve the validated return path and navigate after the session cookie is committed.",
    success:"Dashboard loaded",successDetail:"Authentication completed and the workspace dashboard is visible."
  },
  "search-results": {
    section:"Catalog",page:"Search",eyebrow:"Search intelligence",title:"Search the product catalog",lead:"Return suggestions for the latest customer query.",
    fields:[["Search query","wireless keyboard"],["Index","Products · US"]],icon:"⌕",item:"Latest query",detail:"wireless keyboard · 3 expected results",
    action:"Search catalog",running:"Loading suggestions…",runningDetail:"Waiting for the latest search response.",stall:55,
    error:"Suggestions did not render",errorDetail:"A stale request replaced the latest #search-results response.",
    observed:"Search suggestions failed to appear within 5000ms",cause:"Out-of-order network responses allow a stale query to overwrite the latest result set.",
    fix:"Cancel stale requests and render results only when the response matches the active query.",
    success:"Suggestions loaded",successDetail:"Three keyboard suggestions are visible for the latest query."
  }
};

let scenarioId = "upload-progress";
let bugFixed = false;
let timer;
const scenario = () => scenarios[scenarioId];
const text = (selector, value) => { $(selector).textContent = value; };

function renderScenario(id) {
  scenarioId=id; bugFixed=false; clearInterval(timer);
  document.querySelectorAll(".scenario-nav").forEach(n=>n.classList.toggle("active",n.dataset.scenario===id));
  const s=scenario();
  text("#breadcrumbSection",s.section); text("#breadcrumbPage",s.page); text("#scenarioEyebrow",s.eyebrow);
  text("#scenarioTitle",s.title); text("#scenarioLead",s.lead);
  text("#fieldOneLabel",s.fields[0][0]); $("#fieldOne").value=s.fields[0][1];
  text("#fieldTwoLabel",s.fields[1][0]); $("#fieldTwo").value=s.fields[1][1];
  text("#itemIcon",s.icon); text("#itemTitle",s.item); text("#itemDetail",s.detail);
  text("#visibleErrorTitle",s.error); text("#visibleErrorDetail",s.errorDetail); text("#observedError",s.observed);
  text("#rootCause",s.cause); text("#recommendedFix",s.fix); text("#upload-complete",s.success); text("#successDetail",s.successDetail);
  text("#buildPill","Buggy build"); $("#buildPill").classList.remove("fixed"); resetRun();
}

function resetRun() {
  clearInterval(timer); ["#uploadState","#errorState","#successState"].forEach(id=>$(id).classList.add("hidden"));
  $("#progressBar").style.width="0%"; $("#progressBar").classList.remove("stalled"); text("#percentText","0%");
  $("#uploadButton").disabled=false; text("#uploadButton",bugFixed?`Retry ${scenario().action.toLowerCase()}`:scenario().action);
  $("#failureDot").classList.remove("show");
}

function startRun() {
  resetRun(); const s=scenario(); $("#uploadButton").disabled=true; text("#uploadButton","Running…");
  $("#uploadState").classList.remove("hidden"); text("#uploadTitle",s.running); text("#uploadDetail",s.runningDetail);
  let p=0; timer=setInterval(()=>{p=Math.min(bugFixed?100:s.stall,p+4);$("#progressBar").style.width=`${p}%`;text("#percentText",`${p}%`);
    if(p===(bugFixed?100:s.stall)){clearInterval(timer);bugFixed?completeRun():failRun();}},75);
}
async function failRun(){ $("#progressBar").classList.add("stalled");await wait(450);$("#uploadState").classList.add("hidden");$("#errorState").classList.remove("hidden");$("#failureDot").classList.add("show");$("#uploadButton").disabled=false;text("#uploadButton",`Retry ${scenario().action.toLowerCase()}`); }
async function completeRun(){ text("#uploadTitle","Verifying patched behavior…");await wait(400);$("#uploadState").classList.add("hidden");$("#successState").classList.remove("hidden");$("#uploadButton").disabled=false;text("#uploadButton","Run again"); }
function setAgent(id,state,detail,running){const n=$(id);n.querySelector("i").textContent=state;n.querySelector("p").textContent=detail;n.classList.toggle("running",running);}
function setProgress(p,label){text("#diagnosisPercent",`${p}%`);text("#diagnosisStep",label);$("#diagnosisBar").style.width=`${p}%`;}

async function diagnose(){
  $("#diagnosisOverlay").classList.remove("hidden");$("#report").classList.add("hidden");$("#fixResult").classList.add("hidden");$("#commandConsole").classList.add("hidden");$("#diagnosisProgress").classList.remove("hidden");
  setAgent("#diagnosticianAgent","Running","Reading failure and recent execution history",true);setAgent("#reproducerAgent","Ready","Waiting for repro plan",false);setProgress(12,"Reading application failure");
  const request=fetch("/api/run",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scenario_id:scenarioId})});
  await wait(550);setProgress(34,"Building reproducible browser plan");await wait(550);setAgent("#diagnosticianAgent","Delegated","Repro plan sent to Agent 02",false);
  setAgent("#reproducerAgent","Running","Replaying the failing UI flow",true);setProgress(63,"Reproducer Agent verifying failure");
  const response=await request;const data=await response.json();setAgent("#reproducerAgent","Complete","Failure evidence captured",false);setAgent("#diagnosticianAgent","Complete","Root cause and repair prepared",false);setProgress(100,"Diagnosis complete");
  text("#classification",data.diagnosis.classification.toUpperCase());text("#confidence",`${data.diagnosis.confidence}% confidence`);text("#browserEvidence",data.verification.reproduced?"Failure reproduced at step 4 of 4":"Intermittent failure not reproduced in latest run");
  await wait(250);$("#report").classList.remove("hidden");
}

async function applyFix(){
  $("#commandConsole").classList.remove("hidden");$("#commandOutput").textContent="$ preparing isolated remediation workspace...\n";$("#applyFix").disabled=true;
  const response=await fetch("/api/fix",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scenario_id:scenarioId})});const result=await response.json();
  for(const command of result.commands||[]){$("#commandOutput").textContent+=`\n$ ${command}\n`;await wait(500);}
  $("#commandOutput").textContent+=result.verified?"\n✓ patch verification passed\n✓ fixed build activated for this session":"\n✗ verification failed";
  if(!result.verified){$("#applyFix").disabled=false;return;}bugFixed=true;text("#buildPill","Verified patch");$("#buildPill").classList.add("fixed");await wait(500);
  $("#report").classList.add("hidden");$("#diagnosisProgress").classList.add("hidden");$("#fixResult").classList.remove("hidden");$("#failureDot").classList.remove("show");$("#applyFix").disabled=false;text("#uploadButton",`Retry ${scenario().action.toLowerCase()}`);
  setTimeout(()=>$("#diagnosisOverlay").classList.add("hidden"),1400);
}

document.querySelectorAll(".scenario-nav").forEach(n=>n.addEventListener("click",()=>renderScenario(n.dataset.scenario)));
$("#uploadButton").addEventListener("click",startRun);$("#diagnoseButton").addEventListener("click",diagnose);$("#errorDiagnose").addEventListener("click",diagnose);
$("#closeDiagnosis").addEventListener("click",()=>$("#diagnosisOverlay").classList.add("hidden"));$("#applyFix").addEventListener("click",applyFix);
renderScenario(scenarioId);
