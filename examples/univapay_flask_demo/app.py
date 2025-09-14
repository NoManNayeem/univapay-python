from __future__ import annotations
import os
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from flask import (
    Flask, render_template, request, jsonify, g, redirect, url_for, abort, flash, Response, session
)
from dotenv import load_dotenv

# Load environment variables for the app (.env in this folder)
load_dotenv()

# --- SDK imports ---
# Import from the local SDK in the parent directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from univapay import (
    UnivapayConfig, UnivapayClient,
    ChargesAPI, SubscriptionsAPI, RefundsAPI, CancelsAPI, TokensAPI,
    build_one_time_widget_config, build_subscription_widget_config, build_recurring_widget_config,
    make_idempotency_key, safe_metadata, UnivapayHTTPError,
)
# Webhook helpers (signature verification is optional; enabled if secret is present)
from univapay.resources import parse_event, WebhookVerificationError

# -------------------- Flask setup --------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
# Optional override for widget loader URL (helps in restricted networks)
app.config["UNIVAPAY_WIDGET_URL"] = os.getenv("UNIVAPAY_WIDGET_URL")
app.config["UNIVAPAY_APP_ID"] = os.getenv("UNIVAPAY_JWT", "")

# Debug flag for extra prints
APP_DEBUG = os.getenv("FLASK_APP_DEBUG", "1").lower() not in ("0", "false", "no")
WEBHOOK_SECRET = os.getenv("UNIVAPAY_WEBHOOK_SECRET")  # REQUIRED for real webhooks

# DB path (SQLite)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.sqlite3"


# -------------------- tiny logging helpers --------------------
def log(msg: str, extra: Dict[str, Any] | None = None) -> None:
    if APP_DEBUG:
        if extra:
            print(f"[FlaskDemo] {msg} :: {extra}", flush=True)
        else:
            print(f"[FlaskDemo] {msg}", flush=True)


# -------------------- template globals --------------------
@app.context_processor
def inject_template_globals():
    """
    Make app.config available in all templates.
    """
    return {
        "config": app.config,
        "role": session.get("role", "customer"),
        "app_id_masked": ((os.getenv("UNIVAPAY_JWT") or "")[:6] + "...") if os.getenv("UNIVAPAY_JWT") else None,
    }


# -------------------- DB helpers --------------------
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE,
            name TEXT NOT NULL,
            amount_minor INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'jpy',
            description TEXT,
            kind TEXT NOT NULL CHECK(kind IN ('one_time','subscription','recurring')),
            period TEXT
        );

        CREATE TABLE IF NOT EXISTS charges (
            id TEXT PRIMARY KEY,
            status TEXT,
            amount INTEGER,
            currency TEXT,
            token_id TEXT,
            created_on TEXT,
            json TEXT
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            status TEXT,
            amount INTEGER,
            currency TEXT,
            period TEXT,
            token_id TEXT,
            created_on TEXT,
            json TEXT
        );

        CREATE TABLE IF NOT EXISTS refunds (
            id TEXT PRIMARY KEY,
            charge_id TEXT,
            amount INTEGER,
            status TEXT,
            created_on TEXT,
            json TEXT,
            FOREIGN KEY(charge_id) REFERENCES charges(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            resource_type TEXT,
            created_on TEXT,
            payload_json TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    db.commit()
    log("DB initialized", {"path": str(DB_PATH)})

# -------------------- settings helpers --------------------
def get_setting(key: str) -> Optional[str]:
    try:
        row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row and row["value"] is not None else None
    except Exception:
        return None


def set_setting(key: str, value: Optional[str]) -> None:
    db = get_db()
    if value is None or value == "":
        db.execute("DELETE FROM settings WHERE key=?", (key,))
    else:
        db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
    db.commit()

def seed_products():
    db = get_db()
    cur = db.execute("SELECT COUNT(*) AS n FROM products")
    count = cur.fetchone()["n"]
    if count == 0:
        # Seed three products: one-time, subscription (semiannually), recurring tokenization example
        db.executemany(
            "INSERT INTO products (sku,name,amount_minor,currency,description,kind,period) VALUES (?,?,?,?,?,?,?)",
            [
                ("sku-alpha", "Product Alpha (One-time)", 12000, "jpy", "One-time payment", "one_time", None),
                ("sku-sub-semi", "Semiannual Subscription", 59400, "jpy", "Billed every 6 months", "subscription", "semiannually"),
                ("sku-recurring", "Recurring Billing Token", 30000, "jpy", "Use token for merchant-initiated charges", "recurring", None),
            ],
        )
        db.commit()
        log("Seeded products")
    else:
        log("Products already present", {"count": count})

# Ensure DB exists & seeded
with app.app_context():
    init_db()
    seed_products()

# Soft-check required secrets for real integration (do not block local UI)
missing = [k for k in ("UNIVAPAY_JWT", "UNIVAPAY_SECRET", "UNIVAPAY_STORE_ID") if not os.getenv(k)]
if missing:
    log("Config warning: missing env vars", {"vars": missing})


# -------------------- Widget proxy (optional) --------------------
@app.get("/widget/checkout.js")
def widget_checkout_js():
    """
    Optional server-side fetch for the widget script.
    Useful when the browser cannot reach the CDN directly but the server can.
    """
    src = request.args.get("src") or app.config.get("UNIVAPAY_WIDGET_URL") or "https://widget.univapay.com/client/checkout.js"
    try:
        import httpx  # type: ignore
        log("Proxy fetch widget", {"src": src})
        r = httpx.get(src, timeout=15)
        r.raise_for_status()
        return Response(r.text, mimetype="application/javascript")
    except Exception as e:
        log("Proxy fetch widget failed", {"error": repr(e), "src": src})
        return Response(f"// Failed to fetch widget from {src}: {e}", mimetype="application/javascript", status=502)

# -------------------- SDK Config --------------------
def make_config() -> UnivapayConfig:
    # Use DB settings first, then env
    def _get(k: str, default: Optional[str] = None) -> Optional[str]:
        try:
            row = get_db().execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
            if row and row["value"]:
                return row["value"]
        except Exception:
            pass
        return os.getenv(k, default) if default is not None else os.getenv(k)

    cfg = UnivapayConfig(
        jwt=_get("UNIVAPAY_JWT", ""),
        secret=_get("UNIVAPAY_SECRET", ""),
        store_id=_get("UNIVAPAY_STORE_ID"),
        base_url=_get("UNIVAPAY_BASE_URL", "https://api.univapay.com"),
        timeout=float(_get("UNIVAPAY_TIMEOUT", "30") or 30),
        debug=((_get("UNIVAPAY_DEBUG", "1") or "1") not in ("0", "false", "no")),
    ).validate()
    log("SDK config ready", cfg.masked())
    return cfg


# -------------------- request logging --------------------
@app.before_request
def _log_request():
    # light logging of incoming requests (no bodies unless JSON)
    args = dict(request.args)
    log(f"{request.method} {request.path}", {"args": args})
    if request.is_json:
        try:
            log("JSON body", {"json": request.get_json(silent=True)})
        except Exception:
            pass


# -------------------- Routes --------------------
@app.get("/")
def index():
    return redirect(url_for("customer"))


@app.get("/customer")
def customer():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY id").fetchall()
    # Example feature toggles for gateways — pass-through to widget `**extra`
    gateway_toggles = {
        "card": True,
        "konbini": False,
        "bank_transfer": False,
        "qr": False,
    }
    recent_charges = db.execute("SELECT * FROM charges ORDER BY rowid DESC LIMIT 20").fetchall()
    recent_subs = db.execute("SELECT * FROM subscriptions ORDER BY rowid DESC LIMIT 20").fetchall()
    return render_template("index.html", products=products, gateway_toggles=gateway_toggles, recent_charges=recent_charges, recent_subs=recent_subs)

@app.get("/admin")
def admin():
    if session.get("role", "customer") != "merchant":
        flash("Unauthorized: merchant role required", "error")
        return redirect(url_for("customer"))
    db = get_db()
    # Optional limit param: ?limit=50 (default) | 200 | all
    limit_raw = (request.args.get("limit") or "50").strip().lower()
    limit_val: int | None
    if limit_raw in ("all", "0", "-1"):
        limit_val = None
    else:
        try:
            limit_val = max(1, int(limit_raw))
        except Exception:
            limit_val = 50

    def _q(table: str, order_col: str = "rowid"):
        sql = f"SELECT * FROM {table} ORDER BY {order_col} DESC"
        if limit_val:
            sql += f" LIMIT {limit_val}"
        return db.execute(sql).fetchall()

    charges = _q("charges")
    subs = _q("subscriptions")
    refunds = _q("refunds")
    events = _q("events", order_col="id")
    return render_template(
        "admin.html",
        charges=charges,
        subs=subs,
        refunds=refunds,
        events=events,
    )


@app.get("/admin/export")
def admin_export():
    """
    Export all tables as JSON for admin inspection.
    Optional query: tables=charges,subscriptions,refunds,events (default: all)
    """
    db = get_db()
    tables_param = request.args.get("tables")
    wanted = {
        t.strip(): True
        for t in (tables_param.split(",") if tables_param else ["charges", "subscriptions", "refunds", "events"])
        if t.strip()
    }
    out: dict[str, list[dict]] = {}
    def dump(table: str):
        rows = db.execute(f"SELECT * FROM {table}").fetchall()
        out[table] = [dict(row) for row in rows]

    for t in ("charges", "subscriptions", "refunds", "events"):
        if wanted.get(t):
            dump(t)

    payload = json.dumps(out, ensure_ascii=False, indent=2)
    fn = "univapay_admin_export.json"
    return Response(payload, mimetype="application/json", headers={
        "Content-Disposition": f"attachment; filename={fn}"
    })


@app.post("/admin/backfill/charges")
def admin_backfill_charges():
    """
    Backfill missing amount/currency for charges by parsing stored JSON.
    Useful if earlier records were saved before effective fields were stored.
    """
    db = get_db()
    rows = db.execute("SELECT id, json FROM charges WHERE amount IS NULL OR currency IS NULL").fetchall()
    updated = 0
    for row in rows:
        try:
            data = json.loads(row["json"]) if row["json"] else {}
            amt = data.get("charged_amount") or data.get("requested_amount") or data.get("amount")
            cur = data.get("charged_currency") or data.get("requested_currency") or data.get("currency")
            if amt is not None or cur:
                db.execute(
                    "UPDATE charges SET amount=?, currency=? WHERE id=?",
                    (int(amt) if isinstance(amt, int) else None, (cur or None), row["id"]),
                )
                updated += 1
        except Exception:
            pass
    db.commit()
    return jsonify({"ok": True, "updated": updated, "checked": len(rows)})


# -------------------- Settings & Role --------------------
@app.get("/settings")
def settings_view():
    values = {
        "UNIVAPAY_JWT": get_setting("UNIVAPAY_JWT") or os.getenv("UNIVAPAY_JWT"),
        "UNIVAPAY_SECRET": get_setting("UNIVAPAY_SECRET") or os.getenv("UNIVAPAY_SECRET"),
        "UNIVAPAY_STORE_ID": get_setting("UNIVAPAY_STORE_ID") or os.getenv("UNIVAPAY_STORE_ID"),
        "UNIVAPAY_WEBHOOK_SECRET": get_setting("UNIVAPAY_WEBHOOK_SECRET") or os.getenv("UNIVAPAY_WEBHOOK_SECRET"),
        "UNIVAPAY_BASE_URL": get_setting("UNIVAPAY_BASE_URL") or os.getenv("UNIVAPAY_BASE_URL", "https://api.univapay.com"),
        "UNIVAPAY_WIDGET_URL": get_setting("UNIVAPAY_WIDGET_URL") or os.getenv("UNIVAPAY_WIDGET_URL"),
    }
    return render_template("settings.html", values=values)


@app.post("/settings")
def settings_save():
    if session.get("role", "customer") != "merchant":
        flash("Unauthorized: merchant role required", "error")
        return redirect(url_for("customer"))
    data = request.form
    for k in ("UNIVAPAY_JWT","UNIVAPAY_SECRET","UNIVAPAY_STORE_ID","UNIVAPAY_WEBHOOK_SECRET","UNIVAPAY_BASE_URL","UNIVAPAY_WIDGET_URL"):
        set_setting(k, (data.get(k) or "").strip())
    flash("Settings saved", "success")
    return redirect(url_for("settings_view"))


@app.get("/role/<role>")
def set_role(role: str):
    role = (role or "").strip().lower()
    if role not in ("customer", "merchant"):
        flash("Unknown role", "error")
        return redirect(url_for("customer"))
    session["role"] = role
    flash(f"Switched role to {role}", "info")
    return redirect(url_for("admin" if role == "merchant" else "customer"))

@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


# --------------- Widget config endpoints ---------------
@app.get("/api/widget-config")
def widget_config():
    """
    Returns a Univapay widget envelope for a given product & flavor.
    Query params:
      type = one_time | subscription | recurring
      amount (minor units) -> required
      period (for subscription)
      formId, buttonId, description
      gateways (optional JSON string of toggles; pass-through to extra)
    """
    kind = request.args.get("type", "one_time")
    amount = int(request.args.get("amount", "0"))
    form_id = request.args.get("formId", "form-auto")
    button_id = request.args.get("buttonId", "btn-auto")
    description = request.args.get("description", f"{kind} payment")
    period = request.args.get("period")
    extra_raw = request.args.get("gateways")
    extra: Dict[str, Any] = {}
    if extra_raw:
        try:
            extra = json.loads(extra_raw)
        except Exception:
            extra = {}

    log("Widget config request", {
        "kind": kind, "amount": amount, "period": period,
        "form_id": form_id, "button_id": button_id, "extra": extra
    })

    # Build envelope using SDK (uses UNIVAPAY_JWT from env)
    if kind == "one_time":
        payload = build_one_time_widget_config(
            amount=amount, form_id=form_id, button_id=button_id, description=description, payment_methods=extra
        )
    elif kind == "subscription":
        if not period:
            abort(400, "period is required for subscription")
        payload = build_subscription_widget_config(
            amount=amount, period=period, form_id=form_id, button_id=button_id, description=description, payment_methods=extra
        )
    elif kind == "recurring":
        payload = build_recurring_widget_config(
            amount=amount, form_id=form_id, button_id=button_id, description=description, payment_methods=extra
        )
    else:
        abort(400, "invalid type")

    log("Widget config response (truncated appId)", {"appId": payload.get("appId", "")[:10] + "..."})
    return jsonify(payload)


@app.get("/api/widget-config/sku/<sku>")
def widget_config_by_sku(sku: str):
    """
    Convenience: build widget config from a stored product SKU.
    Optional overrides via query: formId, buttonId, description
    """
    db = get_db()
    row = db.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
    if not row:
        abort(404, "Unknown SKU")

    form_id = request.args.get("formId", f"form-{sku}")
    button_id = request.args.get("buttonId", f"btn-{sku}")
    description = request.args.get("description", row["description"] or row["name"])

    kind = row["kind"]
    amount = int(row["amount_minor"])
    currency = (row["currency"] or "jpy").lower()
    period = row["period"]
    extra_raw = request.args.get("gateways")
    extra: Dict[str, Any] = {}
    if extra_raw:
        try:
            extra = json.loads(extra_raw)
        except Exception:
            extra = {}

    log("Widget-by-SKU", {"sku": sku, "kind": kind, "amount": amount, "currency": currency, "period": period})

    if kind == "one_time":
        payload = build_one_time_widget_config(
            amount=amount, form_id=form_id, button_id=button_id, description=description, payment_methods=extra
        )
    elif kind == "subscription":
        if not period:
            abort(400, "Product missing period for subscription")
        payload = build_subscription_widget_config(
            amount=amount, period=period, form_id=form_id, button_id=button_id, description=description, payment_methods=extra
        )
    elif kind == "recurring":
        payload = build_recurring_widget_config(
            amount=amount, form_id=form_id, button_id=button_id, description=description, payment_methods=extra
        )
    else:
        abort(400, "invalid product kind")

    return jsonify(payload)


# --------------- Server-side actions ---------------
@app.post("/api/charges")
def create_charge():
    """
    Create a (one-time or recurring) charge using a token id.
    Body JSON: { tokenId, amount, currency="jpy", capture=true, metadata? }
    """
    data = request.get_json(force=True) or {}
    log("POST /api/charges", {"body": data})

    token_id = data.get("tokenId")
    amount = data.get("amount")
    currency = (data.get("currency") or "jpy").lower()
    capture = bool(data.get("capture", True))
    metadata = safe_metadata(data.get("metadata")) if data.get("metadata") else None
    if not token_id or not isinstance(amount, int):
        return jsonify({"error": "tokenId and amount (int) required"}), 400

    cfg = make_config()
    idem = make_idempotency_key("one_time")
    with UnivapayClient(cfg, retries=1) as c:
        charges = ChargesAPI(c)
        ch = charges.create_one_time(
            token_id=token_id, amount=amount, currency=currency, capture=capture, metadata=metadata, idempotency_key=idem
        )

    # Store minimal record
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO charges (id,status,amount,currency,token_id,created_on,json) VALUES (?,?,?,?,?,?,?)",
        (
            ch.id,
            getattr(ch, "status", None),
            getattr(ch, "effective_amount", None),
            getattr(ch, "effective_currency", None),
            getattr(ch, "transaction_token_id", None),
            getattr(ch, "created_on", None),
            json.dumps(ch.model_dump(), ensure_ascii=False),
        ),
    )
    db.commit()
    log("Charge created", {"id": ch.id, "status": getattr(ch, "status", None)})
    return jsonify(ch.model_dump())


@app.get("/api/charges/<charge_id>")
def get_charge(charge_id: str):
    polling = (request.args.get("polling") or "").lower() in ("1", "true", "yes")
    cfg = make_config()
    with UnivapayClient(cfg, retries=1) as c:
        charges = ChargesAPI(c)
        ch = charges.get(charge_id, polling=polling)
    return jsonify(ch.model_dump())


@app.post("/api/subscriptions")
def create_subscription():
    """
    Create a subscription using a token id.
    Body JSON: { tokenId, amount, period, currency="jpy", metadata? }
    """
    data = request.get_json(force=True) or {}
    log("POST /api/subscriptions", {"body": data})

    token_id = data.get("tokenId")
    amount = data.get("amount")
    currency = (data.get("currency") or "jpy").lower()
    period = data.get("period")
    metadata = safe_metadata(data.get("metadata")) if data.get("metadata") else None
    if not token_id or not isinstance(amount, int) or not period:
        return jsonify({"error": "tokenId, amount (int) and period required"}), 400

    cfg = make_config()
    idem = make_idempotency_key("sub_create")
    with UnivapayClient(cfg, retries=1) as c:
        subs = SubscriptionsAPI(c)
        s = subs.create(token_id=token_id, amount=amount, period=period, currency=currency, metadata=metadata, idempotency_key=idem)

    # Persist
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO subscriptions (id,status,amount,currency,period,token_id,created_on,json) VALUES (?,?,?,?,?,?,?,?)",
        (
            s.id, getattr(s, "status", None), getattr(s, "amount", None), getattr(s, "currency", None),
            getattr(s, "period", None), getattr(s, "transaction_token_id", None), getattr(s, "created_on", None),
            json.dumps(s.model_dump(), ensure_ascii=False)
        ),
    )
    db.commit()
    log("Subscription created", {"id": s.id, "status": getattr(s, "status", None)})
    return jsonify(s.model_dump())


@app.get("/api/subscriptions/<subscription_id>")
def get_subscription(subscription_id: str):
    polling = (request.args.get("polling") or "").lower() in ("1", "true", "yes")
    cfg = make_config()
    with UnivapayClient(cfg, retries=1) as c:
        subs = SubscriptionsAPI(c)
        s = subs.get(subscription_id, polling=polling)
    return jsonify(s.model_dump())


@app.post("/api/subscriptions/<subscription_id>/cancel")
def cancel_subscription(subscription_id: str):
    """
    Cancel a subscription and persist the updated resource.
    """
    cfg = make_config()
    with UnivapayClient(cfg, retries=1) as c:
        subs = SubscriptionsAPI(c)
        s = subs.cancel(subscription_id)
        # Follow-up fetch with polling to capture latest status if it changes asynchronously
        try:
            s = subs.get(subscription_id, polling=True)
        except Exception:
            pass

    # Persist updated row (including any schedule/termination hints in JSON)
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO subscriptions (id,status,amount,currency,period,token_id,created_on,json) VALUES (?,?,?,?,?,?,?,?)",
        (
            s.id,
            getattr(s, "status", None),
            getattr(s, "amount", None),
            getattr(s, "currency", None),
            getattr(s, "period", None),
            getattr(s, "transaction_token_id", None),
            getattr(s, "created_on", None),
            json.dumps(s.model_dump(), ensure_ascii=False),
        ),
    )
    db.commit()
    log("Subscription canceled", {"id": s.id, "status": getattr(s, "status", None)})
    return jsonify(s.model_dump())


@app.post("/api/refunds/<charge_id>")
def refund_charge(charge_id: str):
    data = request.get_json(force=True) or {}
    log("POST /api/refunds/<charge_id>", {"charge_id": charge_id, "body": data})

    amount = data.get("amount")
    reason = data.get("reason")
    currency_override = data.get("currency")

    # Currency may be required by API for partial refunds; try to obtain it.
    currency_for_refund = None
    try:
        if currency_override:
            currency_for_refund = str(currency_override).strip()
        else:
            row = get_db().execute("SELECT currency FROM charges WHERE id=?", (charge_id,)).fetchone()
            if row and row["currency"]:
                currency_for_refund = str(row["currency"]).strip()
    except Exception:
        pass

    cfg = make_config()
    try:
        with UnivapayClient(cfg, retries=1) as c:
            refunds = RefundsAPI(c)
            payload_extra = {}
            # Include currency only for partial refunds when we have it
            if isinstance(amount, int) and currency_for_refund:
                payload_extra["currency"] = currency_for_refund.upper()
            if isinstance(reason, str) and reason.strip():
                payload_extra["reason"] = reason.strip()
            r = refunds.create(
                charge_id,
                amount=amount if isinstance(amount, int) else None,
                **payload_extra,
            )
    except UnivapayHTTPError as e:
        # Surface API error to client with 4xx/5xx code
        log("Refund API error", {"status": e.status, "code": e.code, "message": e.message_text})
        return jsonify({"ok": False, "status": e.status, "code": e.code, "message": e.message_text}), int(e.status)
    # Save
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO refunds (id,charge_id,amount,status,created_on,json) VALUES (?,?,?,?,?,?)",
        (r.id, charge_id, getattr(r, "amount", None), getattr(r, "status", None), getattr(r, "created_on", None), json.dumps(r.model_dump(), ensure_ascii=False)),
    )
    db.commit()
    log("Refund created", {"refund_id": r.id, "charge_id": charge_id})
    return jsonify(r.model_dump())


@app.get("/api/refunds/<charge_id>/<refund_id>")
def get_refund(charge_id: str, refund_id: str):
    """
    Fetch a refund (optionally with server-side polling), persist, and return it.
    Query param: polling=true|false (default true)
    """
    polling = (request.args.get("polling") or "1").lower() in ("1", "true", "yes")
    cfg = make_config()
    with UnivapayClient(cfg, retries=1) as c:
        refunds = RefundsAPI(c)
        r = refunds.get(charge_id=charge_id, refund_id=refund_id, polling=polling)

    # Persist latest state
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO refunds (id,charge_id,amount,status,created_on,json) VALUES (?,?,?,?,?,?)",
        (
            r.id,
            charge_id,
            getattr(r, "amount", None),
            getattr(r, "status", None),
            getattr(r, "created_on", None),
            json.dumps(r.model_dump(), ensure_ascii=False),
        ),
    )
    db.commit()
    log("Refund refreshed", {"refund_id": r.id, "status": getattr(r, "status", None)})
    return jsonify(r.model_dump())


@app.post("/api/cancels/<charge_id>")
def cancel_charge(charge_id: str):
    cfg = make_config()
    with UnivapayClient(cfg, retries=1) as c:
        cancels = CancelsAPI(c)
        ch = cancels.cancel_charge(charge_id)
    # update local
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO charges (id,status,amount,currency,token_id,created_on,json) VALUES (?,?,?,?,?,?,?)",
        (
            ch.id,
            getattr(ch, "status", None),
            getattr(ch, "effective_amount", None),
            getattr(ch, "effective_currency", None),
            getattr(ch, "transaction_token_id", None),
            getattr(ch, "created_on", None),
            json.dumps(ch.model_dump(), ensure_ascii=False),
        ),
    )
    db.commit()
    log("Charge canceled", {"id": ch.id, "status": getattr(ch, "status", None)})
    return jsonify(ch.model_dump())


@app.get("/api/tokens/<token_id>")
def get_token(token_id: str):
    cfg = make_config()
    with UnivapayClient(cfg, retries=0) as c:
        tokens = TokensAPI(c)
        t = tokens.get(token_id)
    log("Token fetched", {"id": token_id, "type": getattr(t, "token_type", None)})
    return jsonify(t.model_dump())


@app.post("/api/ingest/charge/<charge_id>")
def ingest_charge(charge_id: str):
    """
    Fetch and store a charge from the API (called by frontend after widget success).
    """
    log("POST /api/ingest/charge/<charge_id>", {"charge_id": charge_id})

    cfg = make_config()
    with UnivapayClient(cfg, retries=1) as c:
        charges = ChargesAPI(c)
        ch = charges.get(charge_id, polling=True)
    
    # Store/update in local DB
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO charges (id,status,amount,currency,token_id,created_on,json) VALUES (?,?,?,?,?,?,?)",
        (
            ch.id,
            getattr(ch, "status", None),
            getattr(ch, "effective_amount", None),
            getattr(ch, "effective_currency", None),
            getattr(ch, "transaction_token_id", None),
            getattr(ch, "created_on", None),
            json.dumps(ch.model_dump(), ensure_ascii=False),
        ),
    )
    db.commit()
    log("Charge ingested", {"id": ch.id, "status": getattr(ch, "status", None)})
    return jsonify(ch.model_dump())


@app.post("/api/ingest/subscription/<subscription_id>")
def ingest_subscription(subscription_id: str):
    """
    Fetch and store a subscription from the API (called by frontend after widget success).
    """
    log("POST /api/ingest/subscription/<subscription_id>", {"subscription_id": subscription_id})

    cfg = make_config()
    with UnivapayClient(cfg, retries=1) as c:
        subs = SubscriptionsAPI(c)
        s = subs.get(subscription_id, polling=True)
    
    # Store/update in local DB
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO subscriptions (id,status,amount,currency,period,token_id,created_on,json) VALUES (?,?,?,?,?,?,?,?)",
        (
            s.id, getattr(s, "status", None), getattr(s, "amount", None), getattr(s, "currency", None),
            getattr(s, "period", None), getattr(s, "transaction_token_id", None), getattr(s, "created_on", None),
            json.dumps(s.model_dump(), ensure_ascii=False)
        ),
    )
    db.commit()
    log("Subscription ingested", {"id": s.id, "status": getattr(s, "status", None)})
    return jsonify(s.model_dump())


# --------------- Webhook ---------------
@app.post("/webhook/univapay")
def webhook():
    raw_body = request.data  # bytes
    headers = {k: v for k, v in request.headers.items()}
    # Always verify in real mode; if secret is missing, fail fast
    if not WEBHOOK_SECRET:
        return jsonify({"ok": False, "error": "server misconfigured: UNIVAPAY_WEBHOOK_SECRET missing"}), 500

    try:
        ev = parse_event(
            body=raw_body,
            headers=headers,
            secret=WEBHOOK_SECRET,
            skip_verification=False,
        )
        payload = ev.data  # original JSON
        etype = ev.type
        rtype = ev.resource_type
        created_on = ev.created_on or ev.created

        db = get_db()
        db.execute(
            "INSERT INTO events (type,resource_type,created_on,payload_json) VALUES (?,?,?,?)",
            (
                etype,
                rtype,
                created_on,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        db.commit()
        log("Webhook stored", {"type": etype, "resource": rtype, "verified": True})
        return jsonify({"ok": True, "verified": True})
    except WebhookVerificationError as e:
        log("Webhook signature failed", {"error": str(e)})
        return jsonify({"ok": False, "error": "signature verification failed"}), 400
    except Exception as e:
        log("Webhook error", {"error": repr(e)})
        return jsonify({"ok": False, "error": "invalid payload"}), 400


# -------------------- Simple views to trigger API actions --------------------
@app.post("/buy/<sku>")
def buy_now(sku: str):
    # This route is hit after FE gets a token and posts /api/charges;
    # Here we just redirect to admin for demo.
    flash(f"Purchase flow triggered for {sku}", "info")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    log("Starting Flask app", {
        "port": int(os.getenv("PORT", "5001")),
        "debug": os.getenv("FLASK_DEBUG", "1").lower() not in ("0","false","no"),
        "widget_verification": bool(WEBHOOK_SECRET),
    })
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5001")), debug=os.getenv("FLASK_DEBUG", "1") not in ("0","false","no"))
