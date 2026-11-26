import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_PATH = os.path.join(DATA_DIR, "cache.json")
CACHE_TTL_SECONDS = 12 * 3600

SEC_UA = os.environ.get(
    "AUTOPILOT_SEC_UA",
    "Portfolio-Autopilot/1.0 (personal educational use; contact: you@example.com)",
)

PROGRESS = {"active": False, "done": 0, "total": 0, "current": ""}
_PROGRESS_LOCK = threading.Lock()

MANAGERS = [
    {"cik": "1067983", "name": "Berkshire Hathaway"},
    {"cik": "1697748", "name": "ARK Investment Management"},
    {"cik": "1649339", "name": "Scion Asset Management (Michael Burry)"},
    {"cik": "1037389", "name": "Renaissance Technologies"},
    {"cik": "1336528", "name": "Pershing Square (Bill Ackman)"},
    {"cik": "1006438", "name": "Appaloosa Management (David Tepper)"},
    {"cik": "1423053", "name": "Citadel Advisors (Ken Griffin)"},
    {"cik": "1179392", "name": "Two Sigma Investments"},
    {"cik": "1040273", "name": "Third Point (Dan Loeb)"},
    {"cik": "1167483", "name": "Tiger Global (Chase Coleman)"},
    {"cik": "1135730", "name": "Coatue Management"},
    {"cik": "1079114", "name": "Greenlight Capital (David Einhorn)"},
    {"cik": "1029160", "name": "Soros Fund Management"},
    {"cik": "1166559", "name": "Gates Foundation Trust"},
]

SUFFIX_TOKENS = {
    "INC", "CORP", "CORPORATION", "CO", "LTD", "LIMITED", "PLC", "COMPANY",
    "COM", "NEW", "CL", "CLASS", "A", "B", "C", "ORD", "SHS", "SH", "COMMON",
    "STOCK", "DEPOSITARY", "SPONSORED", "ADS", "REPRESENTING", "SHARES", "US",
    "THE", "HLDGS", "HOLDINGS", "GROUP", "INTERNATIONAL", "GLOBAL", "TR",
}

MANUAL_TICKER_OVERRIDES = {
    "BERKSHIRE HATHAWAY": "BRK.B",
    "ALPHABET": "GOOGL",
    "META PLATFORMS": "META",
    "INVESCO QQQ": "QQQ",
    "INVESCO EXCHANGE TRADED FUND TRUST": "QQQ",
}


def _http_get(url, as_json=False, timeout=45):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": SEC_UA, "Accept-Encoding": "identity"},
    )
    last_exc = None
    for delay in (0, 2, 5, 10, 20):
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            if as_json:
                return json.loads(raw.decode("utf-8", "replace"))
            return raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in (429, 500, 502, 503):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_exc = exc
    raise last_exc


def normalize_name(name):
    tokens = [
        t for t in re.sub(r"[^A-Z0-9]+", " ", (name or "").upper()).split()
        if t and t not in SUFFIX_TOKENS
    ]
    return " ".join(tokens)


_TICKER_MAP = None
_TICKER_LOCK = threading.Lock()


def _ticker_map():
    global _TICKER_MAP
    with _TICKER_LOCK:
        if _TICKER_MAP is not None:
            return _TICKER_MAP
        path = os.path.join(DATA_DIR, "tickers.json")
        try:
            with open(path) as f:
                _TICKER_MAP = json.load(f)
            return _TICKER_MAP
        except (OSError, ValueError):
            pass
        try:
            data = _http_get("https://www.sec.gov/files/company_tickers.json", as_json=True)
            mapping = {}
            for row in data.values():
                ticker = row.get("ticker", "").upper()
                key = normalize_name(row.get("title", ""))
                if key and ticker and key not in mapping:
                    mapping[key] = ticker
            _TICKER_MAP = mapping
            with open(path, "w") as f:
                json.dump(mapping, f)
        except Exception:
            _TICKER_MAP = {}
        return _TICKER_MAP


def resolve_ticker(issuer_name):
    key = normalize_name(issuer_name)
    if not key:
        return None
    if key in MANUAL_TICKER_OVERRIDES:
        return MANUAL_TICKER_OVERRIDES[key]
    mapping = _ticker_map()
    if key in mapping:
        return mapping[key]
    key_tokens = set(key.split())
    if key_tokens:
        best, best_score = None, 0.0
        for map_key, ticker in mapping.items():
            map_tokens = set(map_key.split())
            if not map_tokens:
                continue
            score = len(key_tokens & map_tokens) / len(key_tokens | map_tokens)
            if score > best_score:
                best, best_score = ticker, score
        if best_score >= 0.75:
            return best
    return None


def _list_13f_filings(cik):
    data = _http_get(f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json", as_json=True)
    recent = data["filings"]["recent"]
    filings = []
    for form, accession, filed, period, primary in zip(
        recent["form"],
        recent["accessionNumber"],
        recent["filingDate"],
        recent["reportDate"],
        recent["primaryDocument"],
    ):
        if form in ("13F-HR", "13F-HR/A") and period:
            filings.append(
                {
                    "form": form,
                    "accession": accession,
                    "filed": filed,
                    "period": period,
                    "primary": primary,
                }
            )
    filings.sort(key=lambda f: (f["period"], f["filed"]), reverse=True)
    return filings


def _local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def _parse_holdings_xml(xml_text):
    root = ET.fromstring(xml_text)
    if not _local(root.tag).endswith("informationtable"):
        return None
    holdings = {}
    for info in root.iter():
        if _local(info.tag) != "infotable":
            continue
        children = {_local(c.tag): (c.text or "").strip() for c in info}

        def child(tag):
            return children.get(tag, "")
        issuer = child("nameofissuer")
        cusip = child("cusip")
        if not issuer:
            continue
        put_call = child("putcall").upper() or ""
        key = (cusip, put_call)
        entry = holdings.setdefault(
            key,
            {
                "issuer": issuer,
                "cusip": cusip,
                "put_call": put_call,
                "title": child("titleofclass") or "COMMON STOCK",
                "shares": 0,
                "value": 0,
            },
        )
        try:
            entry["shares"] += int(float(child("sshprnamt") or 0))
        except ValueError:
            pass
        try:
            entry["value"] += int(float(child("value") or 0))
        except ValueError:
            pass
    return list(holdings.values())


def _fetch_holdings(cik, filing):
    accession_nodash = filing["accession"].replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik.zfill(10)}/{accession_nodash}/"
    index = _http_get(base + "index.json", as_json=True)
    candidates = [
        item["name"]
        for item in index["directory"]["item"]
        if item["name"].lower().endswith(".xml")
        and item["name"] != filing["primary"].split("/")[-1]
        and "xsl" not in item["name"].lower()
    ]
    candidates.sort(key=lambda n: -int(index_index_size(index, n)))
    for name in candidates:
        try:
            xml_text = _http_get(base + urllib.parse.quote(name))
            holdings = _parse_holdings_xml(xml_text)
        except (ET.ParseError, ValueError, KeyError):
            continue
        if holdings:
            return holdings
    return None


def index_index_size(index, name):
    for item in index["directory"]["item"]:
        if item["name"] == name:
            return item.get("size", "0")
    return "0"


def _manager_report(manager, filings):
    by_period = {}
    for filing in filings:
        by_period.setdefault(filing["period"], filing)
    periods = sorted(by_period, reverse=True)
    current_period = periods[0] if periods else None
    previous_period = periods[1] if len(periods) > 1 else None

    current = _fetch_holdings(manager["cik"], by_period[current_period]) if current_period else None
    previous = _fetch_holdings(manager["cik"], by_period[previous_period]) if previous_period else None

    if current is None:
        return None

    filed = by_period[current_period]["filed"]
    total_value = sum(h["value"] for h in current)
    for h in current:
        h["weight"] = (h["value"] / total_value) if total_value else 0.0

    signals = []
    current_keys = {(h["cusip"], h["put_call"]): h for h in current}
    previous_keys = {(h["cusip"], h["put_call"]): h for h in (previous or [])}

    for key, h in current_keys.items():
        prev = previous_keys.get(key)
        if prev is None:
            signals.append(_signal(h, "NEW", 1.0, h["value"], 0, h["shares"], 0))
        elif h["shares"] > 0:
            if prev["shares"] > 0:
                pct = (h["shares"] - prev["shares"]) / prev["shares"]
            else:
                pct = 1.0
            if pct >= 0.05:
                signals.append(_signal(h, "INCREASED", pct, h["value"], prev["value"], h["shares"], prev["shares"]))
            elif pct <= -0.05:
                signals.append(_signal(h, "REDUCED", pct, h["value"], prev["value"], h["shares"], prev["shares"]))
        else:
            signals.append(_signal(h, "EXIT", -1.0, 0, prev["value"], 0, prev["shares"]))

    for key, prev in previous_keys.items():
        if key not in current_keys:
            signals.append(_signal(prev, "EXIT", -1.0, 0, prev["value"], 0, prev["shares"]))

    action_rank = {"NEW": 0, "EXIT": 1, "INCREASED": 2, "REDUCED": 3}
    signals.sort(key=lambda s: (action_rank[s["action"]], -(s["cur_value"] or s["prev_value"])))
    signals = signals[:120]

    top = sorted(current, key=lambda h: -h["value"])[:15]

    return {
        "cik": manager["cik"],
        "name": manager["name"],
        "period": current_period,
        "period_previous": previous_period,
        "filed": filed,
        "total_value": total_value,
        "holdings_count": len(current),
        "top": [_holding_view(h) for h in top],
        "signals": signals,
    }


def _holding_view(h):
    return {
        "issuer": h["issuer"],
        "ticker": resolve_ticker(h["issuer"]),
        "cusip": h["cusip"],
        "weight": round(h["weight"], 6),
        "value": h["value"],
        "shares": h["shares"],
    }


def _signal(h, action, pct, cur_value, prev_value, cur_shares, prev_shares):
    return {
        "issuer": h["issuer"],
        "ticker": resolve_ticker(h["issuer"]),
        "cusip": h["cusip"],
        "action": action,
        "pct": round(pct, 4),
        "cur_value": cur_value,
        "prev_value": prev_value,
        "cur_shares": cur_shares,
        "prev_shares": prev_shares,
    }


def build_consensus(reports):
    positions = {}
    for report in reports:
        total_now = report["total_value"]
        seen_now = {}
        for holding in report.get("_current") or []:
            holding = dict(holding)
            holding["weight"] = (holding["value"] / total_now) if total_now else 0.0
            seen_now[holding["cusip"]] = holding
        seen_prev = {}
        prev_total = sum(h["value"] for h in (report.get("_previous") or []))
        for holding in report.get("_previous") or []:
            holding = dict(holding)
            holding["weight"] = (holding["value"] / prev_total) if prev_total else 0.0
            seen_prev[holding["cusip"]] = holding

        for cusip, h in seen_now.items():
            slot = positions.setdefault(
                cusip,
                {"issuer": h["issuer"], "managers_now": 0, "managers_prev": 0, "net": 0.0, "weights": [], "prev_weights": []},
            )
            slot["managers_now"] += 1
            slot["weights"].append(h["weight"])
            prev = seen_prev.get(cusip)
            prev_value = prev["value"] if prev else 0
            slot["net"] += h["value"] - prev_value
            if prev is None:
                slot["net"] += 0

        for cusip, prev in seen_prev.items():
            slot = positions.setdefault(
                cusip,
                {"issuer": prev["issuer"], "managers_now": 0, "managers_prev": 0, "net": 0.0, "weights": [], "prev_weights": []},
            )
            slot["managers_prev"] += 1
            slot["prev_weights"].append(prev["weight"])
            if cusip not in seen_now:
                slot["net"] -= prev["value"]

    buys, sells = [], []
    for cusip, slot in positions.items():
        issuer = slot["issuer"]
        weight = sum(slot["weights"]) / len(slot["weights"]) if slot["weights"] else 0.0
        prev_weight = sum(slot["prev_weights"]) / len(slot["prev_weights"]) if slot["prev_weights"] else 0.0
        entry = {
            "issuer": issuer,
            "ticker": resolve_ticker(issuer),
            "cusip": cusip,
            "net": slot["net"],
            "weight": round(weight, 6),
            "prev_weight": round(prev_weight, 6),
            "managers_now": slot["managers_now"],
            "managers_prev": slot["managers_prev"],
            "managers_active": slot["managers_now"] + slot["managers_prev"],
        }
        if slot["net"] > 0:
            buys.append(entry)
        elif slot["net"] < 0:
            sells.append(entry)

    buys.sort(key=lambda e: -e["net"])
    sells.sort(key=lambda e: e["net"])
    return {"buys": buys[:25], "sells": sells[:25]}


def refresh(force=False):
    os.makedirs(DATA_DIR, exist_ok=True)
    cached = _load_cache()
    if cached and not force and time.time() - cached.get("fetched_at", 0) < CACHE_TTL_SECONDS:
        return cached

    def run(manager):
        set_progress(True, current=manager["name"])
        try:
            filings = _list_13f_filings(manager["cik"])
            report = _manager_report(manager, filings)
            if report:
                by_period = {}
                for filing in filings:
                    by_period.setdefault(filing["period"], filing)
                periods = sorted(by_period, reverse=True)
                report["_current"] = _fetch_holdings(manager["cik"], by_period[periods[0]]) if periods else []
                report["_previous"] = _fetch_holdings(manager["cik"], by_period[periods[1]]) if len(periods) > 1 else []
            return report
        except Exception as exc:
            return {"cik": manager["cik"], "name": manager["name"], "error": str(exc)}
        finally:
            with _PROGRESS_LOCK:
                PROGRESS["done"] += 1

    with ThreadPoolExecutor(max_workers=3) as pool:
        set_progress(True, done=0, total=len(MANAGERS))
        results = list(pool.map(run, MANAGERS))
        set_progress(False, current="")

    if cached:
        cached_by_cik = {m.get("cik"): m for m in cached.get("managers", [])}
        results = [
            cached_by_cik.get(r.get("cik"), r) if (r and "error" in r) else r
            for r in results
        ]

    reports = [r for r in results if r and "error" not in r]
    errors = [r for r in results if r and "error" in r]

    cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 270 * 86400))
    for report in reports:
        report["stale"] = bool(report["period"] and report["period"] < cutoff)
    fresh = [r for r in reports if not r["stale"]]
    consensus = build_consensus(fresh)
    for r in reports:
        r.pop("_current", None)
        r.pop("_previous", None)

    data = {
        "fetched_at": time.time(),
        "fetched_at_iso": datetime.now(timezone.utc).isoformat(),
        "managers": sorted(reports, key=lambda r: -r["total_value"]),
        "errors": errors,
        "consensus": consensus,
    }
    tmp_path = CACHE_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f)
    os.replace(tmp_path, CACHE_PATH)
    return data


def _load_cache():
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def set_progress(active, done=None, current="", total=None):
    with _PROGRESS_LOCK:
        PROGRESS["active"] = active
        if done is not None:
            PROGRESS["done"] = done
        if current is not None:
            PROGRESS["current"] = current
        if total is not None:
            PROGRESS["total"] = total


def get_progress():
    with _PROGRESS_LOCK:
        return dict(PROGRESS)


def get_summary():
    cached = _load_cache()
    if cached:
        cached["stale"] = time.time() - cached.get("fetched_at", 0) > CACHE_TTL_SECONDS
        return cached
    return refresh(force=True)


if __name__ == "__main__":
    data = refresh(force=True)
    print(f"Fetched {len(data['managers'])} managers, {len(data['errors'])} errors")
    for m in data["managers"]:
        print(f"  {m['name']:45s} period={m['period']} filed={m['filed']} value=${m['total_value']/1e9:.1f}B signals={len(m['signals'])}")
    for e in data["errors"]:
        print(f"  ERROR {e['name']}: {e['error'][:100]}")
