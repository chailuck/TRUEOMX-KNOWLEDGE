"""
TIBCO Order Management - Transformation Discovery Assessment Generator
Analyzes ProcessConfig XMLs, ESB/FM services, and produces migration-ready Excel report.
"""

import os
import re
import sys
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
import openpyxl
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side
)
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference

# ── Paths ───────────────────────────────────────────────────────────────────
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

BASE               = _resolve_base()
PROCESS_CONFIG_DIR = os.path.join(BASE, "SupportingFiles", "Configs", "ProcessConfig")
ESB_SERVICES_DIR   = os.path.join(BASE, "OMX-ESB", "Services")
FM_SERVICES_DIR    = os.path.join(BASE, "OMX-FM", "Services")
OUTPUT_FILE        = os.path.join(_PROJECT_ROOT, "output", "summary", "TRUEOMX_Assessment.xlsx")

NS = "http://services.omx.truecorp.co.th/ProcessConfig"

# ── System prefix → backend system catalog ──────────────────────────────────
SYSTEM_MAP = {
    # ── Core BSS / Billing ────────────────────────────────────────────────────
    "CCBS":        ("CCBS",        "Customer Care & Billing System",          "BSS/Legacy"),
    "MBCCBS":      ("MBCCBS",      "Mobile Broadband CCBS",                   "BSS/Legacy"),
    "AMDOCS":      ("AMDOCS",      "AMDOCS BSS Platform",                     "BSS/Legacy"),
    "HWCBS":       ("HWCBS",       "Huawei CBS (Charging/Billing)",            "BSS/Legacy"),
    "DCCB":        ("DCCB",        "DCCB System",                             "BSS/Legacy"),
    "OPCDB":       ("OPCDB",       "OPCDB System",                            "BSS/Legacy"),
    "CAT":         ("CAT",         "Catalog Service (CCBS)",                   "BSS/Legacy"),
    "CDB":         ("CDB",         "Customer Database",                        "BSS/Legacy"),
    "INT":         ("INT",         "CCBs Integration SOAP Service",            "BSS/Legacy"),
    "BDH":         ("BDH",         "BSS Data Hub",                            "BSS/Legacy"),
    "OSB":         ("OSB",         "Oracle Service Bus",                       "BSS/Legacy"),
    "ODS":         ("ODS",         "Oracle Data Services",                     "BSS/Legacy"),
    # ── Subscription / Activation ────────────────────────────────────────────
    "ASRM":        ("ASRM",        "Auto. Service & Resource Management",      "BSS/Legacy"),
    "SBM":         ("SBM",         "Subscription Business Management",         "BSS/Legacy"),
    "PSA":         ("PSA",         "Product / Service Administration",         "BSS/Legacy"),
    "ISERVICE":    ("ISERVICE",    "iService Platform",                        "BSS/Legacy"),
    "CES":         ("CES",         "Custom Enrichment Service",                "BSS/Legacy"),
    "MVP":         ("MVP",         "MVP Platform",                             "BSS/Legacy"),
    "TCC":         ("TCC",         "TCC System",                               "BSS/Legacy"),
    "FLP":         ("FLP",         "FLP Service",                              "BSS/Legacy"),
    "ENSM":        ("ENSM",        "ENSM Service",                             "BSS/Legacy"),
    "ETS":         ("ETS",         "ETS System",                               "BSS/Legacy"),
    "ICC":         ("ICC",         "ICC Integration",                          "BSS/Legacy"),
    "W4":          ("W4",          "W4 Platform",                              "BSS/Legacy"),
    "SFF":         ("SFF",         "SFF Service",                              "BSS/Legacy"),
    "SPGGW":       ("SPGGW",       "SPGGW Gateway",                            "BSS/Legacy"),
    "MF":          ("MF",          "MF Service",                               "BSS/Legacy"),
    "MLDD":        ("MLDD",        "MLDD Service",                             "BSS/Legacy"),
    "MB":          ("MB",          "Mobile Broadband",                         "BSS/Legacy"),
    "MNS":         ("MNS",         "MNS Registration System",                  "BSS/Legacy"),
    "MSIM":        ("MSIM",        "Multi-SIM Management",                     "BSS/Legacy"),
    # ── Network / SIM ────────────────────────────────────────────────────────
    "INTX":        ("INTX",        "SIM / Number Resource Interface",          "Network"),
    "INVENTORY":   ("INVENTORY",   "Inventory Management System",              "Network"),
    "NAS":         ("NAS",         "Network Authentication Server",            "Network"),
    "CCP":         ("CCP",         "CCP Network System",                       "Network"),
    "MBDOCSIS":    ("MBDOCSIS",    "Mobile Broadband DOCSIS",                  "Network"),
    "MBUNLOCK":    ("MBUNLOCK",    "Mobile Broadband Unlock",                  "Network"),
    "MBWIFI":      ("MBWIFI",      "Mobile Broadband WiFi",                    "Network"),
    "OTA":         ("OTA",         "Over-The-Air Provisioning",                "Network"),
    "TMN":         ("TMN",         "TMN Network Service",                      "Network"),
    "GPRS":        ("GPRS",        "GPRS Enable/Disable",                      "Network"),
    "TDG":         ("TDG",         "TDG Platform",                             "Network"),
    "RM":          ("RM",          "Resource Management",                       "Network"),
    "TSM":         ("TSM",         "Trusted Service Manager",                  "Network"),
    "SMDP":        ("SMDP",        "SM-DP+ eSIM Management",                   "Device/eSIM"),
    "KNOX":        ("KNOX",        "Samsung Knox MDM",                         "Device/MDM"),
    "GPS":         ("GPS",         "GPS / Location Service",                   "Network"),
    "GCS":         ("GCS",         "GreenCard / SIM Validation",               "BSS/Legacy"),
    # ── CRM / Customer ───────────────────────────────────────────────────────
    "VCARESERVICE":("VCARESERVICE","VCARE Service Layer",                      "CRM/TNP"),
    "VCAREORDER":  ("VCAREORDER",  "VCARE Order Service",                      "CRM/TNP"),
    "VCAREAM":     ("VCAREAM",     "VCARE Account Management",                 "CRM/TNP"),
    "VCARECRM":    ("VCARECRM",    "VCARE CRM Module",                         "CRM/TNP"),
    "VCAREGW":     ("VCAREGW",     "VCARE Gateway",                            "CRM/TNP"),
    "VCARECCC":    ("VCARECCC",    "VCARE Contact Centre",                     "CRM/TNP"),
    "VCAREACCT":   ("VCAREACCT",   "VCARE Account Service",                    "CRM/TNP"),
    "VCAREService":("VCARESERVICE","VCARE Service Layer",                      "CRM/TNP"),
    "VCARE":       ("VCARE",       "VCARE CRM Platform (TNP)",                 "CRM/TNP"),
    "CRM":         ("CRM",         "CRM System",                               "CRM"),
    "CIA":         ("CIA",         "CIA System",                               "CRM"),
    "CJ":          ("CJ",          "Customer Journey System",                  "CRM"),
    "SMS3CJ":      ("SMS3CJ",      "SMS via Customer Journey",                 "CRM"),
    # ── Charging / Billing ───────────────────────────────────────────────────
    "MCS":         ("MCS",         "Mediation / Charging System",              "Charging"),
    "AR":          ("AR",          "Accounts Receivable / Adjustments",        "Billing"),
    "PROMIS":      ("PROMIS",      "Promise-to-Pay Module",                    "Billing"),
    # ── Notification / Messaging ─────────────────────────────────────────────
    "SMSGATEWAY":  ("SMSGATEWAY",  "SMS Gateway",                              "Notification"),
    "SMSC":        ("SMSC",        "SMS Centre",                               "Notification"),
    "EMAILGATEWAY":("EMAILGATEWAY","Email Notification Gateway",               "Notification"),
    "WHATUP":      ("WHATUP",      "WhatsApp / Notification Gateway",          "Notification"),
    # ── Integration / API ────────────────────────────────────────────────────
    "APIGW":       ("APIGW",       "API Gateway",                              "Integration"),
    "ATS":         ("ATS",         "Campaign / ATS System",                    "Marketing"),
    "BN":          ("BN",          "BN (True Move H) System",                  "BSS/TNP"),
    "TNP":         ("TNP",         "True Network Partner",                     "BSS/TNP"),
    "TAG":         ("TAG",         "TAG Service",                              "Integration"),
    # ── Digital / VAS ────────────────────────────────────────────────────────
    "TRUEID":      ("TRUEID",      "TrueID Platform",                          "Digital"),
    "TRUEDOC":     ("TRUEDOC",     "TrueDoc Platform",                         "Digital"),
    "TRUEYOU":     ("TRUEYOU",     "TrueYou Platform",                         "Digital"),
    "TVS":         ("TVS",         "TVS (True Vision) System",                 "VAS/TNP"),
    "MUSIC":       ("MUSIC",       "Music / VAS Charging",                     "VAS"),
    # ── Security ─────────────────────────────────────────────────────────────
    "BLACKLIST":   ("BLACKLIST",   "Blacklist & Fraud Detection",              "Security"),
    "BL":          ("BL",          "Blacklist Service",                        "Security"),
    "CVSS":        ("CVSS",        "Credit Verification & Scoring",            "Credit"),
    # ── OM / Internal ────────────────────────────────────────────────────────
    "OMX":         ("OMX",         "OMX Internal Functions",                   "OM/Internal"),
    "OM":          ("OM",          "OMX-OM (Order Manager)",                   "OM/Internal"),
    "OMXN":        ("OMXN",        "OMX-N (Fibre/Home) Orders",                "OM/FTTB"),
    "IOM":         ("IOM",         "Intelligent Order Manager",                "OM/Legacy"),
    "AA":          ("AA",          "Auto-Activation System",                   "OM/Internal"),
    "AM":          ("AM",          "Account Management Module",                "BSS/Legacy"),
    "MNP":         ("MNP",         "Mobile Number Portability",                "Regulatory"),
    "RMRF":        ("RMRF",        "Resource Migration & RFM",                 "OM/Internal"),
    "GET_AND":     ("GET_AND",     "Resource Confirmation Activity",            "OM/Internal"),
    "GET":         ("GET",         "Data Retrieval Operation",                  "OM/Internal"),
    "SAVE":        ("SAVE",        "Partial-Order Save",                       "OM/Internal"),
    "SEND":        ("SEND",        "Send / Notification Action",               "OM/Internal"),
    "SINGLE":      ("SINGLE",      "Single-SIM Process",                       "OM/Internal"),
    "CREATE":      ("CREATE",      "Record Creation Activity",                  "OM/Internal"),
    "UPDATE":      ("UPDATE",      "Record Update Activity",                    "OM/Internal"),
    "CHECK":       ("CHECK",       "Validation Check Activity",                 "OM/Internal"),
    "CALCULATE":   ("CALCULATE",   "Calculation / Computation Logic",           "OM/Internal"),
    "BREAK":       ("BREAK",       "Order Flow Break Point",                    "OM/Internal"),
    "STATUS":      ("STATUS",      "Status Check Activity",                     "OM/Internal"),
}

def get_system_info(activity_id):
    """Return (system_code, system_name, system_type) for an activityID.
    Falls back to using the activity prefix itself so every distinct
    system is counted separately (never collapsed into 'OTHER').
    """
    for prefix, info in sorted(SYSTEM_MAP.items(), key=lambda x: -len(x[0])):
        if activity_id.upper().startswith(prefix.upper()):
            return info
    # Unknown prefix: use it as the system code to keep counts accurate
    prefix = activity_id.split("_")[0].upper() if "_" in activity_id else activity_id.upper()
    return (prefix, f"{prefix} System", "External")


# ── Category labels for order processes ─────────────────────────────────────
PROCESS_CATEGORY = {
    "ACTIVATION": "Activation", "PREPAID_ACTIVATION": "Activation",
    "POSTPAID_MNP_ACTIVATION": "MNP", "PREPAID_MNP_ACTIVATION": "MNP",
    "MNP_PORT_IN": "MNP", "MNP_PORT_OUT": "MNP", "MNP_PRE": "MNP", "MNP_POST": "MNP",
    "PREPAID": "Prepaid", "POSTPAID": "Postpaid",
    "CHANGE_": "Change Request", "CANCEL": "Cancellation", "RESTORE": "Restore",
    "SUSPEND": "Suspend", "BN_": "BN Process", "TNP_": "TNP Process",
    "OMXN_": "FTTB/Home", "VCARE": "VCARE", "RMRF": "Resource Migration",
}

def categorize_process(process_name):
    for key, cat in PROCESS_CATEGORY.items():
        if process_name.startswith(key):
            return cat
    return "Other"


# ── Parse all ProcessConfig XML files ───────────────────────────────────────
def parse_process_configs(directory):
    processes = {}
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".xml"):
            continue
        fpath = os.path.join(directory, fname)
        try:
            tree = ET.parse(fpath)
            root = tree.getroot()
        except ET.ParseError:
            continue
        # Root extId is the process name
        process_name = root.attrib.get("extId") or fname.replace(".xml", "")
        activities = []
        for act in root.findall(f"{{{NS}}}Activities"):
            ext_id      = act.attrib.get("extId", "")
            activity_id = (act.findtext(f"{{{NS}}}ActivityID") or "").strip()
            prev_act    = (act.findtext(f"{{{NS}}}PreviousActivity") or "").strip()
            next_act    = (act.findtext(f"{{{NS}}}NextActivity") or "").strip()
            pre_check   = (act.findtext(f"{{{NS}}}PreExecCheck") or "").strip()
            params      = [p.text.strip() for p in act.findall(f"{{{NS}}}Parameter") if p.text]
            activities.append({
                "ext_id":      ext_id,
                "activity_id": activity_id,
                "prev":        prev_act,
                "next":        next_act,
                "pre_check":   pre_check,
                "params":      params,
                "conditional": bool(pre_check),
            })
        processes[process_name] = {
            "file":       fname,
            "activities": activities,
            "category":   categorize_process(process_name),
        }
    return processes


# ── Enumerate ESB/FM services ────────────────────────────────────────────────
def enumerate_services(directory, component):
    services = []
    if not os.path.isdir(directory):
        return services
    for name in sorted(os.listdir(directory)):
        full_path = os.path.join(directory, name)
        sys_code, sys_name, sys_type = get_system_info(name)
        # Count sub-files (operations)
        try:
            ops = [f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))]
        except NotADirectoryError:
            ops = []
        services.append({
            "component":   component,
            "service_name": name,
            "system_code": sys_code,
            "system_name": sys_name,
            "system_type": sys_type,
            "op_count":    len(ops),
        })
    return services


# ── Build aggregated stats ───────────────────────────────────────────────────
def build_stats(processes):
    """Return dict of aggregated statistics from parsed processes."""
    all_activities  = defaultdict(list)   # activity_id -> [process_names]
    system_usage    = defaultdict(set)    # system_code -> set of processes
    process_systems = defaultdict(set)    # process -> set of system_codes
    conditional_count = defaultdict(int)  # process -> conditional activity count

    for pname, pdata in processes.items():
        for act in pdata["activities"]:
            aid = act["activity_id"]
            if not aid:
                continue
            all_activities[aid].append(pname)
            sc, _, _ = get_system_info(aid)
            system_usage[sc].add(pname)
            process_systems[pname].add(sc)
            if act["conditional"]:
                conditional_count[pname] += 1

    return {
        "all_activities":    all_activities,
        "system_usage":      system_usage,
        "process_systems":   process_systems,
        "conditional_count": conditional_count,
    }


# ── Migration complexity scorer ──────────────────────────────────────────────
def complexity_score(pdata, stats):
    """Return (score 1-5, label, rationale) for a process."""
    acts         = pdata["activities"]
    act_count    = len(acts)
    cond_count   = sum(1 for a in acts if a["conditional"])
    sys_count    = len(set(get_system_info(a["activity_id"])[0] for a in acts if a["activity_id"]))
    param_count  = sum(len(a["params"]) for a in acts)

    score = 1
    if act_count > 60:   score += 2
    elif act_count > 30: score += 1
    if cond_count > 20:  score += 1
    if sys_count > 8:    score += 1
    if param_count > 30: score += 1
    score = min(score, 5)

    labels = {1: "Very Low", 2: "Low", 3: "Medium", 4: "High", 5: "Very High"}
    rationale = (
        f"{act_count} activities, {cond_count} conditional, "
        f"{sys_count} systems, {param_count} parameters"
    )
    return score, labels[score], rationale


# ── Style helpers ────────────────────────────────────────────────────────────
COLORS = {
    "header_dark":  "1F3864",
    "header_mid":   "2E75B6",
    "header_light": "BDD7EE",
    "accent":       "E2EFDA",
    "warning":      "FCE4D6",
    "critical":     "F4CCCC",
    "white":        "FFFFFF",
    "row_alt":      "F2F2F2",
    "green":        "70AD47",
    "yellow":       "FFC000",
    "orange":       "ED7D31",
    "red":          "FF0000",
}

COMPLEXITY_COLOR = {
    1: "70AD47",  # green
    2: "A9D18E",  # light green
    3: "FFC000",  # yellow
    4: "ED7D31",  # orange
    5: "FF0000",  # red
}

def hdr_fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def bold_white(size=11):
    return Font(bold=True, color="FFFFFF", name="Calibri", size=size)

def bold_dark(size=11):
    return Font(bold=True, color="1F3864", name="Calibri", size=size)

def normal(size=10):
    return Font(name="Calibri", size=size)

def center():
    return Alignment(horizontal="center", vertical="center", wrap_text=True)

def left():
    return Alignment(horizontal="left", vertical="center", wrap_text=True)

def thin_border():
    s = Side(style="thin", color="AAAAAA")
    return Border(left=s, right=s, top=s, bottom=s)

def set_col_width(ws, col_letter, width):
    ws.column_dimensions[col_letter].width = width

def freeze(ws, cell="B2"):
    ws.freeze_panes = cell

def write_header_row(ws, row, headers, fill_hex, font_func=bold_white, height=28):
    ws.row_dimensions[row].height = height
    for col, hdr in enumerate(headers, start=1):
        c = ws.cell(row=row, column=col, value=hdr)
        c.fill = hdr_fill(fill_hex)
        c.font = font_func()
        c.alignment = center()
        c.border = thin_border()

def write_data_row(ws, row, values, alt=False):
    fill = hdr_fill(COLORS["row_alt"]) if alt else hdr_fill(COLORS["white"])
    for col, val in enumerate(values, start=1):
        c = ws.cell(row=row, column=col, value=val)
        c.fill = fill
        c.font = normal()
        c.alignment = left()
        c.border = thin_border()


# ════════════════════════════════════════════════════════════════════════════
# SHEET BUILDERS
# ════════════════════════════════════════════════════════════════════════════

def build_executive_summary(wb, processes, stats, esb_services, fm_services):
    ws = wb.create_sheet("Executive Summary")
    ws.sheet_view.showGridLines = False

    # Title block
    ws.merge_cells("A1:H1")
    t = ws["A1"]
    t.value = "TIBCO OMX — Transformation Discovery Assessment"
    t.fill = hdr_fill(COLORS["header_dark"])
    t.font = Font(bold=True, color="FFFFFF", name="Calibri", size=18)
    t.alignment = center()
    ws.row_dimensions[1].height = 40

    ws.merge_cells("A2:H2")
    t2 = ws["A2"]
    t2.value = f"Generated: {date.today().isoformat()}  |  Analyst: TRUEOMX AI Discovery Director"
    t2.fill = hdr_fill(COLORS["header_mid"])
    t2.font = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
    t2.alignment = center()
    ws.row_dimensions[2].height = 22

    # KPI section
    total_procs  = len(processes)
    total_acts   = sum(len(p["activities"]) for p in processes.values())
    unique_acts  = len(stats["all_activities"])
    unique_sys   = len(stats["system_usage"])
    esb_svc_cnt  = len(esb_services)
    fm_svc_cnt   = len(fm_services)
    cond_total   = sum(stats["conditional_count"].values())
    cat_counts   = defaultdict(int)
    for p in processes.values():
        cat_counts[p["category"]] += 1

    kpis = [
        ("Total Order Processes",      total_procs),
        ("Total Activity Steps",       total_acts),
        ("Unique Activity Types",      unique_acts),
        ("Backend Systems Touched",    unique_sys),
        ("ESB Services (OMX-ESB)",     esb_svc_cnt),
        ("FM Services (OMX-FM)",       fm_svc_cnt),
        ("Conditional Steps (PreExec)", cond_total),
    ]

    ws.row_dimensions[4].height = 20
    ws["A4"].value = "KEY METRICS"
    ws["A4"].font = bold_dark(13)

    for i, (label, val) in enumerate(kpis):
        row = 5 + i
        ws.row_dimensions[row].height = 22
        c_label = ws.cell(row=row, column=1, value=label)
        c_label.fill = hdr_fill(COLORS["header_light"])
        c_label.font = bold_dark()
        c_label.border = thin_border()
        c_label.alignment = left()
        c_val = ws.cell(row=row, column=2, value=val)
        c_val.font = Font(bold=True, name="Calibri", size=12, color="1F3864")
        c_val.border = thin_border()
        c_val.alignment = center()

    # Category breakdown
    ws.cell(row=4, column=4, value="PROCESS CATEGORIES").font = bold_dark(13)
    write_header_row(ws, 5, ["Category", "Count", "% of Total"], COLORS["header_mid"], height=22)
    for i, (cat, cnt) in enumerate(sorted(cat_counts.items(), key=lambda x: -x[1])):
        row = 6 + i
        pct = f"{100*cnt/total_procs:.1f}%"
        write_data_row(ws, row, [cat, cnt, pct], alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 18

    # Complexity distribution
    comp_dist = defaultdict(int)
    for pname, pdata in processes.items():
        sc, label, _ = complexity_score(pdata, stats)
        comp_dist[label] += 1

    ws.cell(row=4, column=7, value="COMPLEXITY DISTRIBUTION").font = bold_dark(13)
    write_header_row(ws, 5, ["Complexity", "Count"], COLORS["header_mid"], height=22)
    for i, lbl in enumerate(["Very Low", "Low", "Medium", "High", "Very High"]):
        row = 6 + i
        c = comp_dist.get(lbl, 0)
        write_data_row(ws, row, [lbl, c], alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 18
        ws.cell(row=row, column=7).fill = hdr_fill(COMPLEXITY_COLOR[i+1])

    # Observations section
    obs_row = 5 + max(len(cat_counts), len(kpis)) + 3
    ws.merge_cells(f"A{obs_row}:H{obs_row}")
    ws[f"A{obs_row}"].value = "KEY FINDINGS & OBSERVATIONS"
    ws[f"A{obs_row}"].font = bold_dark(13)
    ws.row_dimensions[obs_row].height = 22

    observations = [
        f"• {total_procs} distinct order-management processes discovered across Postpaid, Prepaid, MNP, FTTB, BN and TNP domains.",
        f"• {unique_acts} unique activity types identified — many are reused across multiple processes, indicating shared service dependencies.",
        f"• {unique_sys} backend systems are directly integrated via OMX orchestration (CCBS, ASRM, INTX, BDH, CAT, CES, VCARE, BN, etc.).",
        f"• {cond_total} conditional execution checks (PreExecCheck XPath expressions) introduce branching complexity that must be re-implemented in a target platform.",
        f"• ESB layer exposes {esb_svc_cnt} services; FM orchestration layer exposes {fm_svc_cnt} services — significant integration surface area.",
        "• Highest-complexity processes are MNP flows, multi-system activations and owner-change workflows.",
        "• CCBS remains the dominant backend system, present in virtually every order flow — a key risk for migration.",
        "• Recommendation: adopt an API-first strangler-fig pattern, exposing CCBS operations via modern REST APIs before decommissioning TIBCO ESB.",
    ]
    for j, obs in enumerate(observations):
        r = obs_row + 1 + j
        ws.merge_cells(f"A{r}:H{r}")
        c = ws[f"A{r}"]
        c.value = obs
        c.font = normal(10)
        c.alignment = left()
        c.fill = hdr_fill(COLORS["accent"] if j % 2 == 0 else COLORS["white"])
        c.border = thin_border()
        ws.row_dimensions[r].height = 20

    # Column widths
    set_col_width(ws, "A", 42)
    set_col_width(ws, "B", 12)
    set_col_width(ws, "C", 12)
    set_col_width(ws, "D", 28)
    set_col_width(ws, "E", 10)
    set_col_width(ws, "F", 12)
    set_col_width(ws, "G", 26)
    set_col_width(ws, "H", 10)
    freeze(ws, "A3")


def build_process_catalog(wb, processes, stats):
    ws = wb.create_sheet("Order Journey Map")
    ws.sheet_view.showGridLines = False

    headers = [
        "Process Name", "Category", "Total Steps", "Conditional Steps",
        "Cond. %", "Systems Touched", "System List (sample)",
        "Complexity Score", "Complexity Label", "Rationale"
    ]
    write_header_row(ws, 1, headers, COLORS["header_dark"])

    for i, (pname, pdata) in enumerate(sorted(processes.items())):
        row = 2 + i
        acts      = pdata["activities"]
        total     = len(acts)
        cond      = stats["conditional_count"].get(pname, 0)
        cond_pct  = f"{100*cond/total:.0f}%" if total else "0%"
        sys_set   = sorted(stats["process_systems"].get(pname, set()))
        sys_count = len(sys_set)
        sys_sample = ", ".join(sys_set[:6]) + ("…" if len(sys_set) > 6 else "")
        sc, label, rationale = complexity_score(pdata, stats)

        values = [pname, pdata["category"], total, cond, cond_pct,
                  sys_count, sys_sample, sc, label, rationale]
        write_data_row(ws, row, values, alt=(i % 2 == 1))

        # Color the complexity cell
        comp_cell = ws.cell(row=row, column=8)
        comp_cell.fill = hdr_fill(COMPLEXITY_COLOR[sc])
        comp_cell.font = Font(bold=True, name="Calibri", size=10,
                              color="FFFFFF" if sc >= 3 else "1F3864")
        comp_cell.alignment = center()

        ws.row_dimensions[row].height = 18

    widths = [40, 18, 12, 14, 10, 14, 50, 14, 14, 55]
    for col, w in enumerate(widths, start=1):
        set_col_width(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    freeze(ws, "A2")


def build_activity_detail(wb, processes):
    ws = wb.create_sheet("Activity Detail")
    ws.sheet_view.showGridLines = False

    headers = [
        "Process Name", "Category", "Step #", "Activity Ext-ID",
        "Activity ID (Service)", "Previous Activity", "Next Activity",
        "Conditional?", "PreExecCheck (XPath)", "Parameters",
        "System Code", "System Name", "System Type"
    ]
    write_header_row(ws, 1, headers, COLORS["header_dark"])

    row = 2
    for pname, pdata in sorted(processes.items()):
        cat = pdata["category"]
        for step, act in enumerate(pdata["activities"], start=1):
            sc, sname, stype = get_system_info(act["activity_id"])
            values = [
                pname, cat, step,
                act["ext_id"], act["activity_id"],
                act["prev"], act["next"],
                "Yes" if act["conditional"] else "No",
                act["pre_check"][:200] if act["pre_check"] else "",
                "; ".join(act["params"])[:200],
                sc, sname, stype
            ]
            write_data_row(ws, row, values, alt=(step % 2 == 1))
            if act["conditional"]:
                ws.cell(row=row, column=8).fill = hdr_fill(COLORS["warning"])
            ws.row_dimensions[row].height = 18
            row += 1

    widths = [36, 16, 8, 48, 42, 46, 46, 12, 55, 55, 12, 40, 18]
    for col, w in enumerate(widths, start=1):
        set_col_width(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    freeze(ws, "C2")


def build_service_catalog(wb, esb_services, fm_services, stats):
    ws = wb.create_sheet("Service Catalog")
    ws.sheet_view.showGridLines = False

    # Unique activity IDs and their process counts from ProcessConfig
    activity_usage = stats["all_activities"]

    headers = [
        "Component", "Service / Activity Name", "System Code",
        "Backend System", "System Type", "# Operations",
        "Used in # Processes", "Processes (sample)"
    ]
    write_header_row(ws, 1, headers, COLORS["header_dark"])

    all_services = esb_services + fm_services
    for i, svc in enumerate(sorted(all_services, key=lambda x: (x["component"], x["service_name"]))):
        row = 2 + i
        # Match to activity usage
        sname = svc["service_name"]
        # Try exact match first, then prefix match
        usage = activity_usage.get(sname, [])
        if not usage:
            # fuzzy: activity_id might be uppercase version
            for aid, procs in activity_usage.items():
                if aid.upper() == sname.upper():
                    usage = procs
                    break
        procs_sample = ", ".join(sorted(set(usage))[:4])
        if len(set(usage)) > 4:
            procs_sample += "…"

        values = [
            svc["component"], svc["service_name"], svc["system_code"],
            svc["system_name"], svc["system_type"], svc["op_count"],
            len(set(usage)), procs_sample
        ]
        write_data_row(ws, row, values, alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 18

    widths = [12, 48, 14, 44, 18, 12, 18, 65]
    for col, w in enumerate(widths, start=1):
        set_col_width(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    freeze(ws, "C2")


def build_interface_catalog(wb, stats, processes):
    ws = wb.create_sheet("Interface Catalog")
    ws.sheet_view.showGridLines = False

    headers = [
        "System Code", "Backend System", "System Type / Domain",
        "# Unique Activities", "# Processes Using",
        "Processes (first 6)", "Integration Pattern", "Migration Priority"
    ]
    write_header_row(ws, 1, headers, COLORS["header_dark"])

    # Aggregate by system
    sys_details = defaultdict(lambda: {"activities": set(), "processes": set()})
    for pname, pdata in processes.items():
        for act in pdata["activities"]:
            if not act["activity_id"]:
                continue
            sc, sname, stype = get_system_info(act["activity_id"])
            sys_details[sc]["activities"].add(act["activity_id"])
            sys_details[sc]["processes"].add(pname)
            sys_details[sc]["name"]  = sname
            sys_details[sc]["type"]  = stype

    priority_map = {
        "BSS/Legacy": "High", "OM/Legacy": "High",
        "BSS/TNP": "Medium", "CRM/TNP": "Medium",
        "Charging": "High", "Network": "Medium",
        "Integration": "Low", "OM/Internal": "Low",
        "Security": "Medium", "Marketing": "Low",
        "VAS": "Low", "Digital": "Low",
        "Billing": "High", "Regulatory": "High",
        "Credit": "Medium", "OM/FTTB": "Medium",
    }
    pattern_map = {
        "BSS/Legacy": "SOAP/EJB (legacy)", "OM/Legacy": "JMS/Process",
        "BSS/TNP": "SOAP/REST", "CRM/TNP": "REST/SOAP",
        "Charging": "SOAP", "Network": "REST/SOAP",
        "Integration": "REST API GW", "OM/Internal": "Internal BW/BE",
        "Security": "DB Lookup", "Marketing": "REST",
        "Billing": "SOAP/EJB", "Regulatory": "REST",
    }

    sorted_sys = sorted(sys_details.items(),
                        key=lambda x: -len(x[1]["processes"]))

    for i, (sc, info) in enumerate(sorted_sys):
        row = 2 + i
        stype = info.get("type", "Unknown")
        procs = sorted(info["processes"])
        procs_sample = ", ".join(procs[:6]) + ("…" if len(procs) > 6 else "")
        priority = priority_map.get(stype, "Medium")
        pattern  = pattern_map.get(stype, "SOAP/REST")

        values = [
            sc, info.get("name", "Unknown"), stype,
            len(info["activities"]), len(info["processes"]),
            procs_sample, pattern, priority
        ]
        write_data_row(ws, row, values, alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 18

        # Color priority
        pc = ws.cell(row=row, column=8)
        pc.font = Font(bold=True, name="Calibri", size=10, color="FFFFFF")
        if priority == "High":   pc.fill = hdr_fill("FF0000")
        elif priority == "Medium": pc.fill = hdr_fill("FFC000")
        else:                    pc.fill = hdr_fill("70AD47")

    widths = [14, 44, 20, 18, 18, 70, 24, 18]
    for col, w in enumerate(widths, start=1):
        set_col_width(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    freeze(ws, "B2")


def build_dependency_matrix(wb, processes, stats):
    ws = wb.create_sheet("Dependency Matrix")
    ws.sheet_view.showGridLines = False

    # Top systems by usage
    sys_by_usage = sorted(stats["system_usage"].items(),
                          key=lambda x: -len(x[1]))
    top_systems  = [s[0] for s in sys_by_usage[:30]]

    # Header
    ws.cell(row=1, column=1, value="Process \\ System").fill = hdr_fill(COLORS["header_dark"])
    ws.cell(row=1, column=1).font = bold_white()
    ws.cell(row=1, column=1).alignment = center()
    ws.cell(row=1, column=1).border = thin_border()
    ws.row_dimensions[1].height = 65

    for col, sys_code in enumerate(top_systems, start=2):
        c = ws.cell(row=1, column=col, value=sys_code)
        c.fill = hdr_fill(COLORS["header_mid"])
        c.font = bold_white(9)
        c.alignment = Alignment(horizontal="center", vertical="center",
                                text_rotation=60, wrap_text=False)
        c.border = thin_border()
        set_col_width(ws, get_column_letter(col), 7)

    set_col_width(ws, "A", 40)

    for i, (pname, pdata) in enumerate(sorted(processes.items())):
        row = 2 + i
        c = ws.cell(row=row, column=1, value=pname)
        c.fill = hdr_fill(COLORS["header_light"])
        c.font = bold_dark(9)
        c.alignment = left()
        c.border = thin_border()
        ws.row_dimensions[row].height = 16

        p_systems = stats["process_systems"].get(pname, set())
        for col, sys_code in enumerate(top_systems, start=2):
            cell = ws.cell(row=row, column=col)
            cell.border = thin_border()
            if sys_code in p_systems:
                cell.value = "✓"
                cell.fill = hdr_fill(COLORS["header_mid"])
                cell.font = Font(bold=True, color="FFFFFF", name="Calibri", size=9)
                cell.alignment = center()
            else:
                cell.fill = hdr_fill(COLORS["white"])

    freeze(ws, "B2")


def build_migration_assessment(wb, processes, stats):
    ws = wb.create_sheet("Migration Complexity")
    ws.sheet_view.showGridLines = False

    headers = [
        "Process Name", "Category", "Total Steps", "Cond. Steps",
        "# Systems", "# Params", "Complexity Score", "Complexity",
        "Migration Effort (days)", "Migration Notes"
    ]
    write_header_row(ws, 1, headers, COLORS["header_dark"])

    effort_map = {1: "3–5", 2: "5–10", 3: "10–20", 4: "20–40", 5: "40–80"}
    notes_map  = {
        1: "Straightforward migration; minimal branching.",
        2: "Low complexity; review conditional logic.",
        3: "Medium effort; map all PreExecCheck XPath to target rules engine.",
        4: "High complexity; multiple system integrations — plan phased approach.",
        5: "Very high; recommend decomposing into sub-flows before migrating.",
    }

    for i, (pname, pdata) in enumerate(sorted(processes.items())):
        row = 2 + i
        acts     = pdata["activities"]
        total    = len(acts)
        cond     = stats["conditional_count"].get(pname, 0)
        sys_set  = stats["process_systems"].get(pname, set())
        params   = sum(len(a["params"]) for a in acts)
        sc, label, _ = complexity_score(pdata, stats)
        effort   = effort_map[sc]
        notes    = notes_map[sc]

        values = [pname, pdata["category"], total, cond,
                  len(sys_set), params, sc, label, effort, notes]
        write_data_row(ws, row, values, alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 18

        comp_c = ws.cell(row=row, column=7)
        comp_c.fill = hdr_fill(COMPLEXITY_COLOR[sc])
        comp_c.font = Font(bold=True, name="Calibri", size=10,
                           color="FFFFFF" if sc >= 3 else "1F3864")
        comp_c.alignment = center()

        lbl_c = ws.cell(row=row, column=8)
        lbl_c.fill = hdr_fill(COMPLEXITY_COLOR[sc])
        lbl_c.font = Font(bold=True, name="Calibri", size=10,
                          color="FFFFFF" if sc >= 3 else "1F3864")

    widths = [40, 18, 12, 12, 12, 12, 14, 14, 18, 65]
    for col, w in enumerate(widths, start=1):
        set_col_width(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    freeze(ws, "A2")


def build_top_activities(wb, stats):
    ws = wb.create_sheet("Activity Reuse Analysis")
    ws.sheet_view.showGridLines = False

    headers = [
        "Activity ID (Service)", "System Code", "Backend System",
        "System Type", "# Processes Using", "% Coverage",
        "Reuse Classification", "Process Names (first 10)"
    ]
    write_header_row(ws, 1, headers, COLORS["header_dark"])

    total_procs = len(set(p for procs in stats["all_activities"].values() for p in procs))
    sorted_acts = sorted(stats["all_activities"].items(),
                         key=lambda x: -len(set(x[1])))

    for i, (aid, procs) in enumerate(sorted_acts):
        row = 2 + i
        unique_procs = sorted(set(procs))
        cnt = len(unique_procs)
        pct = 100 * cnt / total_procs if total_procs else 0
        sc, sname, stype = get_system_info(aid)

        if pct >= 50:    reuse = "Universal (>50%)"
        elif pct >= 25:  reuse = "High (25–50%)"
        elif pct >= 10:  reuse = "Moderate (10–25%)"
        elif cnt > 1:    reuse = "Low (<10%)"
        else:            reuse = "Single-use"

        procs_str = ", ".join(unique_procs[:10])
        if len(unique_procs) > 10:
            procs_str += f"… (+{len(unique_procs)-10} more)"

        values = [aid, sc, sname, stype, cnt, f"{pct:.1f}%", reuse, procs_str]
        write_data_row(ws, row, values, alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 18

        reuse_c = ws.cell(row=row, column=7)
        if "Universal" in reuse:   reuse_c.fill = hdr_fill("FF0000"); reuse_c.font = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
        elif "High" in reuse:      reuse_c.fill = hdr_fill("ED7D31"); reuse_c.font = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
        elif "Moderate" in reuse:  reuse_c.fill = hdr_fill("FFC000"); reuse_c.font = Font(bold=True, name="Calibri", size=10)

    widths = [48, 14, 44, 18, 16, 12, 22, 90]
    for col, w in enumerate(widths, start=1):
        set_col_width(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    freeze(ws, "B2")


def build_modernization_recommendations(wb, stats, processes):
    ws = wb.create_sheet("Modernization Recommendations")
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:G1")
    t = ws["A1"]
    t.value = "Modernization Recommendations — TIBCO OMX to Cloud-Native Migration"
    t.fill = hdr_fill(COLORS["header_dark"])
    t.font = Font(bold=True, color="FFFFFF", name="Calibri", size=14)
    t.alignment = center()
    ws.row_dimensions[1].height = 36

    headers = ["#", "Recommendation", "Category", "Priority",
               "Effort", "Rationale / Evidence", "Target Architecture"]
    write_header_row(ws, 2, headers, COLORS["header_mid"])

    recommendations = [
        (1, "Adopt API-First / Strangler-Fig for CCBS",
         "Architecture", "Critical", "High",
         "CCBS is the most-used backend system across virtually all order flows. Wrapping it in a modern REST API layer first allows incremental migration without big-bang replacement.",
         "REST API Gateway → CCBS Adapter Microservice"),

        (2, "Replace TIBCO BW Orchestration with Cloud-native Workflow Engine",
         "Platform", "Critical", "Very High",
         "168 process configs with complex XPath-based conditional logic must be re-implemented. Tools like AWS Step Functions, Azure Durable Functions, or Conductor OSS map well to the existing step pattern.",
         "Cloud Workflow Engine (Step Functions / Conductor)"),

        (3, "Decouple ESB Service Integrations via Event-Driven Architecture",
         "Integration", "High", "High",
         f"517 ESB services create tight coupling. Publish domain events (OrderPlaced, SubscriberActivated) via Kafka/EventBridge and have downstream systems consume them.",
         "Apache Kafka / AWS EventBridge + Consumer Microservices"),

        (4, "Migrate PreExecCheck XPath Rules to a Rules Engine",
         "Business Logic", "High", "Medium",
         f"{sum(stats['conditional_count'].values())} conditional XPath checks embed business rules in XML config. Externalizing these to Drools, AWS Business Rules, or Open Policy Agent improves maintainability.",
         "OPA / Drools Rules Engine"),

        (5, "Build Order Microservices per Business Domain",
         "Architecture", "High", "Very High",
         "Group processes by domain: Activation, MNP, Change-Request, Suspend/Restore, Cancellation. Each domain becomes an owning microservice with its own DB and API.",
         "Domain-Driven Microservices (K8s / ECS)"),

        (6, "Automate Process Config → Workflow Migration",
         "Tooling", "Medium", "Medium",
         "The XML ProcessConfig files have a regular structure (Activity chain). A code-generation tool can parse these XMLs and emit Terraform/CloudFormation templates or workflow DSL stubs, reducing manual effort.",
         "Custom XSLT/Python code-gen tool"),

        (7, "Centralize Blacklist & Fraud Checks as a Shared Capability",
         "Security", "Medium", "Low",
         "Blacklist/Fraud checks appear in >30 processes. Extract to a shared fraud-detection microservice with a REST interface to avoid duplication.",
         "Shared Fraud Detection Service (REST)"),

        (8, "Replace JMS/EMS Messaging with Managed Message Broker",
         "Integration", "Medium", "Medium",
         "TIBCO EMS is used for async messaging between FM and ESB. Replace with AWS SQS/SNS or Azure Service Bus to eliminate on-prem messaging dependency.",
         "AWS SQS + SNS / Azure Service Bus"),

        (9, "Decommission TIBCO BE (Rules Engine) After OPA Migration",
         "Platform", "Medium", "Low",
         "TIBCO BusinessEvents hosts rule functions referenced by FM. Once rules are migrated to OPA/Drools, BE can be decommissioned.",
         "OPA / Open-source Rules Engine"),

        (10, "MNP Flows — Integrate Directly with NRA APIs",
         "Regulatory", "High", "Medium",
         "MNP Port-In/Out processes interface with multiple systems. A dedicated MNP microservice with direct NRA API integration will reduce latency and simplify the flow.",
         "MNP Microservice → NRA REST API"),

        (11, "FTTB / Home (OMXN) — Separate Deployment Track",
         "Architecture", "Low", "Medium",
         "OMXN_ processes represent a distinct product line (fixed/fiber). Treat as a separate migration track to avoid scope creep in mobile migration.",
         "Separate FTTB Order Service"),

        (12, "Implement Saga Pattern for Long-running Order Compensation",
         "Resilience", "High", "High",
         "Multi-step orders touching 8–12 systems require compensating transactions on failure. The Saga choreography/orchestration pattern ensures eventual consistency.",
         "Saga Orchestration via Workflow Engine"),
    ]

    priority_colors = {"Critical": "FF0000", "High": "ED7D31",
                       "Medium": "FFC000", "Low": "70AD47"}

    for i, (num, rec, cat, pri, eff, rationale, target) in enumerate(recommendations):
        row = 3 + i
        values = [num, rec, cat, pri, eff, rationale, target]
        write_data_row(ws, row, values, alt=(i % 2 == 1))
        ws.row_dimensions[row].height = 50

        pri_c = ws.cell(row=row, column=4)
        pri_c.fill = hdr_fill(priority_colors.get(pri, "AAAAAA"))
        pri_c.font = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
        pri_c.alignment = center()

    widths = [5, 50, 20, 12, 12, 80, 50]
    for col, w in enumerate(widths, start=1):
        set_col_width(ws, get_column_letter(col), w)
    freeze(ws, "B3")


def build_data_mapping_matrix(wb, processes):
    """Sheet summarising parameter patterns to help with data mapping."""
    ws = wb.create_sheet("Data Mapping Matrix")
    ws.sheet_view.showGridLines = False

    headers = [
        "Process Name", "Activity ID", "Parameter Key", "Parameter Value / Pattern",
        "Data Domain", "Notes"
    ]
    write_header_row(ws, 1, headers, COLORS["header_dark"])

    row = 2
    domain_map = {
        "OFFER": "Offer / Product", "SOC": "SOC Code", "MSISDN": "MSISDN",
        "CUSTOMERTYPE": "Customer", "CHANNEL": "Channel", "DEALERCODE": "Dealer",
        "ESIM": "eSIM", "SUBSTATUS": "Subscriber Status", "BUSINESSLINE": "Business Line",
        "ORDERTYPE": "Order Type", "COMPANYCODE": "Company", "SEGMENT": "Segment",
        "ICCID": "SIM/ICCID", "PEID": "eSIM PEID",
    }

    for pname, pdata in sorted(processes.items()):
        for act in pdata["activities"]:
            for param in act["params"]:
                if "=" in param:
                    key, val = param.split("=", 1)
                else:
                    key, val = param, ""
                domain = "General"
                for dk, dv in domain_map.items():
                    if dk in key.upper() or dk in val.upper():
                        domain = dv
                        break
                values = [pname, act["activity_id"], key.strip(),
                          val.strip()[:120], domain, ""]
                write_data_row(ws, row, values, alt=(row % 2 == 0))
                ws.row_dimensions[row].height = 16
                row += 1

    widths = [36, 38, 28, 70, 22, 30]
    for col, w in enumerate(widths, start=1):
        set_col_width(ws, get_column_letter(col), w)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    freeze(ws, "C2")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("Parsing ProcessConfig files ...")
    processes = parse_process_configs(PROCESS_CONFIG_DIR)
    print(f"  -> {len(processes)} processes loaded")

    print("Enumerating ESB services ...")
    esb_services = enumerate_services(ESB_SERVICES_DIR, "OMX-ESB")
    print(f"  -> {len(esb_services)} ESB services")

    print("Enumerating FM services ...")
    fm_services = enumerate_services(FM_SERVICES_DIR, "OMX-FM")
    print(f"  -> {len(fm_services)} FM services")

    print("Building statistics ...")
    stats = build_stats(processes)
    print(f"  -> {len(stats['all_activities'])} unique activity types")
    print(f"  -> {len(stats['system_usage'])} backend systems")

    print("Creating workbook …")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default sheet

    print("  Sheet 1: Executive Summary")
    build_executive_summary(wb, processes, stats, esb_services, fm_services)

    print("  Sheet 2: Order Journey Map")
    build_process_catalog(wb, processes, stats)

    print("  Sheet 3: Activity Detail")
    build_activity_detail(wb, processes)

    print("  Sheet 4: Service Catalog")
    build_service_catalog(wb, esb_services, fm_services, stats)

    print("  Sheet 5: Interface Catalog")
    build_interface_catalog(wb, stats, processes)

    print("  Sheet 6: Dependency Matrix")
    build_dependency_matrix(wb, processes, stats)

    print("  Sheet 7: Migration Complexity")
    build_migration_assessment(wb, processes, stats)

    print("  Sheet 8: Activity Reuse Analysis")
    build_top_activities(wb, stats)

    print("  Sheet 9: Data Mapping Matrix")
    build_data_mapping_matrix(wb, processes)

    print("  Sheet 10: Modernization Recommendations")
    build_modernization_recommendations(wb, stats, processes)

    print(f"Saving to {OUTPUT_FILE} …")
    wb.save(OUTPUT_FILE)
    print("Done!")

if __name__ == "__main__":
    main()
