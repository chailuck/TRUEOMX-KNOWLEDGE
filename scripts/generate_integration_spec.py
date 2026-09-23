"""
TIBCO OMX - Detailed Integration Specification Generator
Chain: ProcessConfig Activity -> FM Service -> ESB Service -> REST/EJB/SOAP Backend

Mapping source (authoritative):
  OMX-OM/Rules/OMConsumers/OMXFM/Request/*.rule  -> ActivityID -> Event name
  OMX-OM/Channels/OMXFMConnectionRequest.channel -> Event name -> FM JMS queue suffix
"""

import os
import re
import sys
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── Paths ────────────────────────────────────────────────────────────────────
def _resolve_base():
    """Return BASE path from --source-folder CLI arg or scripts/config.json."""
    import argparse as _ap
    _dir  = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.dirname(_dir)
    _p = _ap.ArgumentParser(add_help=False)
    _p.add_argument("--source-folder", default=None)
    _args, _ = _p.parse_known_args()
    if _args.source_folder:
        print(f"Using source folder from CLI: {_args.source_folder}")
        return os.path.join(_root, _args.source_folder)
    cfg = os.path.join(_dir, "config.json")
    if os.path.isfile(cfg):
        with open(cfg, encoding="utf-8") as f:
            folder = json.load(f).get("source_folder", "")
        if folder:
            print(f"Using source folder from config.json: {folder}")
            return os.path.join(_root, folder)
    raise FileNotFoundError(
        "source_folder not set. Edit scripts/config.json or pass --source-folder 'FOLDER NAME'")

_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

BASE     = _resolve_base()
PC_DIR   = os.path.join(BASE, "SupportingFiles", "Configs", "ProcessConfig")
FM_DIR   = os.path.join(BASE, "OMX-FM",  "Services")
ESB_DIR  = os.path.join(BASE, "OMX-ESB", "Services")
OM_DIR   = os.path.join(BASE, "OMX-OM")
MAPPING_JSON = os.path.join(_SCRIPT_DIR, "activity_fm_mapping.json")
OUTPUT       = os.path.join(_PROJECT_ROOT, "output", "summary", "TRUEOMX_Integration_Spec.xlsx")

PC_NS = "http://services.omx.truecorp.co.th/ProcessConfig"

# ── Style helpers ─────────────────────────────────────────────────────────────
def fill(h): return PatternFill("solid", fgColor=h)
def bw(s=10): return Font(bold=True, color="FFFFFF", name="Calibri", size=s)
def bd(s=10): return Font(bold=True, color="1F3864", name="Calibri", size=s)
def nm(s=9):  return Font(name="Calibri", size=s)
def ctr():    return Alignment(horizontal="center", vertical="center", wrap_text=True)
def lft():    return Alignment(horizontal="left",   vertical="center", wrap_text=True)
def bdr():
    s = Side(style="thin", color="BBBBBB")
    return Border(left=s, right=s, top=s, bottom=s)

C = {
    "h1": "1F3864", "h2": "2E75B6", "h3": "BDD7EE",
    "fm": "375623", "esb": "7030A0", "rest": "00B0F0",
    "ejb": "ED7D31", "soap": "FFC000", "jms": "70AD47",
    "cond": "FCE4D6", "param": "E2EFDA", "alt": "F2F2F2",
    "white": "FFFFFF", "red": "FF0000", "green": "70AD47",
}

BACKEND_COLOR = {
    "REST":            "00B0F0",
    "SOAP":            "FFC000",
    "EJB (CCBS-Client)": "ED7D31",
    "JMS-Adapter/EJB": "C55A11",
    "JMS (Internal)":  "70AD47",
    "Unknown":         "AAAAAA",
}

def wh(ws, row, headers, fill_hex, fnt=None, ht=26):
    ws.row_dimensions[row].height = ht
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=col, value=h)
        c.fill = fill(fill_hex)
        c.font = fnt or bw()
        c.alignment = ctr()
        c.border = bdr()

def wr(ws, row, vals, alt=False):
    bg = fill(C["alt"]) if alt else fill(C["white"])
    for col, v in enumerate(vals, 1):
        c = ws.cell(row=row, column=col, value=v)
        c.fill = bg
        c.font = nm()
        c.alignment = lft()
        c.border = bdr()

def cw(ws, col_letter, w):
    ws.column_dimensions[col_letter].width = w


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 – Parse ProcessConfig
# ══════════════════════════════════════════════════════════════════════════════
def parse_process_configs(directory):
    processes = {}
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".xml"):
            continue
        try:
            root = ET.parse(os.path.join(directory, fname)).getroot()
        except ET.ParseError:
            continue
        pname = root.attrib.get("extId") or fname.replace(".xml", "")
        acts  = []
        for a in root.findall(f"{{{PC_NS}}}Activities"):
            acts.append({
                "ext_id":      a.attrib.get("extId", ""),
                "activity_id": (a.findtext(f"{{{PC_NS}}}ActivityID") or "").strip(),
                "prev":        (a.findtext(f"{{{PC_NS}}}PreviousActivity") or "").strip(),
                "next":        (a.findtext(f"{{{PC_NS}}}NextActivity") or "").strip(),
                "pre_check":   (a.findtext(f"{{{PC_NS}}}PreExecCheck") or "").strip(),
                "params":      [p.text.strip() for p in a.findall(f"{{{PC_NS}}}Parameter") if p.text],
            })
        processes[pname] = acts
    return processes


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 – Parse FM services
# ══════════════════════════════════════════════════════════════════════════════
def parse_process_file(fpath):
    """Extract all integration details from a .process file."""
    try:
        content = open(fpath, encoding="utf-8", errors="ignore").read()
    except Exception:
        return {}

    result = {
        "listen_queues":  [],
        "send_queues":    [],
        "esb_calls":      [],    # ESB service names called via sub-process
        "sub_processes":  [],    # any non-utility sub-process
        "rest_calls":     [],
        "soap_calls":     [],
        "jms_rr_queues":  [],    # JMS request/reply to adapters
        "schemas":        [],
        "plugin_types":   set(),
    }

    for m in re.findall(r"com\.tibco\.[a-zA-Z0-9._]+", content):
        result["plugin_types"].add(m)

    # JMS queues
    for m in re.findall(r"<destination>([^<]+)</destination>", content):
        q = m.strip()
        if "Modules/FM" in q or "Modules/OM" in q:
            if ".Req" in q:  result["listen_queues"].append(q)
            else:            result["send_queues"].append(q)
        elif "Modules/ESB" in q or ".esb." in q.lower():
            result["send_queues"].append(q)
        elif "adapter." in q.lower():
            result["jms_rr_queues"].append(q)
        else:
            result["send_queues"].append(q)

    # JMS request/reply (adapter calls)
    for m in re.findall(r"<destination>([^<]*adapter[^<]*)</destination>", content, re.IGNORECASE):
        result["jms_rr_queues"].append(m.strip())

    # Sub-process calls
    for m in re.findall(r"<processName>([^<]+)</processName>", content):
        p = m.strip()
        # Skip utility processes
        skip = ["SendLog", "LogEx", "E2ELog", "SendEx", "GenerateSuc", "Construct",
                "HandleDirty", "LogMessage", "SendAdmin", "SendEmail", "RemoveSpec"]
        if any(s in p for s in skip):
            continue
        result["sub_processes"].append(p)
        # Identify ESB service calls: /Services/<ServiceName>/...
        m2 = re.match(r"/Services/([^/]+)/", p)
        if m2:
            result["esb_calls"].append(m2.group(1))
        # Also CCBS Client calls
        if "Tibco_CCBS_Client" in p or "CCBS_Client" in p:
            result["esb_calls"].append("CCBS-Client: " + p.split("/")[-1].replace(".process",""))

    # REST calls
    if re.search(r"RestActivity|HttpClient", content):
        for m in re.findall(r"<(?:url|EndpointURL|endpoint)>([^<]+)<", content):
            result["rest_calls"].append(m.strip())
        if not result["rest_calls"]:
            result["rest_calls"].append("[REST — endpoint from global vars]")

    # SOAP calls
    if re.search(r"com\.tibco\.plugin\.soap|SOAPSend|\.wsdl", content):
        result["soap_calls"].append("[SOAP/WebService call]")

    # Schema imports
    for m in re.findall(r'schemaLocation="([^"]+)"', content):
        result["schemas"].append(m.split("/")[-1])

    result["plugin_types"] = sorted(result["plugin_types"])
    return result


def parse_fm_services(fm_dir):
    """For each FM service, parse all .process files."""
    fm_services = {}
    for svc_name in sorted(os.listdir(fm_dir)):
        svc_path = os.path.join(fm_dir, svc_name)
        if not os.path.isdir(svc_path):
            continue
        files = [f for f in os.listdir(svc_path) if f.endswith(".process")]
        svc_data = {
            "files":         files,
            "listen_queues": [],
            "esb_calls":     [],
            "sub_processes": [],
            "rest_calls":    [],
            "soap_calls":    [],
            "jms_rr_queues": [],
            "schemas":       [],
            "plugin_types":  set(),
        }
        for fname in files:
            pd = parse_process_file(os.path.join(svc_path, fname))
            svc_data["listen_queues"]  += pd.get("listen_queues",  [])
            svc_data["esb_calls"]      += pd.get("esb_calls",      [])
            svc_data["sub_processes"]  += pd.get("sub_processes",  [])
            svc_data["rest_calls"]     += pd.get("rest_calls",     [])
            svc_data["soap_calls"]     += pd.get("soap_calls",     [])
            svc_data["jms_rr_queues"]  += pd.get("jms_rr_queues", [])
            svc_data["schemas"]        += pd.get("schemas",        [])
            svc_data["plugin_types"]   |= set(pd.get("plugin_types", []))

        # Deduplicate
        for k in ("listen_queues","esb_calls","sub_processes","rest_calls",
                  "soap_calls","jms_rr_queues","schemas"):
            svc_data[k] = list(dict.fromkeys(svc_data[k]))
        svc_data["plugin_types"] = sorted(svc_data["plugin_types"])
        fm_services[svc_name] = svc_data
    return fm_services


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 – Parse ESB services
# ══════════════════════════════════════════════════════════════════════════════
def classify_backend(content):
    """Determine the backend call type from process file content."""
    if re.search(r"com\.tibco\.plugin\.json\.activities\.RestActivity|RestActivity", content):
        return "REST"
    if re.search(r"com\.tibco\.plugin\.soap|SOAPSend|\.wsdl", content):
        return "SOAP"
    if re.search(r"JMSQueueRequestReply", content) and re.search(r"adapter\.", content, re.I):
        return "JMS-Adapter/EJB"
    if re.search(r"Tibco_CCBS_Client", content):
        return "EJB (CCBS-Client)"
    if re.search(r"JMSQueueEventSource|JMSReplyActivity", content):
        return "JMS (Internal)"
    return "Unknown"


def parse_esb_services(esb_dir):
    """For each ESB service, extract backend call details."""
    esb_services = {}
    for svc_name in sorted(os.listdir(esb_dir)):
        svc_path = os.path.join(esb_dir, svc_name)
        if not os.path.isdir(svc_path):
            continue

        combined    = ""
        listen_q    = []
        adapter_q   = []
        rest_urls   = []
        soap_notes  = []
        ccbs_procs  = []
        schemas     = []
        sub_procs   = []

        for fname in sorted(os.listdir(svc_path)):
            if not fname.endswith(".process"):
                continue
            try:
                content = open(os.path.join(svc_path, fname), encoding="utf-8", errors="ignore").read()
            except:
                continue
            combined += content

            for m in re.findall(r"<destination>([^<]+)</destination>", content):
                q = m.strip()
                if "adapter." in q.lower():
                    adapter_q.append(q)
                elif "Modules/ESB" in q or "Modules/FM" in q:
                    listen_q.append(q)

            for m in re.findall(r"<(?:url|EndpointURL|endpoint)>([^<]+)<", content):
                rest_urls.append(m.strip())

            for m in re.findall(r"/Tibco_CCBS_Client/([^<\"]+)", content):
                ccbs_procs.append(m.strip().replace(".process",""))

            for m in re.findall(r'schemaLocation="([^"]+)"', content):
                schemas.append(m.split("/")[-1])

            for m in re.findall(r"<processName>([^<]+)</processName>", content):
                p = m.strip()
                skip = ["SendLog","LogEx","E2ELog","SendEx","GenerateSuc","Construct",
                        "HandleDirty","LogMessage","RemoveSpec"]
                if not any(s in p for s in skip):
                    sub_procs.append(p)

        backend_type = classify_backend(combined)
        backend_detail = ""
        if backend_type == "REST":
            backend_detail = "; ".join(dict.fromkeys(rest_urls))[:200] or "[endpoint from global vars]"
        elif backend_type == "SOAP":
            backend_detail = "SOAP/WSDL call"
        elif backend_type == "EJB (CCBS-Client)":
            backend_detail = "AMDOCS CCBS EJB: " + ", ".join(dict.fromkeys(ccbs_procs))[:150]
        elif backend_type == "JMS-Adapter/EJB":
            backend_detail = "Adapter queue: " + "; ".join(dict.fromkeys(adapter_q))[:150]
        elif backend_type == "JMS (Internal)":
            backend_detail = "Internal JMS bridge"

        esb_services[svc_name] = {
            "backend_type":   backend_type,
            "backend_detail": backend_detail,
            "listen_queue":   list(dict.fromkeys(listen_q))[:2],
            "adapter_queues": list(dict.fromkeys(adapter_q))[:2],
            "rest_urls":      list(dict.fromkeys(rest_urls))[:3],
            "ccbs_procs":     list(dict.fromkeys(ccbs_procs))[:5],
            "schemas":        list(dict.fromkeys(schemas))[:8],
            "sub_procs":      list(dict.fromkeys(sub_procs))[:8],
        }
    return esb_services


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 – Activity ID → FM service matching (authoritative BE-rule mapping)
# ══════════════════════════════════════════════════════════════════════════════
def load_authoritative_mapping(json_path):
    """
    Load the ActivityID -> {event_name, fm_queue, req_queue, resp_queue}
    mapping extracted from BE rules + channel file.
    """
    try:
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def build_fm_queue_index(fm_services):
    """
    Build index: normalised(fm_service_dir_name) -> fm_service_dir_name
    FM service directory names usually match the FM queue suffix exactly
    (e.g., queue 'ActivateSubscriber' -> dir 'ActivateSubscriber').
    """
    idx = {}
    for name in fm_services:
        idx[re.sub(r"[^a-z0-9]", "", name.lower())] = name
    return idx


def resolve_fm_service(activity_id, auth_mapping, fm_queue_idx, fm_services):
    """
    Return (fm_service_name, fm_queue_suffix, event_name, match_source) for an activity.

    Priority:
    1. Authoritative BE rule + channel mapping
    2. Exact match of activity_id to FM service directory name
    3. Not found
    """
    # 1. Authoritative lookup
    if activity_id and activity_id in auth_mapping:
        entry     = auth_mapping[activity_id]
        fm_queue  = entry.get("fm_queue", "")
        evt_name  = entry.get("event_name", "")
        req_queue = entry.get("req_queue", "")
        resp_queue= entry.get("resp_queue", "")
        if fm_queue:
            # Find FM service directory matching the queue suffix
            norm_q  = re.sub(r"[^a-z0-9]", "", fm_queue.lower())
            fm_svc  = fm_queue_idx.get(norm_q, fm_queue)   # dir name or the queue name itself
            return fm_svc, fm_queue, evt_name, req_queue, resp_queue, "BE-rule/channel"
        else:
            # We have the event but couldn't resolve FM queue from channel;
            # store event name as partial info
            return "(event: " + evt_name + ")", "", evt_name, "", "", "BE-rule only"

    # 2. Direct activity_id == FM service dir name (case-insensitive)
    if activity_id:
        norm_aid = re.sub(r"[^a-z0-9]", "", activity_id.lower())
        if norm_aid in fm_queue_idx:
            fm_svc = fm_queue_idx[norm_aid]
            return fm_svc, fm_svc, activity_id, f"...FM/{fm_svc}.Req", f"...OM/{fm_svc}.Res", "direct-name-match"

    return "(not found)", "", "", "", "", "unmatched"


def get_system_prefix(activity_id):
    """Return the system prefix portion of an activity ID."""
    m = re.match(r"^([A-Z]+)_", activity_id or "")
    return m.group(1) if m else "OMX"


def infer_protocol(activity_id, esb_name, esb_data, fm_data):
    """Return (protocol, detail) derived from ESB data or heuristics."""
    if esb_name and esb_name in esb_data:
        e = esb_data[esb_name]
        return e["backend_type"], e["backend_detail"]

    # Heuristic by system prefix
    prefix = get_system_prefix(activity_id)
    heuristics = {
        "CCBS":    ("EJB (CCBS-Client)", "AMDOCS CCBS EJB via Tibco_CCBS_Client adapter"),
        "ASRM":    ("JMS-Adapter/EJB",   "CES/ASRM adapter via JMS request-reply"),
        "INTX":    ("SOAP",              "INTX SIM management SOAP service"),
        "BDH":     ("REST",              "BDH REST API"),
        "CAT":     ("EJB (CCBS-Client)", "CCBS Product Catalog EJB"),
        "APIGW":   ("REST",              "API Gateway REST"),
        "CRM":     ("REST",              "CRM REST API"),
        "VCARE":   ("SOAP",              "VCARE SOAP service"),
        "CDB":     ("SOAP",              "CDB SOAP/HTTP service"),
        "CIA":     ("REST",              "CIA REST service"),
        "ATS":     ("REST",              "ATS campaign REST API"),
        "IOM":     ("JMS (Internal)",    "IOM internal JMS queue"),
        "BLACKLIST":("EJB (CCBS-Client)","AMDOCS Blacklist EJB"),
        "MNP":     ("JMS (Internal)",    "MNP internal orchestration"),
        "MCS":     ("SOAP",              "Mediation SOAP call"),
    }
    if prefix in heuristics:
        return heuristics[prefix]
    return ("JMS (Internal)", "Internal OMX orchestration")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 – Build full integration chain rows
# ══════════════════════════════════════════════════════════════════════════════
def build_integration_chain(processes, fm_services, esb_services, auth_mapping):
    """
    Return list of dicts, one per (process, activity) with full chain info.
    Uses authoritative BE-rule / channel mapping for ActivityID -> FM service.
    """
    fm_queue_idx = build_fm_queue_index(fm_services)

    rows = []
    for pname, acts in sorted(processes.items()):
        for step, act in enumerate(acts, 1):
            aid = act["activity_id"]
            sys_prefix = get_system_prefix(aid)

            # ── Authoritative FM resolution ──────────────────────────────────
            fm_name, fm_queue_sfx, event_name, req_queue, resp_queue, match_src = \
                resolve_fm_service(aid, auth_mapping, fm_queue_idx, fm_services)

            fm_data = fm_services.get(fm_name, {})

            # FM JMS listen queue (from authoritative mapping first, then from parsed FM)
            fm_jms_queue = req_queue or ""
            if not fm_jms_queue and fm_data.get("listen_queues"):
                q = fm_data["listen_queues"][0]
                m = re.search(r"Destinations/FM/([^.%]+)", q)
                fm_jms_queue = f"...FM/{m.group(1)}.Req" if m else q

            # FM response queue
            fm_resp_queue = resp_queue or ""

            # ── ESB calls from FM service ─────────────────────────────────────
            esb_calls = fm_data.get("esb_calls", [])
            esb_primary = esb_calls[0] if esb_calls else ""

            if esb_primary.startswith("CCBS-Client:"):
                esb_display = esb_primary
                protocol, backend_detail = "EJB (CCBS-Client)", esb_primary
            else:
                esb_display = esb_primary
                protocol, backend_detail = infer_protocol(aid, esb_primary, esb_services, fm_data)

            # ESB JMS listen queue
            esb_q = ""
            if esb_primary and esb_primary in esb_services:
                lq = esb_services[esb_primary].get("listen_queue", [])
                if lq:
                    m = re.search(r"Destinations/ESB/([^%]+)", lq[0])
                    esb_q = m.group(1) if m else lq[0]

            # Backend endpoint detail
            backend_endpoint = backend_detail
            if esb_primary and esb_primary in esb_services:
                ed = esb_services[esb_primary]
                if ed["backend_type"] == "EJB (CCBS-Client)" and ed["ccbs_procs"]:
                    backend_endpoint = "CCBS EJB: " + "; ".join(ed["ccbs_procs"][:3])
                elif ed["backend_type"] == "JMS-Adapter/EJB" and ed["adapter_queues"]:
                    backend_endpoint = "; ".join(ed["adapter_queues"][:2])
                elif ed["backend_type"] == "REST" and ed["rest_urls"]:
                    backend_endpoint = "; ".join(ed["rest_urls"][:2])
                elif ed["backend_type"] == "SOAP":
                    backend_endpoint = "SOAP/WSDL endpoint"

            schemas_fm  = "; ".join(fm_data.get("schemas",  [])[:4])
            schemas_esb = ""
            if esb_primary and esb_primary in esb_services:
                schemas_esb = "; ".join(esb_services[esb_primary].get("schemas", [])[:4])

            all_esb = "; ".join(esb_calls[:5]) if esb_calls else ""

            rows.append({
                "process":           pname,
                "step":              step,
                "ext_id":            act["ext_id"],
                "activity_id":       aid,
                "sys_prefix":        sys_prefix,
                "conditional":       "Yes" if act["pre_check"] else "No",
                "pre_check":         act["pre_check"][:250] if act["pre_check"] else "",
                "params":            "; ".join(act["params"])[:250],
                "event_name":        event_name,
                "match_source":      match_src,
                "fm_service":        fm_name,
                "fm_queue_suffix":   fm_queue_sfx,
                "fm_jms_req_queue":  fm_jms_queue,
                "fm_jms_resp_queue": fm_resp_queue,
                "fm_files":          "; ".join(fm_data.get("files", []))[:150],
                "esb_primary":       esb_display,
                "esb_all_calls":     all_esb,
                "esb_jms_queue":     esb_q,
                "protocol":          protocol,
                "backend_endpoint":  backend_endpoint[:300],
                "fm_schemas":        schemas_fm,
                "esb_schemas":       schemas_esb,
                "prev_act":          act["prev"],
                "next_act":          act["next"],
            })
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# SHEET BUILDERS
# ══════════════════════════════════════════════════════════════════════════════
def build_title_sheet(wb):
    ws = wb.create_sheet("Cover")
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:I1")
    t = ws["A1"]
    t.value = "TIBCO OMX — Integration Specification & Mapping Report"
    t.fill = fill(C["h1"])
    t.font = Font(bold=True, color="FFFFFF", name="Calibri", size=20)
    t.alignment = ctr()
    ws.row_dimensions[1].height = 50

    ws.merge_cells("A2:I2")
    t2 = ws["A2"]
    t2.value = f"Generated: {date.today().isoformat()}"
    t2.fill = fill(C["h2"])
    t2.font = bw(12)
    t2.alignment = ctr()
    ws.row_dimensions[2].height = 24

    sections = [
        ("", ""),
        ("SCOPE", ""),
        ("Source Components Analysed", "OMX-FM (Flow Manager), OMX-ESB (Enterprise Service Bus), ProcessConfig (Order Configuration)"),
        ("Total ProcessConfig Files", "168 XML files"),
        ("Total FM Services",         "533 services in OMX-FM"),
        ("Total ESB Services",         "518 services in OMX-ESB"),
        ("", ""),
        ("INTEGRATION CHAIN", ""),
        ("Step 1", "ProcessConfig XML defines the ordered list of ActivityIDs for each order type"),
        ("Step 2", "OMX-OM dispatches each ActivityID to the Flow Manager (FM) via JMS queue"),
        ("Step 3", "FM (TIBCO BusinessWorks) orchestrates calls to one or more ESB services"),
        ("Step 4", "ESB calls the backend system via REST, EJB (CCBS-Client), SOAP, or JMS-Adapter"),
        ("Step 5", "Response flows back: Backend -> ESB -> FM -> OM -> ProcessConfig next step"),
        ("", ""),
        ("BACKEND CALL TYPES", ""),
        ("REST",             "com.tibco.plugin.json.activities.RestActivity - used for BDH, APIGW, CRM, CIA, ATS"),
        ("EJB (CCBS-Client)","Tibco_CCBS_Client sub-process adapter - used for AMDOCS CCBS / ASRM EJB calls"),
        ("SOAP",             "com.tibco.plugin.soap / WSDL - used for AA Notify, CDB, VCARE, Collection services"),
        ("JMS-Adapter/EJB",  "JMSQueueRequestReply to adapter.* queue - used for ASRM CES adapter"),
        ("JMS (Internal)",   "Internal JMS bridge between OMX components"),
        ("", ""),
        ("SHEETS IN THIS WORKBOOK", ""),
        ("Sheet: Integration Chain (All)",     "Every process step with full FM->ESB->backend mapping"),
        ("Sheet: Integration Chain (Summary)", "One row per unique ActivityID with FM+ESB+protocol"),
        ("Sheet: FM Service Catalog",          "All FM services with their ESB dependencies and schemas"),
        ("Sheet: ESB Service Catalog",         "All ESB services with backend type, endpoint, and schema"),
        ("Sheet: Protocol Distribution",       "Count of REST / EJB / SOAP / JMS calls per process"),
        ("Sheet: Data Flow Map",               "JMS queue topology: OM -> FM -> ESB -> Backend"),
        ("Sheet: Schema Reference",            "XSD schemas referenced per ESB service"),
    ]

    for i, (key, val) in enumerate(sections):
        row = 4 + i
        ws.row_dimensions[row].height = 20
        if key == "" and val == "":
            continue
        if val == "":
            ws.cell(row=row, column=1, value=key).font = bd(11)
            ws.cell(row=row, column=1).fill = fill(C["h3"])
            ws.merge_cells(f"A{row}:I{row}")
            ws.cell(row=row, column=1).border = bdr()
        else:
            c1 = ws.cell(row=row, column=1, value=key)
            c1.fill = fill("EBF3FB")
            c1.font = bd(10)
            c1.border = bdr()
            c2 = ws.cell(row=row, column=2, value=val)
            c2.font = nm(10)
            c2.border = bdr()
            ws.merge_cells(f"B{row}:I{row}")

    for col in ["A","B","C","D","E","F","G","H","I"]:
        ws.column_dimensions[col].width = 22 if col == "A" else 18
    ws.column_dimensions["A"].width = 35
    ws.column_dimensions["B"].width = 100


def build_integration_chain_detail(wb, chain_rows):
    ws = wb.create_sheet("Integration Chain (All)")
    ws.sheet_view.showGridLines = False

    headers = [
        "Process Name",              # A
        "Step #",                    # B
        "Activity Ext-ID",           # C
        "Activity ID",               # D
        "System Prefix",             # E
        "Conditional?",              # F
        "PreExecCheck",              # G
        "Parameters",                # H
        "BE Event Name",             # I  ← new: authoritative BE rule event
        "Mapping Source",            # J  ← new: BE-rule/channel vs fallback
        "FM Service (Dir)",          # K
        "FM Queue Suffix",           # L
        "FM JMS Request Queue",      # M
        "FM JMS Response Queue",     # N
        "FM Process Files",          # O
        "ESB Service (Primary)",     # P
        "ESB All Calls",             # Q
        "ESB JMS Queue",             # R
        "Backend Protocol",          # S
        "Backend Endpoint / Sub-Process", # T
        "FM XSD Schemas",            # U
        "ESB XSD Schemas",           # V
        "Previous Activity",         # W
        "Next Activity",             # X
    ]
    wh(ws, 1, headers, C["h1"], ht=30)

    for i, row_data in enumerate(chain_rows):
        row = 2 + i
        vals = [
            row_data["process"],
            row_data["step"],
            row_data["ext_id"],
            row_data["activity_id"],
            row_data["sys_prefix"],
            row_data["conditional"],
            row_data["pre_check"],
            row_data["params"],
            row_data["event_name"],
            row_data["match_source"],
            row_data["fm_service"],
            row_data["fm_queue_suffix"],
            row_data["fm_jms_req_queue"],
            row_data["fm_jms_resp_queue"],
            row_data["fm_files"],
            row_data["esb_primary"],
            row_data["esb_all_calls"],
            row_data["esb_jms_queue"],
            row_data["protocol"],
            row_data["backend_endpoint"],
            row_data["fm_schemas"],
            row_data["esb_schemas"],
            row_data["prev_act"],
            row_data["next_act"],
        ]
        wr(ws, row, vals, alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 20

        if row_data["conditional"] == "Yes":
            ws.cell(row=row, column=6).fill = fill(C["cond"])
            ws.cell(row=row, column=7).fill = fill(C["cond"])

        # Color mapping source column
        src = row_data["match_source"]
        src_cell = ws.cell(row=row, column=10)
        if src == "BE-rule/channel":
            src_cell.fill = fill(C["green"])
            src_cell.font = Font(bold=True, color="FFFFFF", name="Calibri", size=9)
        elif src == "BE-rule only":
            src_cell.fill = fill(C["yellow"] if "yellow" in C else "FFC000")
            src_cell.font = Font(bold=True, name="Calibri", size=9)
        elif src == "unmatched":
            src_cell.fill = fill(C["red"])
            src_cell.font = Font(bold=True, color="FFFFFF", name="Calibri", size=9)

        # Color protocol cell
        proto = row_data["protocol"]
        pc = ws.cell(row=row, column=19)
        color = BACKEND_COLOR.get(proto, "AAAAAA")
        pc.fill = fill(color)
        pc.font = Font(bold=True, color="FFFFFF" if proto not in ("SOAP","JMS (Internal)") else "1F3864",
                       name="Calibri", size=9)
        pc.alignment = ctr()

        if row_data["fm_service"] and "(not found)" not in row_data["fm_service"]:
            ws.cell(row=row, column=11).font = Font(bold=True, color=C["fm"], name="Calibri", size=9)
        if row_data["esb_primary"]:
            ws.cell(row=row, column=16).font = Font(bold=True, color=C["esb"], name="Calibri", size=9)

    widths = [36,6,48,42,12,10,60,60,40,20,36,30,50,50,50,36,80,36,20,80,70,70,46,46]
    for col, w in enumerate(widths, 1):
        cw(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.freeze_panes = "D2"


def build_integration_chain_summary(wb, chain_rows, esb_services):
    """One row per unique ActivityID with full authoritative mapping."""
    ws = wb.create_sheet("Integration Chain (Summary)")
    ws.sheet_view.showGridLines = False

    seen = {}
    for r in chain_rows:
        aid = r["activity_id"]
        if aid not in seen:
            seen[aid] = dict(r)
            seen[aid]["proc_count"] = 0
            seen[aid]["proc_list"]  = []
        seen[aid]["proc_count"] += 1
        if r["process"] not in seen[aid]["proc_list"]:
            seen[aid]["proc_list"].append(r["process"])

    headers = [
        "Activity ID",
        "System Prefix",
        "BE Event Name",
        "Mapping Source",
        "FM Service (Dir)",
        "FM Queue Suffix",
        "FM JMS Request Queue",
        "FM JMS Response Queue",
        "ESB Service (Primary)",
        "All ESB Calls",
        "ESB JMS Queue",
        "Backend Protocol",
        "Backend Endpoint / Call Detail",
        "FM XSD Schemas",
        "ESB XSD Schemas",
        "# Processes Using",
        "Sample Processes",
    ]
    wh(ws, 1, headers, C["h1"], ht=30)

    for i, (aid, r) in enumerate(sorted(seen.items())):
        row = 2 + i
        procs_sample = ", ".join(r["proc_list"][:6])
        if len(r["proc_list"]) > 6:
            procs_sample += f" (+{len(r['proc_list'])-6} more)"

        vals = [
            aid,
            r["sys_prefix"],
            r["event_name"],
            r["match_source"],
            r["fm_service"],
            r["fm_queue_suffix"],
            r["fm_jms_req_queue"],
            r["fm_jms_resp_queue"],
            r["esb_primary"],
            r["esb_all_calls"],
            r["esb_jms_queue"],
            r["protocol"],
            r["backend_endpoint"],
            r["fm_schemas"],
            r["esb_schemas"],
            r["proc_count"],
            procs_sample,
        ]
        wr(ws, row, vals, alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 20

        # Color mapping source
        src = r["match_source"]
        sc = ws.cell(row=row, column=4)
        if src == "BE-rule/channel":
            sc.fill = fill("70AD47"); sc.font = Font(bold=True, color="FFFFFF", name="Calibri", size=9)
        elif src == "BE-rule only":
            sc.fill = fill("FFC000"); sc.font = Font(bold=True, name="Calibri", size=9)
        elif src == "unmatched":
            sc.fill = fill("FF0000"); sc.font = Font(bold=True, color="FFFFFF", name="Calibri", size=9)

        proto = r["protocol"]
        pc = ws.cell(row=row, column=12)
        color = BACKEND_COLOR.get(proto, "AAAAAA")
        pc.fill = fill(color)
        pc.font = Font(bold=True, color="FFFFFF" if proto not in ("SOAP","JMS (Internal)") else "1F3864",
                       name="Calibri", size=9)
        pc.alignment = ctr()

    widths = [44,14,40,20,36,30,55,55,36,80,36,22,80,70,70,14,90]
    for col, w in enumerate(widths, 1):
        cw(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.freeze_panes = "C2"


def build_fm_catalog(wb, fm_services, esb_services):
    ws = wb.create_sheet("FM Service Catalog")
    ws.sheet_view.showGridLines = False

    headers = [
        "FM Service Name",
        "Process Files",
        "FM JMS Listen Queue",
        "ESB Services Called",
        "Sub-Processes (non-utility)",
        "Has REST Calls?",
        "Has SOAP Calls?",
        "JMS Adapter Calls",
        "XSD Schemas Referenced",
        "Plugin Types",
    ]
    wh(ws, 1, headers, C["fm"], ht=28)

    for i, (svc_name, data) in enumerate(sorted(fm_services.items())):
        row = 2 + i
        vals = [
            svc_name,
            "; ".join(data.get("files", [])),
            "; ".join(data.get("listen_queues", []))[:120],
            "; ".join(data.get("esb_calls", []))[:200],
            "; ".join(data.get("sub_processes", []))[:200],
            "Yes" if data.get("rest_calls") else "No",
            "Yes" if data.get("soap_calls") else "No",
            "; ".join(data.get("jms_rr_queues", []))[:150],
            "; ".join(data.get("schemas", []))[:200],
            "; ".join(t for t in data.get("plugin_types", [])
                      if "tibco" in t and not any(x in t for x in ["core","pe","mapper"]))[:150],
        ]
        wr(ws, row, vals, alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 20
        if vals[5] == "Yes":
            ws.cell(row=row, column=6).fill = fill(C["rest"])
            ws.cell(row=row, column=6).font = Font(bold=True, color="FFFFFF", name="Calibri", size=9)
        if vals[6] == "Yes":
            ws.cell(row=row, column=7).fill = fill(C["soap"])

    widths = [40, 80, 80, 100, 100, 12, 12, 80, 100, 80]
    for col, w in enumerate(widths, 1):
        cw(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.freeze_panes = "B2"


def build_esb_catalog(wb, esb_services):
    ws = wb.create_sheet("ESB Service Catalog")
    ws.sheet_view.showGridLines = False

    headers = [
        "ESB Service Name",
        "Backend Protocol",
        "Backend Call Detail",
        "ESB JMS Listen Queue",
        "Adapter JMS Queue",
        "REST URLs / Endpoints",
        "CCBS EJB Sub-Processes",
        "XSD Schemas Referenced",
        "Other Sub-Processes",
    ]
    wh(ws, 1, headers, C["esb"], ht=28)

    for i, (svc_name, data) in enumerate(sorted(esb_services.items())):
        row = 2 + i
        vals = [
            svc_name,
            data["backend_type"],
            data["backend_detail"][:200],
            "; ".join(data.get("listen_queue", []))[:120],
            "; ".join(data.get("adapter_queues", []))[:120],
            "; ".join(data.get("rest_urls", []))[:200],
            "; ".join(data.get("ccbs_procs", []))[:200],
            "; ".join(data.get("schemas", []))[:200],
            "; ".join(data.get("sub_procs", []))[:200],
        ]
        wr(ws, row, vals, alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 20

        proto = data["backend_type"]
        pc = ws.cell(row=row, column=2)
        color = BACKEND_COLOR.get(proto, "AAAAAA")
        pc.fill = fill(color)
        pc.font = Font(bold=True, color="FFFFFF" if proto not in ("SOAP","JMS (Internal)") else "1F3864",
                       name="Calibri", size=9)
        pc.alignment = ctr()

    widths = [48, 22, 100, 80, 80, 100, 100, 100, 100]
    for col, w in enumerate(widths, 1):
        cw(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.freeze_panes = "C2"


def build_protocol_distribution(wb, chain_rows, processes):
    ws = wb.create_sheet("Protocol Distribution")
    ws.sheet_view.showGridLines = False

    # Per-process protocol counts
    proc_proto = defaultdict(lambda: defaultdict(int))
    for r in chain_rows:
        proc_proto[r["process"]][r["protocol"]] += 1

    protocols = ["REST", "EJB (CCBS-Client)", "SOAP", "JMS-Adapter/EJB", "JMS (Internal)", "Unknown"]

    headers = ["Process Name", "Total Steps"] + protocols + ["Dominant Protocol"]
    wh(ws, 1, headers, C["h1"], ht=28)

    for i, (pname, proto_counts) in enumerate(sorted(proc_proto.items())):
        row = 2 + i
        total = sum(proto_counts.values())
        vals = [pname, total]
        for p in protocols:
            vals.append(proto_counts.get(p, 0))
        dominant = max(proto_counts, key=proto_counts.get) if proto_counts else "Unknown"
        vals.append(dominant)
        wr(ws, row, vals, alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 18

        # Color each protocol cell
        for j, p in enumerate(protocols):
            cell = ws.cell(row=row, column=3+j)
            cnt = proto_counts.get(p, 0)
            if cnt > 0:
                cell.fill = fill(BACKEND_COLOR.get(p, "AAAAAA"))
                cell.font = Font(bold=True, color="FFFFFF" if p not in ("SOAP","JMS (Internal)") else "1F3864",
                                 name="Calibri", size=9)
                cell.alignment = ctr()

        dom_cell = ws.cell(row=row, column=3+len(protocols))
        dom_cell.fill = fill(BACKEND_COLOR.get(dominant, "AAAAAA"))
        dom_cell.font = Font(bold=True, color="FFFFFF" if dominant not in ("SOAP","JMS (Internal)") else "1F3864",
                             name="Calibri", size=9)

    widths = [40, 12] + [20]*len(protocols) + [24]
    for col, w in enumerate(widths, 1):
        cw(ws, get_column_letter(col), w)

    # Totals row
    total_row = 2 + len(proc_proto)
    ws.row_dimensions[total_row].height = 22
    ws.cell(total_row, 1, "TOTAL").fill = fill(C["h2"])
    ws.cell(total_row, 1).font = bw()
    ws.cell(total_row, 2, sum(r["step"] for r in chain_rows)).fill = fill(C["h2"])
    ws.cell(total_row, 2).font = bw()
    for j, p in enumerate(protocols):
        cnt = sum(1 for r in chain_rows if r["protocol"] == p)
        c = ws.cell(total_row, 3+j, cnt)
        c.fill = fill(C["h2"])
        c.font = bw()

    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.freeze_panes = "B2"


def build_data_flow_map(wb, fm_services, esb_services):
    """Tabular view of the JMS queue topology."""
    ws = wb.create_sheet("Data Flow Map")
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:F1")
    ws["A1"].value = "JMS Queue Topology: OM -> FM -> ESB -> Backend"
    ws["A1"].fill = fill(C["h1"])
    ws["A1"].font = bw(14)
    ws["A1"].alignment = ctr()
    ws.row_dimensions[1].height = 36

    headers = [
        "FM Service", "FM JMS Queue (OM sends here)", "ESB Service Called",
        "ESB JMS Queue (FM sends here)", "Backend Protocol", "Backend System / Endpoint"
    ]
    wh(ws, 2, headers, C["h2"], ht=26)

    row = 3
    for svc_name in sorted(fm_services.keys()):
        fm  = fm_services[svc_name]
        esb_calls = fm.get("esb_calls", []) or ["(none)"]

        fm_q = ""
        if fm.get("listen_queues"):
            m = re.search(r"Destinations/FM/([^%]+)", fm["listen_queues"][0])
            fm_q = m.group(1).rstrip("%") if m else fm["listen_queues"][0]

        for j, esb_name in enumerate(esb_calls):
            esb_data = esb_services.get(esb_name, {})
            esb_q = ""
            if esb_data.get("listen_queue"):
                m2 = re.search(r"Destinations/ESB/([^%]+)", esb_data["listen_queue"][0])
                esb_q = m2.group(1).rstrip("%") if m2 else esb_data["listen_queue"][0]

            proto  = esb_data.get("backend_type", "(N/A)")
            detail = esb_data.get("backend_detail", "")[:120]

            vals = [
                svc_name if j == 0 else "",
                fm_q     if j == 0 else "",
                esb_name,
                esb_q,
                proto,
                detail,
            ]
            wr(ws, row, vals, alt=(row % 2 == 1))
            ws.row_dimensions[row].height = 18

            proto_cell = ws.cell(row=row, column=5)
            proto_cell.fill = fill(BACKEND_COLOR.get(proto, "AAAAAA"))
            proto_cell.font = Font(bold=True, color="FFFFFF" if proto not in ("SOAP","JMS (Internal)") else "1F3864",
                                   name="Calibri", size=9)
            proto_cell.alignment = ctr()
            row += 1

    widths = [40, 50, 40, 50, 22, 100]
    for col, w in enumerate(widths, 1):
        cw(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A2:{get_column_letter(len(headers))}2"
    ws.freeze_panes = "C3"


def build_schema_reference(wb, esb_services, fm_services):
    ws = wb.create_sheet("Schema Reference")
    ws.sheet_view.showGridLines = False

    headers = [
        "Service Layer", "Service Name", "XSD Schema File", "Schema Purpose (inferred)",
        "Backend Protocol"
    ]
    wh(ws, 1, headers, C["h1"], ht=26)

    SCHEMA_KEYWORDS = {
        "Request": "Request message schema",
        "Response": "Response message schema",
        "Header": "Data header/summary schema",
        "Info": "Detail info schema",
        "Error": "Error/fault schema",
        "Subscriber": "Subscriber entity schema",
        "Customer": "Customer entity schema",
        "Account": "Account entity schema",
        "Offer": "Product/Offer schema",
        "Resource": "Resource management schema",
        "Billing": "Billing entity schema",
        "PayChannel": "Payment channel schema",
        "Agreement": "Agreement/contract schema",
        "ActivateSubscriber": "Activation request/response",
        "CreateSubscriber": "New subscriber creation",
        "GetSubscriber": "Subscriber query",
    }

    row = 2
    # ESB schemas
    for svc_name in sorted(esb_services.keys()):
        data = esb_services[svc_name]
        proto = data.get("backend_type", "")
        for schema in data.get("schemas", []):
            purpose = "Data schema"
            for kw, desc in SCHEMA_KEYWORDS.items():
                if kw.lower() in schema.lower():
                    purpose = desc
                    break
            vals = ["ESB", svc_name, schema, purpose, proto]
            wr(ws, row, vals, alt=(row % 2 == 1))
            ws.row_dimensions[row].height = 16

            pc = ws.cell(row=row, column=5)
            color = BACKEND_COLOR.get(proto, "AAAAAA")
            pc.fill = fill(color)
            pc.font = Font(bold=True, color="FFFFFF" if proto not in ("SOAP","JMS (Internal)") else "1F3864",
                           name="Calibri", size=9)
            row += 1

    # FM schemas
    for svc_name in sorted(fm_services.keys()):
        for schema in fm_services[svc_name].get("schemas", []):
            purpose = "FM orchestration schema"
            for kw, desc in SCHEMA_KEYWORDS.items():
                if kw.lower() in schema.lower():
                    purpose = desc
                    break
            vals = ["FM", svc_name, schema, purpose, "JMS (FM layer)"]
            wr(ws, row, vals, alt=(row % 2 == 1))
            ws.row_dimensions[row].height = 16
            row += 1

    widths = [12, 44, 60, 40, 22]
    for col, w in enumerate(widths, 1):
        cw(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.freeze_panes = "C2"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    print("Step 1: Parsing ProcessConfig files ...")
    processes = parse_process_configs(PC_DIR)
    print(f"  -> {len(processes)} processes, "
          f"{sum(len(v) for v in processes.values())} total activities")

    print("Step 2: Parsing FM services ...")
    fm_services = parse_fm_services(FM_DIR)
    print(f"  -> {len(fm_services)} FM services parsed")

    print("Step 3: Parsing ESB services ...")
    esb_services = parse_esb_services(ESB_DIR)
    backend_counts = defaultdict(int)
    for e in esb_services.values():
        backend_counts[e["backend_type"]] += 1
    print(f"  -> {len(esb_services)} ESB services parsed")
    for bt, cnt in sorted(backend_counts.items(), key=lambda x: -x[1]):
        print(f"     {bt}: {cnt}")

    print("Step 4: Loading authoritative ActivityID->FM mapping ...")
    auth_mapping = load_authoritative_mapping(MAPPING_JSON)
    matched_auth = sum(1 for v in auth_mapping.values() if v.get("fm_queue"))
    print(f"  -> {len(auth_mapping)} activity rules loaded, {matched_auth} with FM queue resolved")

    print("Step 5: Building integration chain ...")
    chain_rows = build_integration_chain(processes, fm_services, esb_services, auth_mapping)
    print(f"  -> {len(chain_rows)} chain rows")

    print("Step 6: Creating Excel workbook ...")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    print("  Sheet: Cover")
    build_title_sheet(wb)

    print("  Sheet: Integration Chain (All)")
    build_integration_chain_detail(wb, chain_rows)

    print("  Sheet: Integration Chain (Summary)")
    build_integration_chain_summary(wb, chain_rows, esb_services)

    print("  Sheet: FM Service Catalog")
    build_fm_catalog(wb, fm_services, esb_services)

    print("  Sheet: ESB Service Catalog")
    build_esb_catalog(wb, esb_services)

    print("  Sheet: Protocol Distribution")
    build_protocol_distribution(wb, chain_rows, processes)

    print("  Sheet: Data Flow Map")
    build_data_flow_map(wb, fm_services, esb_services)

    print("  Sheet: Schema Reference")
    build_schema_reference(wb, esb_services, fm_services)

    print(f"Saving to {OUTPUT} ...")
    wb.save(OUTPUT)
    print("Done!")


if __name__ == "__main__":
    main()
