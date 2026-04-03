"""Tool: fetch_sf_permits

Fetch San Francisco permit and complaint history from DBI (dbiweb02) only.
"""

from __future__ import annotations

from datetime import datetime, timezone
import html
import re
from typing import Any
from urllib.parse import urlencode

import httpx

_DBI_BASE = "https://dbiweb02.sfgov.org/dbipts"

_SUFFIX_TO_DBI = {
    "ST": "ST",
    "STREET": "ST",
    "AVE": "AV",
    "AV": "AV",
    "AVENUE": "AV",
    "RD": "RD",
    "ROAD": "RD",
    "BLVD": "BL",
    "BOULEVARD": "BL",
    "DR": "DR",
    "DRIVE": "DR",
    "CT": "CT",
    "COURT": "CT",
    "LN": "LA",
    "LANE": "LA",
    "PL": "PL",
    "PLACE": "PL",
    "WAY": "WY",
}

_PANEL_MAP = {
    "EID": "electrical",
    "PID": "plumbing",
    "BID": "building",
}


def _empty_result(address: str | None = None, source_detail: str | None = None) -> dict[str, Any]:
    return {
        "source": "none",
        "source_detail": source_detail,
        "address": address,
        "open_permits_count": 0,
        "recent_permits_5y": 0,
        "major_permits_10y": 0,
        "oldest_open_permit_age_days": None,
        "permit_counts_by_type": {
            "electrical": 0,
            "plumbing": 0,
            "building": 0,
        },
        "complaints_open_count": 0,
        "complaints_recent_3y": 0,
        "flags": [],
        "permits": [],
        "complaints": [],
    }


def _clean_text(raw: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", raw or "")
    unescaped = html.unescape(no_tags).replace("\xa0", " ")
    return re.sub(r"\s+", " ", unescaped).strip()


def _extract_hidden(html_text: str, name: str) -> str | None:
    m = re.search(rf'name="{re.escape(name)}"[^>]*value="([^"]*)"', html_text, flags=re.IGNORECASE)
    if not m:
        return None
    return html.unescape(m.group(1))


def _parse_address_parts(address_matched: str) -> tuple[str, str, str]:
    street = (address_matched or "").split(",")[0].strip().upper()
    parts = [p for p in street.split() if p]
    if not parts or len(parts) < 2:
        return "", "", ""

    number = parts[0]
    suffix_raw = parts[-1]
    suffix = _SUFFIX_TO_DBI.get(suffix_raw, suffix_raw[:2])
    street_name = " ".join(parts[1:-1]) if len(parts) > 2 else parts[1]
    return number, street_name, suffix


def _parse_us_date(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _is_open_status(status: str | None) -> bool:
    if not status:
        return True
    s = status.strip().lower()
    return not any(term in s for term in ("complete", "closed", "final", "resolved", "cancel"))


def _extract_redirect_path(post_html: str) -> str | None:
    m = re.search(r'<a href="([^"]*\?page=address[^"]*)"', post_html, flags=re.IGNORECASE)
    if not m:
        return None
    return html.unescape(m.group(1))


async def _fetch_address_list_html(
    client: httpx.AsyncClient,
    number: str,
    street_name: str,
    suffix: str,
    unit: str | None,
) -> str:
    # Prefer direct DBI address query URL; this avoids brittle ASP.NET event-validation.
    params = urlencode({
        "page": "address",
        "StreetNumber": number,
        "StreetName": street_name,
        "StreetSuffix": suffix,
        "Unit": unit or "",
        "Block": "",
        "Lot": "",
    })
    direct_url = f"{_DBI_BASE}/?{params}"
    direct_resp = await client.get(direct_url)
    direct_resp.raise_for_status()
    if "AddressID=" in direct_resp.text:
        return direct_resp.text

    # Fallback: form post flow (kept as resilience path).
    query_url = f"{_DBI_BASE}/default.aspx?page=AddressQuery"
    query_resp = await client.get(query_url)
    query_resp.raise_for_status()
    query_html = query_resp.text

    viewstate = _extract_hidden(query_html, "__VIEWSTATE")
    viewstate_gen = _extract_hidden(query_html, "__VIEWSTATEGENERATOR")
    eventvalidation = _extract_hidden(query_html, "__EVENTVALIDATION")
    if not (viewstate and viewstate_gen and eventvalidation):
        return direct_resp.text

    post_url = f"{_DBI_BASE}/Default2.aspx?page=AddressQuery"
    form_data = {
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEGENERATOR": viewstate_gen,
        "__EVENTVALIDATION": eventvalidation,
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "InfoReq1$txtStreetNumber": number,
        "InfoReq1$txtStreetName": street_name,
        "InfoReq1$cboStreetSuffix": suffix,
        "InfoReq1$txtUnit": unit or "",
        "InfoReq1$txtBlock": "",
        "InfoReq1$txtLot": "",
        "InfoReq1$cmdSearch": "Search",
    }
    post_resp = await client.post(post_url, data=form_data)
    post_resp.raise_for_status()

    redirect_path = _extract_redirect_path(post_resp.text)
    if redirect_path:
        address_list_url = f"https://dbiweb02.sfgov.org{redirect_path}"
        list_resp = await client.get(address_list_url)
        list_resp.raise_for_status()
        return list_resp.text
    return post_resp.text


def _extract_table_rows(html_text: str, table_id: str) -> list[dict[str, str]]:
    tm = re.search(rf'<table[^>]*id="{re.escape(table_id)}"[^>]*>(.*?)</table>', html_text, flags=re.IGNORECASE | re.DOTALL)
    if not tm:
        return []

    table_html = tm.group(1)
    tr_blocks = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL)
    if len(tr_blocks) < 2:
        return []

    header_cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr_blocks[0], flags=re.IGNORECASE | re.DOTALL)
    headers = [_clean_text(h) for h in header_cells]
    rows: list[dict[str, str]] = []

    for tr in tr_blocks[1:]:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, flags=re.IGNORECASE | re.DOTALL)
        if not cells:
            continue
        row = {}
        for i, header in enumerate(headers):
            if i >= len(cells):
                break
            row[header] = _clean_text(cells[i])
        row["_row_html"] = tr
        rows.append(row)

    return rows


def _extract_href_from_row(row_html: str) -> str | None:
    m = re.search(r'<a href="([^"]+)"', row_html, flags=re.IGNORECASE)
    if not m:
        return None
    href = html.unescape(m.group(1))
    if href.startswith("http"):
        return href
    return f"{_DBI_BASE}/{href.lstrip('/')}"


def _extract_address_candidates(address_list_html: str) -> list[dict[str, str]]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", address_list_html, flags=re.IGNORECASE | re.DOTALL)
    candidates: list[dict[str, str]] = []
    for row in rows:
        if "AddressID=" not in row or "Select" not in row:
            continue
        href_m = re.search(r'href="([^"]*AddressID=\d+)"', row, flags=re.IGNORECASE)
        if not href_m:
            continue
        href = html.unescape(href_m.group(1))
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 3:
            continue

        number = _clean_text(cells[1]) if len(cells) > 1 else ""
        street = _clean_text(cells[2]) if len(cells) > 2 else ""
        unit = _clean_text(cells[3]) if len(cells) > 3 else ""
        block = _clean_text(cells[4]) if len(cells) > 4 else ""
        lot = _clean_text(cells[5]) if len(cells) > 5 else ""

        candidates.append({
            "href": href,
            "number": number,
            "street": street,
            "unit": unit,
            "block": block,
            "lot": lot,
        })
    return candidates


def _choose_best_candidate(
    candidates: list[dict[str, str]],
    number: str,
    street_name: str,
    suffix: str,
    unit: str | None,
) -> dict[str, str] | None:
    if not candidates:
        return None

    target_street = f"{street_name} {suffix}".strip()
    unit_norm = (unit or "").strip().upper()

    def score(c: dict[str, str]) -> tuple[int, int, int]:
        c_number = c.get("number", "").strip().upper()
        c_street = c.get("street", "").strip().upper()
        c_unit = c.get("unit", "").strip().upper()
        exact_number = 1 if c_number == number else 0
        exact_street = 1 if c_street == target_street else 0
        exact_unit = 1 if unit_norm and c_unit == unit_norm else 0
        return (exact_street, exact_number, exact_unit)

    ranked = sorted(candidates, key=score, reverse=True)
    return ranked[0]


def _parse_permits(panel_html: str, panel_code: str) -> list[dict[str, Any]]:
    table_id = f"InfoReq1_dg{panel_code}"
    rows = _extract_table_rows(panel_html, table_id)
    permit_type = _PANEL_MAP.get(panel_code, panel_code.lower())

    permits: list[dict[str, Any]] = []
    for row in rows:
        permit_no = row.get("Permit #", "")
        status = row.get("Current Stage") or row.get("Status") or None
        stage_date_iso = _parse_us_date(row.get("Stage Date"))
        href = _extract_href_from_row(row.get("_row_html", ""))

        permits.append({
            "permit_number": permit_no,
            "filed_date": stage_date_iso,
            "issued_date": None,
            "completed_date": stage_date_iso if status and status.strip().upper() == "COMPLETE" else None,
            "status": status,
            "permit_type": permit_type,
            "work_description": row.get("Street Name") or None,
            "estimated_cost": None,
            "address": f"{row.get('Street #', '').strip()} {row.get('Street Name', '').strip()}".strip() or None,
            "unit": row.get("Unit") or None,
            "source_url": href,
        })
    return permits


def _parse_complaints(panel_html: str) -> list[dict[str, Any]]:
    rows = _extract_table_rows(panel_html, "InfoReq1_dgCTS")
    complaints: list[dict[str, Any]] = []

    for row in rows:
        complaint_no = row.get("Complaint #", "")
        href = _extract_href_from_row(row.get("_row_html", ""))
        complaints.append({
            "complaint_number": complaint_no,
            "date_filed": _parse_us_date(row.get("Date Filed")),
            "status": row.get("Status") or None,
            "division": row.get("Div") or None,
            "expired": row.get("Expired") or None,
            "address": f"{row.get('Street #', '').strip()} {row.get('Street Name', '').strip()}".strip() or None,
            "source_url": href,
        })

    return complaints


async def fetch_sf_permits(
    address_matched: str,
    unit: str | None = None,
    max_results: int = 25,
) -> dict[str, Any]:
    """Fetch SF permit and complaint history from DBI only."""
    del max_results  # DBI UI controls row count; keep arg for compatibility.

    base = _empty_result(address=address_matched)

    number, street_name, suffix = _parse_address_parts(address_matched)
    if not number or not street_name:
        base["source_detail"] = "invalid_address"
        return base

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            # Step 1: load address list from direct URL (or form fallback).
            address_list_html = await _fetch_address_list_html(
                client=client,
                number=number,
                street_name=street_name,
                suffix=suffix,
                unit=unit,
            )

            # Step 2: select best candidate address.
            candidates = _extract_address_candidates(address_list_html)
            chosen = _choose_best_candidate(candidates, number, street_name, suffix, unit)
            if not chosen:
                return _empty_result(address=address_matched, source_detail="dbi_no_address_match")

            selected_url = f"{_DBI_BASE}/{chosen['href'].lstrip('/')}"
            selected_resp = await client.get(selected_url)
            selected_resp.raise_for_status()

            # Step 3: fetch panel pages in selected-address session context.
            permits: list[dict[str, Any]] = []
            for panel_code in ("EID", "PID", "BID"):
                panel_url = f"{_DBI_BASE}/default.aspx?page=AddressData2&ShowPanel={panel_code}"
                panel_resp = await client.get(panel_url)
                panel_resp.raise_for_status()
                permits.extend(_parse_permits(panel_resp.text, panel_code))

            complaints_url = f"{_DBI_BASE}/default.aspx?page=AddressData2&ShowPanel=CTS"
            complaints_resp = await client.get(complaints_url)
            complaints_resp.raise_for_status()
            complaints = _parse_complaints(complaints_resp.text)

    except Exception as exc:
        return _empty_result(address=address_matched, source_detail=f"dbi_error:{type(exc).__name__}")

    now = datetime.now(timezone.utc)
    five_year_cutoff = now.replace(year=now.year - 5)
    three_year_cutoff = now.replace(year=now.year - 3)

    permit_counts_by_type = {"electrical": 0, "plumbing": 0, "building": 0}
    open_permits: list[dict[str, Any]] = []
    recent_permits = 0

    for permit in permits:
        ptype = str(permit.get("permit_type") or "").lower()
        if ptype in permit_counts_by_type:
            permit_counts_by_type[ptype] += 1

        status = permit.get("status")
        if _is_open_status(status):
            open_permits.append(permit)

        filed = permit.get("filed_date")
        if filed:
            try:
                filed_dt = datetime.strptime(filed, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if filed_dt >= five_year_cutoff:
                    recent_permits += 1
            except ValueError:
                pass

    oldest_open_permit_age_days: int | None = None
    if open_permits:
        filed_dates = []
        for permit in open_permits:
            filed = permit.get("filed_date")
            if not filed:
                continue
            try:
                filed_dates.append(datetime.strptime(filed, "%Y-%m-%d").replace(tzinfo=timezone.utc))
            except ValueError:
                continue
        if filed_dates:
            oldest_open_permit_age_days = max(0, (now - min(filed_dates)).days)

    complaints_open_count = 0
    complaints_recent_3y = 0
    for complaint in complaints:
        status = complaint.get("status")
        if _is_open_status(status):
            complaints_open_count += 1

        filed = complaint.get("date_filed")
        if filed:
            try:
                filed_dt = datetime.strptime(filed, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if filed_dt >= three_year_cutoff:
                    complaints_recent_3y += 1
            except ValueError:
                pass

    flags: list[str] = []
    if oldest_open_permit_age_days is not None and oldest_open_permit_age_days > 365:
        flags.append("open_over_365_days")
    if complaints_open_count > 0 or complaints_recent_3y > 0:
        flags.append("recent_complaints")
    if not permits:
        flags.append("no_recent_permit_history")

    result = _empty_result(address=address_matched)
    result.update({
        "source": "dbi",
        "source_detail": None,
        "open_permits_count": len(open_permits),
        "recent_permits_5y": recent_permits,
        "major_permits_10y": 0,
        "oldest_open_permit_age_days": oldest_open_permit_age_days,
        "permit_counts_by_type": permit_counts_by_type,
        "complaints_open_count": complaints_open_count,
        "complaints_recent_3y": complaints_recent_3y,
        "flags": flags,
        "permits": permits,
        "complaints": complaints,
    })
    return result
