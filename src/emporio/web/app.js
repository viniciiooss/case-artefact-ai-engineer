"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const storageKey = "emporio.mel.session.v1";
  const messageText = new WeakMap();
  const state = { session: null, messages: [], ready: false, busy: false, verifying: false, resetting: false, verifiedOrders: [], initialization: null };
  const messageInput = $("message");
  const orderDialog = $("order-dialog");
  const resetDialog = $("reset-dialog");

  class RequestError extends Error {
    constructor(message, status) { super(message); this.status = status; }
  }

  function saveSession(session) {
    state.session = session;
    try {
      if (session) localStorage.setItem(storageKey, JSON.stringify(session));
      else localStorage.removeItem(storageKey);
    } catch (_) { /* A conversa continua mesmo sem armazenamento local disponível. */ }
  }

  function readSession() {
    try {
      const value = JSON.parse(localStorage.getItem(storageKey));
      return value && typeof value.session_id === "string" && typeof value.token === "string" ? value : null;
    } catch (_) { return null; }
  }

  async function request(path, options = {}, authenticated = false) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 120000);
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    if (options.body) headers["Content-Type"] = "application/json";
    if (authenticated && state.session) headers.Authorization = `Bearer ${state.session.token}`;
    try {
      const response = await fetch(path, { ...options, headers, signal: controller.signal, cache: "no-store" });
      if (!response.ok) {
        let detail;
        try { const data = await response.json(); detail = data.detail; } catch (_) { /* HTTP sem JSON. */ }
        const text = typeof detail === "string" && response.status < 500 ? detail : "";
        throw new RequestError(text || "Não foi possível concluir agora. Tente novamente em instantes.", response.status);
      }
      return response.status === 204 ? null : await response.json();
    } catch (error) {
      if (error instanceof RequestError) throw error;
      throw new RequestError(error.name === "AbortError" ? "A consulta demorou mais que o esperado. Sua mensagem continua aqui para tentar novamente." : "Não foi possível conectar à loja. Confira sua conexão e tente novamente.", 0);
    } finally { window.clearTimeout(timeout); }
  }

  const sessionPath = (suffix = "") => `/api/sessions/${encodeURIComponent(state.session.session_id)}${suffix}`;
  // Um 403 ao identificar pedido indica dados não conferidos, não sessão expirada.
  const invalidSession = (error) => [401, 404].includes(error.status);

  function showError(message, retry = false) {
    $("error-message").textContent = message;
    $("retry-connection").hidden = !retry;
    $("error-banner").hidden = false;
  }

  function clearError() { $("error-banner").hidden = true; }

  function syncControls() {
    const blocked = !state.ready || state.busy || state.resetting || state.verifying;
    $("send-message").disabled = blocked || !messageInput.value.trim();
    messageInput.disabled = state.busy || state.resetting;
    $("new-conversation").disabled = !state.ready || state.busy || state.verifying || state.resetting;
    $("open-order").disabled = blocked || state.verifying;
    document.querySelectorAll("[data-prompt]").forEach((button) => { button.disabled = blocked; });
    $("thinking").hidden = !state.busy;
    $("message-form").setAttribute("aria-busy", String(state.busy));
  }

  function updateProvider(provider) { $("demo-label").hidden = provider !== "demo"; }

  function resizeInput() {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 150)}px`;
  }

  function scrollToEnd() {
    const scroller = $("conversation-scroll");
    scroller.scrollTop = scroller.scrollHeight;
  }

  function renderSources(sources, parent) {
    if (!Array.isArray(sources) || !sources.length) return;
    const wrapper = document.createElement("div");
    wrapper.className = "sources";
    const label = document.createElement("p");
    label.className = "sources-label";
    label.textContent = "Fontes desta resposta";
    wrapper.append(label);
    const seen = new Set();
    for (const source of sources) {
      if (!source || typeof source !== "object") continue;
      const key = `${source.id || source.title || ""}:${source.page || ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const details = document.createElement("details");
      details.className = "source";
      const summary = document.createElement("summary");
      const page = Number(source.page);
      const hasPage = Number.isInteger(page) && page > 0;
      summary.textContent = `${source.title || "Referência consultada"}${hasPage ? ` · pág. ${page}` : ""}`;
      const body = document.createElement("div");
      body.className = "source-body";
      if (source.excerpt) {
        const excerpt = document.createElement("p");
        excerpt.textContent = String(source.excerpt);
        body.append(excerpt);
      }
      if (source.reference) {
        const reference = document.createElement("p");
        reference.textContent = String(source.reference);
        body.append(reference);
      }
      if (hasPage) {
        const link = document.createElement("a");
        link.href = `/api/policies/document#page=${page}`;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = `Abrir manual na página ${page} ↗`;
        body.append(link);
      }
      if (!body.childNodes.length) body.textContent = "Referência consultada para esta resposta.";
      details.append(summary, body);
      wrapper.append(details);
    }
    if (seen.size) parent.append(wrapper);
  }

  function appendMessage(message) {
    if (!["user", "assistant"].includes(message.role)) return;
    const article = document.createElement("article");
    article.className = `message message-${message.role}`;
    article.setAttribute("aria-label", message.role === "user" ? "Você" : "Mel");
    if (message.role === "assistant") {
      const label = document.createElement("p");
      label.className = "message-label";
      label.textContent = "Mel";
      article.append(label);
    }
    const content = document.createElement("div");
    content.className = "message-content";
    const text = String(message.content || "");
    messageText.set(article, text);
    if (message.role === "assistant") renderAnswer(text, content);
    else content.textContent = text;
    article.append(content);
    if (message.role === "assistant") {
      const ms = message.latency_ms;
      if (typeof ms === "number" && Number.isFinite(ms) && ms >= 0) {
        const latency = document.createElement("p");
        latency.className = "message-latency";
        const value = ms < 1000 ? Math.round(ms) : ms / 1000;
        const formatted = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(value);
        latency.textContent = `Tempo de resposta: ${formatted} ${ms < 1000 ? "ms" : "s"}`;
        latency.title = "Tempo de processamento no servidor, incluindo consultas às fontes.";
        article.append(latency);
      }
      renderSources(message.sources, article);
    }
    $("messages").append(article);
  }

  function renderAnswer(text, parent) {
    let paragraph = null;
    let list = null;
    for (const line of text.split(/\r?\n/)) {
      if (!line.trim()) { paragraph = null; list = null; continue; }
      const item = line.match(/^\s*(?:([-*•])|(\d+)[.)])\s+(.+)$/);
      if (item) {
        const tag = item[1] ? "ul" : "ol";
        if (!list || list.localName !== tag) {
          list = document.createElement(tag);
          if (tag === "ol") list.start = Number(item[2]);
          parent.append(list);
        }
        const entry = document.createElement("li");
        renderEmphasis(item[3], entry);
        list.append(entry);
        paragraph = null;
      } else {
        list = null;
        if (!paragraph) {
          paragraph = document.createElement("p");
          parent.append(paragraph);
        } else paragraph.append(document.createElement("br"));
        renderEmphasis(line, paragraph);
      }
    }
  }

  function renderEmphasis(text, parent) {
    // Só criamos texto e elementos de ênfase; HTML, links e imagens não são executados.
    const pattern = /\\([\\*])|\*\*([^*\n]+)\*\*|\*([^*\n]+)\*/g;
    let end = 0;
    for (const match of text.matchAll(pattern)) {
      parent.append(document.createTextNode(text.slice(end, match.index)));
      if (match[1]) parent.append(document.createTextNode(match[1]));
      else {
        const emphasis = document.createElement(match[2] ? "strong" : "em");
        emphasis.textContent = match[2] || match[3];
        parent.append(emphasis);
      }
      end = match.index + match[0].length;
    }
    parent.append(document.createTextNode(text.slice(end)));
  }

  function renderHistory() {
    const log = $("messages");
    let common = 0;
    while (common < log.children.length && common < state.messages.length) {
      const node = log.children[common];
      const message = state.messages[common];
      if (!node.classList.contains(`message-${message.role}`) || messageText.get(node) !== String(message.content || "")) break;
      common += 1;
    }
    while (log.children.length > common) log.lastChild.remove();
    state.messages.slice(common).forEach(appendMessage);
    $("welcome").hidden = state.messages.length > 0;
    scrollToEnd();
  }

  function updateVerified(orders) {
    state.verifiedOrders = Array.isArray(orders) ? orders.filter((order) => Number.isSafeInteger(order) && order > 0) : [];
    const note = $("verified-note");
    note.hidden = !state.verifiedOrders.length;
    note.textContent = state.verifiedOrders.length ? `${state.verifiedOrders.length === 1 ? "Pedido" : "Pedidos"} ${state.verifiedOrders.join(", ")} ${state.verifiedOrders.length === 1 ? "identificado" : "identificados"} nesta conversa.` : "";
    $("open-order").textContent = state.verifiedOrders.length ? "Identificar outro pedido ↗" : "Identificar pedido ↗";
  }

  async function createSession() {
    const session = await request("/api/sessions", { method: "POST" });
    if (!session || typeof session.session_id !== "string" || typeof session.token !== "string") {
      throw new RequestError("A conversa não pôde ser iniciada. Tente novamente.", 0);
    }
    saveSession(session);
    state.messages = [];
    updateVerified([]);
  }

  async function initialize() {
    if (state.initialization) return state.initialization;
    state.initialization = (async () => {
      clearError();
      state.ready = false;
      syncControls();
      $("connection-status").lastChild.textContent = "Preparando a conversa…";
      try {
        const health = await request("/api/health");
        updateProvider(health.provider);
        if (!state.session) saveSession(readSession());
        if (state.session) {
          try {
            const history = await request(sessionPath(), {}, true);
            state.messages = Array.isArray(history.messages) ? history.messages.filter((m) => m && ["user", "assistant"].includes(m.role)) : [];
            updateVerified(history.verified_orders);
          } catch (error) {
            if (!invalidSession(error)) throw error;
            saveSession(null);
            await createSession();
          }
        } else { await createSession(); }
        state.ready = true;
        $("connection-status").classList.add("is-ready");
        $("connection-status").lastChild.textContent = "Pode chegar, estou por aqui";
        renderHistory();
      } catch (error) {
        $("connection-status").classList.remove("is-ready");
        $("connection-status").lastChild.textContent = "Conexão indisponível";
        showError(error.message, true);
      } finally { state.initialization = null; syncControls(); }
    })();
    return state.initialization;
  }

  async function sendMessage(event) {
    event.preventDefault();
    const text = messageInput.value.trim();
    if (!text || !state.ready || state.busy || state.resetting) return;
    if (text.length > 4000) {
      showError("Sua mensagem pode ter até 4.000 caracteres. Divida o texto para continuar.");
      messageInput.focus();
      return;
    }
    clearError();
    $("status-notice").hidden = true;
    const previousLength = state.messages.length;
    state.busy = true;
    state.messages.push({ role: "user", content: text, sources: [] });
    messageInput.value = "";
    resizeInput();
    syncControls();
    renderHistory();
    try {
      const result = await request(sessionPath("/messages"), { method: "POST", body: JSON.stringify({ message: text }) }, true);
      if (typeof result.message !== "string" || !result.message.trim()) throw new RequestError("A resposta não chegou completa. Sua mensagem está pronta para tentar novamente.", 0);
      state.messages.push({ role: "assistant", content: result.message, sources: result.sources || [], latency_ms: result.latency_ms });
      updateProvider(result.provider);
      renderHistory();
    } catch (error) {
      let recovered = false;
      // Se a resposta chegou ao servidor antes de a conexão cair, recupera o histórico
      // antes de oferecer o reenvio da mesma mensagem.
      if (!invalidSession(error)) {
        try {
          const history = await request(sessionPath(), {}, true);
          const messages = Array.isArray(history.messages) ? history.messages : [];
          const tail = messages.slice(previousLength);
          if (tail.some((m) => m.role === "user" && m.content === text) && tail.some((m) => m.role === "assistant")) {
            state.messages = messages;
            updateVerified(history.verified_orders);
            recovered = true;
          }
        } catch (_) { /* Mantém o texto disponível para um reenvio manual. */ }
      }
      if (!recovered) {
        state.messages = state.messages.slice(0, previousLength);
        messageInput.value = text;
        resizeInput();
        if (invalidSession(error)) {
          saveSession(null);
          state.ready = false;
          await initialize();
          showError("Esta sessão expirou. Uma nova conversa foi aberta e sua mensagem está pronta para enviar.", !state.ready);
        } else { showError(error.message); }
      }
      renderHistory();
    } finally {
      state.busy = false;
      syncControls();
      messageInput.focus({ preventScroll: true });
      scrollToEnd();
    }
  }

  async function verifyOrder(event) {
    event.preventDefault();
    if (state.verifying || !state.ready || state.busy) return;
    const orderId = Number($("order-id").value);
    const email = $("order-email").value.trim();
    const feedback = $("order-feedback");
    if (!Number.isSafeInteger(orderId) || orderId <= 0) {
      feedback.classList.remove("success");
      feedback.textContent = "Informe um número de pedido inteiro maior que zero.";
      feedback.hidden = false;
      $("order-id").focus();
      return;
    }
    if (!email) return;
    state.verifying = true;
    feedback.hidden = true;
    feedback.classList.remove("success");
    $("verify-order").disabled = true;
    $("verify-order").textContent = "Conferindo os dados…";
    syncControls();
    try {
      const result = await request(sessionPath("/order-access"), { method: "POST", body: JSON.stringify({ order_id: orderId, email }) }, true);
      if (!result.verified) throw new RequestError("Não encontramos um pedido com esses dados. Confira o número e o e-mail da compra.", 422);
      clearError();
      updateVerified([...new Set([...state.verifiedOrders, result.order_id])]);
      feedback.textContent = `Pedido ${result.order_id} identificado. Agora você pode perguntar o andamento à Mel.`;
      feedback.classList.add("success");
      feedback.hidden = false;
      $("order-email").value = "";
      if (!messageInput.value.trim()) messageInput.value = `Qual é o andamento do pedido ${result.order_id}?`;
      resizeInput();
      $("status-notice").textContent = feedback.textContent;
      $("status-notice").hidden = false;
      orderDialog.close();
      messageInput.focus();
    } catch (error) {
      if (invalidSession(error)) {
        saveSession(null);
        await initialize();
        feedback.textContent = "A sessão expirou. Confira os dados e identifique o pedido novamente.";
      } else { feedback.textContent = error.message; }
      feedback.hidden = false;
    } finally {
      state.verifying = false;
      $("verify-order").disabled = false;
      $("verify-order").textContent = "Identificar pedido";
      syncControls();
    }
  }

  async function resetConversation() {
    if (state.resetting || state.busy) return;
    state.resetting = true;
    $("confirm-reset").disabled = true;
    $("confirm-reset").textContent = "Excluindo…";
    $("reset-feedback").hidden = true;
    syncControls();
    try {
      if (state.session) {
        try { await request(sessionPath(), { method: "DELETE" }, true); }
        catch (error) { if (!invalidSession(error)) throw error; }
      }
      saveSession(null);
      state.messages = [];
      state.ready = false;
      updateVerified([]);
      messageInput.value = "";
      $("status-notice").hidden = true;
      resizeInput();
      renderHistory();
      resetDialog.close();
      await initialize();
      messageInput.focus();
    } catch (error) {
      $("reset-feedback").textContent = `${error.message} Seu histórico foi mantido nesta tela.`;
      $("reset-feedback").hidden = false;
    } finally {
      state.resetting = false;
      $("confirm-reset").disabled = false;
      $("confirm-reset").textContent = "Excluir e começar";
      syncControls();
    }
  }

  $("message-form").addEventListener("submit", sendMessage);
  messageInput.addEventListener("input", () => { resizeInput(); syncControls(); });
  messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      if (!$("send-message").disabled) $("message-form").requestSubmit();
    }
  });
  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      messageInput.value = button.dataset.prompt;
      resizeInput();
      syncControls();
      $("message-form").requestSubmit();
    });
  });
  $("open-order").addEventListener("click", () => {
    $("order-feedback").hidden = true;
    orderDialog.showModal();
  });
  $("new-conversation").addEventListener("click", () => {
    $("reset-feedback").hidden = true;
    resetDialog.showModal();
  });
  document.querySelectorAll("[data-close]").forEach((button) => {
    button.addEventListener("click", () => { $(button.dataset.close).close(); });
  });
  // O dialog nativo mantém o foco dentro do modal e permite fechá-lo com Escape.
  resetDialog.addEventListener("cancel", (event) => { if (state.resetting) event.preventDefault(); });
  $("confirm-reset").addEventListener("click", resetConversation);
  $("order-form").addEventListener("submit", verifyOrder);
  $("retry-connection").addEventListener("click", initialize);
  $("dismiss-error").addEventListener("click", clearError);
  initialize();
})();
