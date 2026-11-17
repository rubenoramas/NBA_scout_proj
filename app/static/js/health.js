// Calls GET /api/health and shows the result on the page.
// Three states: loading, success (or a database problem), and request error.

const statusEl = document.getElementById("status");
const detailsEl = document.getElementById("details");
const retryBtn = document.getElementById("retry");

function showStatus(text, kind) {
  statusEl.textContent = text;
  statusEl.className = "status " + kind;
}

function showDetails(lines) {
  detailsEl.innerHTML = "";
  for (const line of lines) {
    const li = document.createElement("li");
    li.textContent = line;
    detailsEl.appendChild(li);
  }
  detailsEl.hidden = lines.length === 0;
}

async function checkHealth() {
  showStatus("Checking the API and database...", "loading");
  showDetails([]);
  retryBtn.hidden = true;
  retryBtn.disabled = true;

  try {
    // Stop waiting after 8 seconds so the page never hangs.
    const response = await fetch("/api/health", { signal: AbortSignal.timeout(8000) });
    const data = await response.json();

    const aiLine = data.ai_key_set
      ? "AI reports: API key found."
      : "AI reports: add an API key to .env to turn on AI features. Everything else works without it.";

    if (data.mongo === "ok") {
      showStatus("Everything is working.", "ok");
      showDetails(["API: running.", "Database: connected.", aiLine]);
    } else {
      showStatus(data.message || "The database is not answering.", "error");
      showDetails(["API: running.", "Database: not reachable. Check that the mongo container is up.", aiLine]);
      retryBtn.hidden = false;
    }
  } catch (err) {
    const why = err.name === "TimeoutError"
      ? "The API took too long to answer."
      : "Could not reach the API. Check that the web container is running.";
    showStatus(why, "error");
    retryBtn.hidden = false;
  } finally {
    retryBtn.disabled = false;
  }
}

retryBtn.addEventListener("click", checkHealth);
checkHealth();
