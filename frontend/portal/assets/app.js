const state = {
  activeBuild: null,
  products: [],
  builds: [],
};

const storageKeys = {
  apiKey: "urgp.portal.apiKey",
  userId: "urgp.portal.userId",
};

const elements = {
  apiKey: document.getElementById("api-key"),
  userId: document.getElementById("user-id"),
  refreshAll: document.getElementById("refresh-all"),
  saveCredentials: document.getElementById("save-credentials"),
  statusBanner: document.getElementById("status-banner"),
  metricsGrid: document.getElementById("metrics-grid"),
  productsList: document.getElementById("products-list"),
  productsCount: document.getElementById("products-count"),
  buildsList: document.getElementById("builds-list"),
  buildsCount: document.getElementById("builds-count"),
  buildDetail: document.getElementById("build-detail"),
  verifySelected: document.getElementById("verify-selected"),
  subscriptionForm: document.getElementById("subscription-form"),
  subscriptionProduct: document.getElementById("subscription-product"),
  subscriptionRelease: document.getElementById("subscription-release"),
  subscriptionChannel: document.getElementById("subscription-channel"),
  subscriptionWebhook: document.getElementById("subscription-webhook"),
  subscriptionsList: document.getElementById("subscriptions-list"),
  refreshSubscriptions: document.getElementById("refresh-subscriptions"),
  metricTemplate: document.getElementById("metric-template"),
};

function bootstrap() {
  elements.apiKey.value = localStorage.getItem(storageKeys.apiKey) || "";
  elements.userId.value = localStorage.getItem(storageKeys.userId) || "";

  elements.refreshAll.addEventListener("click", refreshDashboard);
  elements.saveCredentials.addEventListener("click", saveCredentials);
  elements.verifySelected.addEventListener("click", verifySelectedBuild);
  elements.subscriptionForm.addEventListener("submit", createSubscription);
  elements.refreshSubscriptions.addEventListener("click", refreshSubscriptions);

  if (elements.apiKey.value) {
    refreshDashboard();
  }
}

function saveCredentials() {
  localStorage.setItem(storageKeys.apiKey, elements.apiKey.value.trim());
  localStorage.setItem(storageKeys.userId, elements.userId.value.trim());
  setBanner("Credentials saved locally for this browser session.");
  refreshDashboard();
}

async function refreshDashboard() {
  if (!elements.apiKey.value.trim()) {
    setBanner("Provide an API key before loading platform data.");
    return;
  }

  setBanner("Refreshing platform state...");
  try {
    const [activity, products, builds] = await Promise.all([
      api("/api/v1/activity"),
      api("/api/v1/products"),
      api("/api/v1/builds?limit=10"),
    ]);

    state.products = products.items || [];
    state.builds = builds.items || [];
    renderMetrics(activity.totals);
    renderProducts(state.products);
    renderBuilds(state.builds);
    populateSubscriptionProducts(state.products);
    await refreshSubscriptions();
    hydrateFromQueryString();
    setBanner("Platform data loaded.");
  } catch (error) {
    setBanner(error.message || "Failed to load platform data.", true);
  }
}

async function refreshSubscriptions() {
  if (!elements.apiKey.value.trim()) {
    return;
  }

  try {
    const data = await api("/api/v1/notifications/subscriptions");
    renderSubscriptions(data.items || []);
  } catch (error) {
    elements.subscriptionsList.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "Could not load subscriptions.")}</div>`;
  }
}

function renderMetrics(totals) {
  const cards = [
    ["Products", totals.products, "Onboarded software lines"],
    ["Releases", totals.releases, "Release trains tracked"],
    ["Builds", totals.builds, "Manifests stored in the control plane"],
    ["Released", totals.released_builds, "Immutable approved builds"],
    ["Incomplete", totals.incomplete_builds, "Builds still missing full traceability"],
  ];
  elements.metricsGrid.innerHTML = "";
  for (const [label, value, note] of cards) {
    const node = elements.metricTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector(".metric-label").textContent = label;
    node.querySelector(".metric-value").textContent = value;
    node.querySelector(".metric-note").textContent = note;
    elements.metricsGrid.appendChild(node);
  }
}

function renderProducts(products) {
  elements.productsCount.textContent = `${products.length} products`;
  if (!products.length) {
    elements.productsList.innerHTML = '<div class="empty-state">No products found.</div>';
    return;
  }

  elements.productsList.innerHTML = products.map((product) => `
    <div class="product-card">
      <h3>${escapeHtml(product.name)}</h3>
      <div class="meta-row">
        <span class="mono">${escapeHtml(product.external_id)}</span>
        <span>${product.release_count} releases</span>
        <span>${product.build_count} builds</span>
      </div>
      <div class="meta-row">
        <span>Last build: ${escapeHtml(product.last_build_id || "none")}</span>
        <span>${escapeHtml(product.last_build_status || "n/a")}</span>
      </div>
    </div>
  `).join("");
}

function renderBuilds(builds) {
  elements.buildsCount.textContent = `${builds.length} builds`;
  if (!builds.length) {
    elements.buildsList.innerHTML = '<div class="empty-state">No recent builds found.</div>';
    return;
  }

  elements.buildsList.innerHTML = builds.map((build) => `
    <button type="button" class="build-row ${state.activeBuild && state.activeBuild.build_id === build.build_id && state.activeBuild.product_id === build.product_id ? "is-active" : ""}" data-build-id="${escapeHtml(build.build_id)}" data-product-id="${escapeHtml(build.product_id)}">
      <h3>${escapeHtml(build.product_name)} / <span class="mono">${escapeHtml(build.build_id)}</span></h3>
      <div class="meta-row">
        <span class="status-chip" data-status="${escapeHtml(build.status)}">${escapeHtml(build.status)}</span>
        <span>${escapeHtml(build.release || "no release")}</span>
        <span>${build.commit_count} commits</span>
        <span>${build.artifact_count} artifacts</span>
      </div>
    </button>
  `).join("");

  for (const button of elements.buildsList.querySelectorAll(".build-row")) {
    button.addEventListener("click", () => loadBuild(button.dataset.buildId, button.dataset.productId));
  }
}

async function loadBuild(buildId, productId) {
  try {
    const [detail, artifacts, traceability] = await Promise.all([
      api(`/api/v1/builds/${encodeURIComponent(buildId)}?product_id=${encodeURIComponent(productId)}`),
      api(`/api/v1/builds/${encodeURIComponent(buildId)}/artifacts?product_id=${encodeURIComponent(productId)}`),
      api(`/api/v1/builds/${encodeURIComponent(buildId)}/traceability?product_id=${encodeURIComponent(productId)}`),
    ]);

    state.activeBuild = detail;
    renderBuilds(state.builds);
    renderBuildDetail(detail, artifacts, traceability);
    updateQueryString(buildId, productId);
    setBanner(`Loaded build ${buildId}.`);
  } catch (error) {
    setBanner(error.message || `Could not load build ${buildId}.`, true);
  }
}

function renderBuildDetail(detail, artifacts, traceability, verification = null) {
  const verificationMarkup = verification ? `
    <div class="detail-block">
      <h3>Integrity</h3>
      <div class="meta-row">
        <span class="status-chip" data-status="${escapeHtml(verification.integrity_status)}">${escapeHtml(verification.integrity_status)}</span>
        <span>${verification.artifacts.length} artifacts checked</span>
      </div>
    </div>
  ` : "";

  const artifactsMarkup = (artifacts.artifacts || []).map((artifact) => `
    <div class="artifact-item">
      <strong>${escapeHtml(artifact.name)}</strong>
      <div class="meta-row">
        <span>${escapeHtml(artifact.type)}</span>
        <span class="mono">${escapeHtml(artifact.sha256.slice(0, 16))}...</span>
      </div>
    </div>
  `).join("") || '<div class="empty-state">No artifacts recorded.</div>';

  const traceabilityMarkup = (traceability.repositories || []).map((repository) => `
    <div class="trace-item">
      <strong>${escapeHtml(repository.repository)}</strong>
      <div class="meta-row">
        <span>${repository.commit_count} commits</span>
        <span>${repository.pull_request_count} pull requests</span>
        <span>${repository.issue_count} issues</span>
      </div>
    </div>
  `).join("") || '<div class="empty-state">No traceability data recorded.</div>';

  elements.buildDetail.innerHTML = `
    <div class="detail-stack">
      <div class="detail-block">
        <h3>${escapeHtml(detail.product_name)} / <span class="mono">${escapeHtml(detail.build_id)}</span></h3>
        <div class="meta-row">
          <span class="status-chip" data-status="${escapeHtml(detail.status)}">${escapeHtml(detail.status)}</span>
          <span>${escapeHtml(detail.release || "no release")}</span>
          <span>${escapeHtml(detail.build_type)}</span>
          <span>Traceability incomplete: ${detail.traceability_incomplete ? "yes" : "no"}</span>
        </div>
      </div>
      ${verificationMarkup}
      <div class="detail-block">
        <h3>Artifacts</h3>
        <div class="artifact-list">${artifactsMarkup}</div>
      </div>
      <div class="detail-block">
        <h3>Traceability</h3>
        <div class="trace-list">${traceabilityMarkup}</div>
      </div>
    </div>
  `;
}

async function verifySelectedBuild() {
  if (!state.activeBuild) {
    setBanner("Select a build before requesting verification.");
    return;
  }

  try {
    const verification = await api(`/api/v1/builds/${encodeURIComponent(state.activeBuild.build_id)}/verify?product_id=${encodeURIComponent(state.activeBuild.product_id)}`, {
      method: "POST",
    });
    const artifacts = await api(`/api/v1/builds/${encodeURIComponent(state.activeBuild.build_id)}/artifacts?product_id=${encodeURIComponent(state.activeBuild.product_id)}`);
    const traceability = await api(`/api/v1/builds/${encodeURIComponent(state.activeBuild.build_id)}/traceability?product_id=${encodeURIComponent(state.activeBuild.product_id)}`);
    renderBuildDetail(state.activeBuild, artifacts, traceability, verification);
    setBanner(`Integrity status: ${verification.integrity_status}.`);
  } catch (error) {
    setBanner(error.message || "Verification failed.", true);
  }
}

function populateSubscriptionProducts(products) {
  elements.subscriptionProduct.innerHTML = products
    .map((product) => `<option value="${escapeHtml(product.external_id)}">${escapeHtml(product.name)}</option>`)
    .join("");
}

async function createSubscription(event) {
  event.preventDefault();

  try {
    await api("/api/v1/notifications/subscriptions", {
      method: "POST",
      body: JSON.stringify({
        product_id: elements.subscriptionProduct.value,
        release: elements.subscriptionRelease.value.trim() || null,
        channel: elements.subscriptionChannel.value,
        webhook_url: elements.subscriptionWebhook.value.trim() || null,
      }),
    });
    elements.subscriptionForm.reset();
    await refreshSubscriptions();
    setBanner("Subscription created.");
  } catch (error) {
    setBanner(error.message || "Could not create subscription.", true);
  }
}

function renderSubscriptions(subscriptions) {
  if (!subscriptions.length) {
    elements.subscriptionsList.innerHTML = '<div class="empty-state">No subscriptions configured for this user.</div>';
    return;
  }

  elements.subscriptionsList.innerHTML = subscriptions.map((subscription) => `
    <div class="subscription-row">
      <div>
        <strong>${escapeHtml(subscription.product_name)}</strong>
        <div class="meta-row">
          <span>${escapeHtml(subscription.channel)}</span>
          <span>${escapeHtml(subscription.release || "all releases")}</span>
        </div>
      </div>
      <button type="button" class="secondary-button" data-subscription-id="${subscription.id}">Delete</button>
    </div>
  `).join("");

  for (const button of elements.subscriptionsList.querySelectorAll("[data-subscription-id]")) {
    button.addEventListener("click", async () => {
      try {
        await api(`/api/v1/notifications/subscriptions/${button.dataset.subscriptionId}`, { method: "DELETE" });
        await refreshSubscriptions();
        setBanner("Subscription removed.");
      } catch (error) {
        setBanner(error.message || "Could not remove subscription.", true);
      }
    });
  }
}

function hydrateFromQueryString() {
  const params = new URLSearchParams(window.location.search);
  const buildId = params.get("build");
  const productId = params.get("product");
  if (buildId && productId) {
    loadBuild(buildId, productId);
    return;
  }
  if (state.builds.length && !state.activeBuild) {
    loadBuild(state.builds[0].build_id, state.builds[0].product_id);
  }
}

function updateQueryString(buildId, productId) {
  const url = new URL(window.location.href);
  url.searchParams.set("build", buildId);
  url.searchParams.set("product", productId);
  window.history.replaceState({}, "", url);
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-API-Key": elements.apiKey.value.trim(),
  };
  const userId = elements.userId.value.trim();
  if (userId) {
    headers["X-User-Id"] = userId;
  }

  const response = await fetch(path, {
    ...options,
    headers: {
      ...headers,
      ...(options.headers || {}),
    },
  });

  if (response.status === 204) {
    return null;
  }

  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (error) {
    data = null;
  }

  if (!response.ok) {
    const detail = data && typeof data.detail === "string"
      ? data.detail
      : data && data.detail && data.detail.message
        ? data.detail.message
        : text || `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return data;
}

function setBanner(message, isError = false) {
  elements.statusBanner.textContent = message;
  elements.statusBanner.style.background = isError
    ? "linear-gradient(135deg, rgba(216, 84, 55, 0.16), rgba(216, 84, 55, 0.08))"
    : "linear-gradient(135deg, rgba(13, 110, 110, 0.14), rgba(12, 79, 85, 0.08))";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

bootstrap();
