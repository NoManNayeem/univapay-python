// Front-end glue for the UniVapay widget (no simulation).
// IMPORTANT: Make sure the official UniVapay widget loader is included
// in your page BEFORE this file, so window.UniVapay.open(...) exists.

(function () {
  "use strict";

  // ---------- utils ----------
  function log() {
    var args = Array.prototype.slice.call(arguments);
    args.unshift("[Demo]");
    console.log.apply(console, args);
  }

  function fetchJSON(url, opts) {
    var base = { headers: { "Content-Type": "application/json" } };
    var merged = Object.assign({}, base, opts || {});
    return fetch(url, merged).then(function (r) {
      if (!r.ok) {
        return r.text().then(function (txt) {
          throw new Error("HTTP " + r.status + ": " + txt);
        });
      }
      return r.json();
    });
  }

  function postJSON(url, body) {
    return fetchJSON(url, {
      method: "POST",
      body: JSON.stringify(body || {})
    });
  }

  function currentGatewayToggles() {
    var card = document.querySelector("#gate-card");
    var konbini = document.querySelector("#gate-konbini");
    var bank = document.querySelector("#gate-bank");
    var paypay = document.querySelector("#gate-paypay");
    var alipay = document.querySelector("#gate-alipay");
    var alipayPlus = document.querySelector("#gate-alipay-plus");
    var wechat = document.querySelector("#gate-wechat");
    var dbarai = document.querySelector("#gate-dbarai");
    var gateways = {
      card: !!(card && card.checked),
      konbini: !!(konbini && konbini.checked),
      bank_transfer: (bank && bank.checked) ? { aozora_bank: true } : {},
      online: {
        pay_pay_online: !!(paypay && paypay.checked),
        alipay_online: !!(alipay && alipay.checked),
        alipay_plus_online: !!(alipayPlus && alipayPlus.checked),
        we_chat_online: !!(wechat && wechat.checked),
        d_barai_online: !!(dbarai && dbarai.checked)
      }
    };
    return { gateways: JSON.stringify(gateways) };
  }

  function selectedPaymentMethodsArray() {
    // Build array for UnivapayCheckout.create({ paymentMethods: [...] })
    var arr = [];
    var card = document.querySelector("#gate-card");
    var konbini = document.querySelector("#gate-konbini");
    var bank = document.querySelector("#gate-bank");
    var paypay = document.querySelector("#gate-paypay");
    var alipay = document.querySelector("#gate-alipay");
    var alipayPlus = document.querySelector("#gate-alipay-plus");
    var wechat = document.querySelector("#gate-wechat");
    var dbarai = document.querySelector("#gate-dbarai");

    if (card && card.checked) arr.push("card");
    if (konbini && konbini.checked) arr.push("konbini");
    if (bank && bank.checked) arr.push("bank_transfer");
    if (paypay && paypay.checked) arr.push("pay_pay_online");
    if (alipay && alipay.checked) arr.push("alipay_online");
    if (alipayPlus && alipayPlus.checked) arr.push("alipay_plus_online");
    if (wechat && wechat.checked) arr.push("we_chat_online");
    if (dbarai && dbarai.checked) arr.push("d_barai_online");

    // Keep card as default if nothing selected
    if (arr.length === 0) arr.push("card");
    return arr;
  }

  function ensureWidgetAvailable() {
    console.log('[Demo] Checking widget availability...');
    var uniVapayOk = !!(window.UniVapay && typeof window.UniVapay.open === 'function');
    var checkoutOk = !!(window.UnivapayCheckout && typeof window.UnivapayCheckout.create === 'function');
    console.log('[Demo] UniVapay.open available:', uniVapayOk);
    console.log('[Demo] UnivapayCheckout.create available:', checkoutOk);
    return uniVapayOk || checkoutOk;
  }

  function waitForWidget(callback, maxAttempts = 300) {
    var attempts = 0;
    var checkWidget = function() {
      attempts++;
      console.log('[Demo] Checking widget availability (attempt ' + attempts + ')');
      
      var hasCheckout = !!(window.UnivapayCheckout && typeof window.UnivapayCheckout.create === 'function');
      var hasLegacyOpen = !!(window.UniVapay && typeof window.UniVapay.open === 'function');

      if (hasCheckout || hasLegacyOpen) {
        console.log('[Demo] Widget is now available!', { hasCheckout: hasCheckout, hasLegacyOpen: hasLegacyOpen });
        callback(true);
        return;
      }
      
      if (attempts >= maxAttempts) {
        console.log('[Demo] Widget failed to load after ' + maxAttempts + ' attempts');
        console.log('[Demo] Available globals:', Object.keys(window).filter(k => k.toLowerCase().includes('univa')));
        callback(false);
        return;
      }
      
      setTimeout(checkWidget, 100); // Check every 100ms
    };
    
    checkWidget();
  }

  // ---------- backend ingest helpers ----------
  // These call server endpoints to fetch/store the full resource details in SQLite.
  // We’ll add them to app.py next: /api/ingest/charge/<id>, /api/ingest/subscription/<id>
  function ingestCharge(chargeId) {
    return postJSON("/api/ingest/charge/" + encodeURIComponent(chargeId), {});
  }
  function ingestSubscription(subscriptionId) {
    return postJSON("/api/ingest/subscription/" + encodeURIComponent(subscriptionId), {});
  }

  // ---------- widget event listeners ----------
  function attachWidgetEventLogging() {
    if (window.__univaDemoEventsAttached) return;
    window.__univaDemoEventsAttached = true;

    window.addEventListener("univapay:opened", function (ev) {
      log("[event] opened", ev);
    });

    window.addEventListener("univapay:token-created", function (ev) {
      log("[event] token-created", ev.detail || {});
    });

    window.addEventListener("univapay:subscription-created", function (ev) {
      var d = ev.detail || {};
      log("[event] subscription-created", d);
      if (d.subscriptionId) {
        ingestSubscription(d.subscriptionId).catch(function (e) {
          log("ingestSubscription failed:", e && e.message ? e.message : e);
        });
      }
    });

    window.addEventListener("univapay:success", function (ev) {
      var d = ev && ev.detail ? ev.detail : {};
      log("[event] success", d);

      var ingested = Promise.resolve();
      if (d.resourceType === "subscription" && d.subscriptionId) {
        ingested = ingestSubscription(d.subscriptionId);
      } else if (d.chargeId) {
        ingested = ingestCharge(d.chargeId);
      }

      ingested
        .catch(function (e) {
          log("ingest failed (continuing):", e && e.message ? e.message : e);
        })
        .finally(function () {
          try {
            var msg = "Success";
            if (d.resourceType === "subscription" && d.subscriptionId) {
              msg = "Subscription created: " + d.subscriptionId;
            } else if (d.chargeId) {
              msg = "Charge created: " + d.chargeId;
            }
            alert(msg);
          } catch (e2) {}
          window.location = "/admin";
        });
    });

    window.addEventListener("univapay:closed", function (ev) {
      log("[event] closed", ev);
    });
  }

  // ---------- open widget ----------
  function openWithWidget(envelopeOrProduct) {
    // If UnivapayCheckout is available, use it; otherwise, use UniVapay.open with envelope
    var hasCheckout = (window.UnivapayCheckout && typeof window.UnivapayCheckout.create === 'function');
    if (hasCheckout) {
      var product = envelopeOrProduct;
      var appId = (window.FLASK_DEMO && window.FLASK_DEMO.appId) || '';
      if (!appId) {
        alert('Missing appId. Check UNIVAPAY_JWT in server .env');
        return;
      }
      // Build minimal options from product
      var opts = {
        appId: appId,
        checkout: 'payment',
        amount: Number(product.amount) || 0,
        currency: (product.currency || 'jpy').toLowerCase(),
        cvvAuthorize: true,
        paymentMethods: selectedPaymentMethodsArray(),
        onSuccess: function () {
          try { window.__demoLog('Checkout success'); } catch (e) {}
        }
      };
      if (product && product.kind === 'subscription') {
        opts.tokenType = 'subscription';
        if (product.period) opts.subscriptionPeriod = String(product.period);
      } else if (product && product.kind === 'recurring') {
        opts.tokenType = 'recurring';
      }
      try {
        var checkout = window.UnivapayCheckout.create(opts);
        checkout.open();
      } catch (error) {
        console.error('[Demo] Error opening UnivapayCheckout:', error);
        alert('Error opening UnivapayCheckout: ' + error.message);
      }
      return;
    }
    // Fallback: use UniVapay.open with backend-built envelope
    var envelope = envelopeOrProduct;
    console.log('[Demo] openWithWidget called with envelope:', envelope);
    log('Opening UniVapay widget with envelope:', envelope);
    try {
      window.UniVapay.open(envelope);
    } catch (error) {
      console.error('[Demo] Error opening widget:', error);
      alert('Error opening widget: ' + error.message);
    }
  }

  function openWidgetFor(button, product) {
    console.log('[Demo] openWidgetFor called with:', button, product);
    
    // Wait for widget to be available
    waitForWidget(function(isAvailable) {
      if (!isAvailable) {
        alert("UniVapay widget failed to load. Please check:\n1. Your internet connection\n2. The widget script URL is correct\n3. Your browser allows external scripts");
        return;
      }

      console.log('[Demo] Widget is available, building config...');

      // If using UnivapayCheckout, open using JS options from product
      if (window.UnivapayCheckout && typeof window.UnivapayCheckout.create === 'function') {
        attachWidgetEventLogging();
        openWithWidget(product);
        return;
      }

      // Otherwise, build a widget config envelope from the backend
      var params = new URLSearchParams();
      params.set("type", product.kind);
      params.set("amount", String(product.amount));
      params.set("description", product.description || (product.kind + " payment"));
      params.set("formId", "form-" + product.kind + "-" + product.sku);
      params.set("buttonId", "btn-" + product.kind + "-" + product.sku);
      if (product.kind === "subscription" && product.period) {
        params.set("period", product.period);
      }
      var tog = currentGatewayToggles();
      if (tog.gateways) params.set("gateways", tog.gateways);

      console.log('[Demo] Fetching widget config with params:', params.toString());

      fetchJSON("/api/widget-config?" + params.toString())
        .then(function (envelope) {
          console.log('[Demo] Widget config received:', envelope);
          attachWidgetEventLogging();
          openWithWidget(envelope);
        })
        .catch(function (err) {
          console.error('[Demo] Widget config fetch failed:', err);
          alert(err && err.message ? err.message : String(err));
        });
    });
  }

  // ---------- UI wiring ----------
  function onClickGrid(e) {
    console.log('[Demo] Click event:', e.target);
    var btn = e.target.closest && e.target.closest("button.btn");
    if (!btn) {
      console.log('[Demo] No button found');
      return;
    }
    console.log('[Demo] Button found:', btn);
    var article = btn.closest && btn.closest("article.card");
    if (!article) {
      console.log('[Demo] No article found');
      return;
    }

    var product = {
      kind: btn.dataset.kind,
      amount: parseInt(btn.dataset.amount || "0", 10),
      currency: btn.dataset.currency || "jpy",
      period: btn.dataset.period || "",
      sku: btn.dataset.sku,
      description: (article.querySelector("p") && article.querySelector("p").textContent) || ""
    };
    console.log('[Demo] Product data:', product);
    openWidgetFor(btn, product);
  }

  function onAdminActions(e) {
    var refundBtn = e.target.closest && e.target.closest("button.refund");
    var cancelBtn = e.target.closest && e.target.closest("button.cancel");
    var subCancelBtn = e.target.closest && e.target.closest("button.sub-cancel");
    var refundRefreshBtn = e.target.closest && e.target.closest("button.refund-refresh");
    var subRefreshBtn = e.target.closest && e.target.closest("button.sub-refresh");
    var chargeRefreshBtn = e.target.closest && e.target.closest("button.charge-refresh");
    if (!refundBtn && !cancelBtn && !subCancelBtn && !refundRefreshBtn && !subRefreshBtn && !chargeRefreshBtn) return;

    var id = (refundBtn || cancelBtn || subCancelBtn)?.dataset?.id;
    var chargeId = refundRefreshBtn ? refundRefreshBtn.dataset.chargeId : null;
    var refundId = refundRefreshBtn ? refundRefreshBtn.dataset.refundId : null;
    if (!id && !refundRefreshBtn && !subRefreshBtn && !chargeRefreshBtn) return;

    if (refundBtn) {
      var amountStr = window.prompt("Refund amount (minor units). Leave blank for full refund.", "");
      var payload = {};
      if (amountStr && amountStr.trim().length > 0) {
        payload.amount = parseInt(amountStr, 10);
      }
      postJSON("/api/refunds/" + id, payload)
        .then(function (r) {
          alert("Refund created: " + r.id);
          window.location.reload();
        })
        .catch(function (err) {
          alert(err && err.message ? err.message : String(err));
        });
    }

    if (cancelBtn) {
      postJSON("/api/cancels/" + id, {})
        .then(function (r) {
          alert("Charge canceled: " + r.id);
          window.location.reload();
        })
        .catch(function (err) {
          alert(err && err.message ? err.message : String(err));
        });
    }

    if (subCancelBtn) {
      postJSON("/api/subscriptions/" + id + "/cancel", {})
        .then(function (r) {
          alert("Subscription canceled: " + r.id);
          window.location.reload();
        })
        .catch(function (err) {
          alert(err && err.message ? err.message : String(err));
        });
    }

    if (refundRefreshBtn && chargeId && refundId) {
      fetchJSON("/api/refunds/" + encodeURIComponent(chargeId) + "/" + encodeURIComponent(refundId) + "?polling=1")
        .then(function (r) {
          alert("Refund status: " + (r.status || '')); 
          window.location.reload();
        })
        .catch(function (err) {
          alert(err && err.message ? err.message : String(err));
        });
    }

    if (subRefreshBtn && subRefreshBtn.dataset.id) {
      fetchJSON("/api/subscriptions/" + encodeURIComponent(subRefreshBtn.dataset.id) + "?polling=1")
        .then(function (r) {
          alert("Subscription status: " + (r.status || ''));
          window.location.reload();
        })
        .catch(function (err) {
          alert(err && err.message ? err.message : String(err));
        });
    }

    if (chargeRefreshBtn && chargeRefreshBtn.dataset.id) {
      // Re-ingest the charge to update amount/currency/status in DB
      postJSON("/api/ingest/charge/" + encodeURIComponent(chargeRefreshBtn.dataset.id), {})
        .then(function (r) {
          alert("Charge status: " + (r.status || ''));
          window.location.reload();
        })
        .catch(function (err) {
          alert(err && err.message ? err.message : String(err));
        });
    }
  }

  document.addEventListener("click", function (e) {
    if (document.querySelector(".grid")) onClickGrid(e);
    if (document.querySelector(".table")) onAdminActions(e);
  });
})();
