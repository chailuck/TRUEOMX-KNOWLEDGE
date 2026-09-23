#!/usr/bin/env python3
"""
generate_field_mapping.py

End-to-end field mapping:
  Order Request (OrderData fields) -> ProcessConfig Activity + Parameters
  -> FM Service (input schema) -> ESB Service -> Backend API + Request Fields

Output: TRUEOMX_Field_Mapping.xlsx  (6 sheets)
"""
import os, sys, re, json
from xml.etree import ElementTree as ET
from collections import defaultdict

try:
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    sys.exit("openpyxl not found. Run:  pip install openpyxl")

# ── Paths ─────────────────────────────────────────────────────────────────────
_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

def _resolve_base():
    import argparse as _ap, json as _js
    _p = _ap.ArgumentParser(add_help=False)
    _p.add_argument("--source-folder", default=None)
    _args, _ = _p.parse_known_args()
    if _args.source_folder:
        print(f"Using source folder from CLI: {_args.source_folder}")
        return os.path.join(_PROJECT_ROOT, _args.source_folder)
    cfg = os.path.join(_SCRIPT_DIR, "config.json")
    if os.path.isfile(cfg):
        with open(cfg, encoding="utf-8") as f:
            folder = _js.load(f).get("source_folder", "")
        if folder:
            print(f"Using source folder from config.json: {folder}")
            return os.path.join(_PROJECT_ROOT, folder)
    raise FileNotFoundError(
        "source_folder not set. Edit scripts/config.json or pass --source-folder")

BASE = _resolve_base()

# ── XSD namespace constant ────────────────────────────────────────────────────
XSD_NS = "http://www.w3.org/2001/XMLSchema"

# ── Excel style helpers ───────────────────────────────────────────────────────
COLORS = {
    "dark_blue":   "1F3864", "med_blue": "2E75B6", "light_blue":  "DEEAF1",
    "dark_green":  "375623", "med_green": "70AD47","light_green": "E2EFDA",
    "dark_purple": "412369", "med_purple":"7030A0","light_purple":"EBE5F2",
    "dark_red":    "833C00", "med_orange":"ED7D31","light_orange":"FDEBD0",
    "dark_teal":   "215868", "med_teal":  "2C8DA0","light_teal":  "D6EEF2",
    "row_alt":     "F5F5F5", "white":     "FFFFFF",
}

def _hdr_fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def _thin_border():
    s = Side(style="thin", color="BFBFBF")
    return Border(left=s, right=s, top=s, bottom=s)

def _style_header(ws, row_idx, fill_hex):
    fill = _hdr_fill(fill_hex)
    for cell in ws[row_idx]:
        cell.fill = fill
        cell.font = Font(bold=True, color="FFFFFF", size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _thin_border()

def _set_col_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

def _row_fill(ws, r, ncols, hex_color):
    fill = _hdr_fill(hex_color)
    for c in range(1, ncols + 1):
        ws.cell(row=r, column=c).fill = fill

def _apply_cell(ws, r, c):
    cell = ws.cell(row=r, column=c)
    cell.alignment = Alignment(wrap_text=True, vertical="top")
    cell.border    = _thin_border()
    return cell

# ── 1. Load global substitution variables (regex approach) ────────────────────
def load_global_vars(vars_dir):
    """Walk .substvar files, build {rel_path/VAR_NAME: value} via regex."""
    gvars = {}
    if not os.path.isdir(vars_dir):
        return gvars
    for root, _, files in os.walk(vars_dir):
        for fname in files:
            if not fname.endswith(".substvar"):
                continue
            fpath = os.path.join(root, fname)
            rel   = os.path.relpath(root, vars_dir).replace("\\", "/")
            try:
                content = open(fpath, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            for m in re.finditer(
                r'<globalVariable>\s*<name>([^<]+)</name>\s*<value>([^<]*)</value>',
                content, re.DOTALL
            ):
                var_name  = m.group(1).strip()
                var_value = m.group(2).strip()
                key = f"{rel}/{var_name}" if rel != "." else var_name
                gvars[key] = var_value
    return gvars

def resolve_var(var_expr, gvars):
    """Resolve %%path/VAR_NAME%% from gvars. Returns (url, key) or ('', key)."""
    if not var_expr:
        return "", ""
    m = re.search(r"%%([^%]+)%%", var_expr)
    if not m:
        return var_expr if var_expr.startswith("http") else "", ""
    clean = m.group(1).strip()
    # Direct lookup
    val = gvars.get(clean, "")
    if val:
        return val, clean
    # Fallback: match by last two segments
    suffix = "/".join(clean.split("/")[-2:])
    for k, v in gvars.items():
        if k.endswith(suffix):
            return v, k
    return "", clean

# ── 2. Parse ALL ProcessConfig XML files ─────────────────────────────────────
PC_NS = "http://services.omx.truecorp.co.th/ProcessConfig"

def parse_all_processconfig(base):
    """
    Returns {process_name: [
        {seq, activity_id, ext_id, params:[(k,v)], pre_exec, prev, next}
    ]}
    Skips archive/backup subdirs.
    """
    pc_dir = os.path.join(base, "SupportingFiles", "Configs", "ProcessConfig")
    result = {}
    if not os.path.isdir(pc_dir):
        print(f"  [WARN] ProcessConfig dir not found: {pc_dir}")
        return result

    for root_dir, dirs, files in os.walk(pc_dir):
        dirs[:] = [d for d in dirs if d.lower() not in ("archive", "backupfttbuat")]
        for fname in files:
            if not fname.endswith(".xml"):
                continue
            fpath    = os.path.join(root_dir, fname)
            proc_name = os.path.splitext(fname)[0]
            try:
                tree  = ET.parse(fpath)
                rootel = tree.getroot()
                activities = []
                seq = 0
                for act in rootel.findall(f"{{{PC_NS}}}Activities"):
                    seq += 1
                    aid      = (act.findtext(f"{{{PC_NS}}}ActivityID")      or "").strip()
                    prev_act = (act.findtext(f"{{{PC_NS}}}PreviousActivity") or "").strip()
                    next_act = (act.findtext(f"{{{PC_NS}}}NextActivity")     or "").strip()
                    pre_exec = (act.findtext(f"{{{PC_NS}}}PreExecCheck")     or "").strip()
                    ext_id   = act.get("extId", "")

                    params = []
                    for p in act.findall(f"{{{PC_NS}}}Parameter"):
                        txt = (p.text or "").strip()
                        if "=" in txt:
                            k, _, v = txt.partition("=")
                            params.append((k.strip(), v.strip()))
                        elif txt:
                            params.append((txt, ""))

                    activities.append({
                        "seq":         seq,
                        "activity_id": aid,
                        "ext_id":      ext_id,
                        "params":      params,
                        "pre_exec":    pre_exec,
                        "prev":        prev_act.split(":")[-1] if ":" in prev_act else prev_act,
                        "next":        next_act.split(":")[-1] if ":" in next_act else next_act,
                    })
                if activities:
                    result[proc_name] = activities
            except Exception as e:
                print(f"  [WARN] Cannot parse {fname}: {e}")
    return result

# ── 3. Extract order-request field references from XPath ─────────────────────
_FIELD_RE = re.compile(
    r"(?://OrderData/|/ns0:OrderRequest/OrderData/)"
    r"([A-Za-z][A-Za-z0-9_]*/[A-Za-z][A-Za-z0-9_/]*|[A-Za-z][A-Za-z0-9_]+)"
    r"(?:/text\(\))?",
    re.IGNORECASE
)

def extract_order_fields(xpath_str):
    """Return sorted list of 'OrderData/FieldPath' strings found in XPath."""
    fields = set()
    for m in _FIELD_RE.finditer(xpath_str):
        path = m.group(1).rstrip("/")
        path = re.sub(r"\[.*?\]", "", path).rstrip("/")
        if path:
            fields.add("OrderData/" + path)
    return sorted(fields)

# ── 4. Load activity->FM->ESB mapping from activity_fm_mapping.json ──────────
def load_activity_mapping():
    """
    Returns dict keyed by activity_id (upper).
    Values: {fm_queue, payload_root, req_queue, event_name, ...}
    """
    map_path = os.path.join(_SCRIPT_DIR, "activity_fm_mapping.json")
    if not os.path.isfile(map_path):
        print("  [INFO] activity_fm_mapping.json not found - run extract_mapping.py first")
        return {}
    with open(map_path, encoding="utf-8") as f:
        raw = json.load(f)
    # Normalise keys to upper
    return {k.upper(): v for k, v in raw.items() if isinstance(v, dict)}

# ── 5. Fuzzy ESB service lookup ───────────────────────────────────────────────
def _norm(s):
    return re.sub(r"[_\-\s]", "", s).lower()

def build_esb_service_index(esb_services_dir):
    """Returns {norm_name: actual_dir_name} for all dirs under esb_services_dir."""
    idx = {}
    if not os.path.isdir(esb_services_dir):
        return idx
    for d in os.listdir(esb_services_dir):
        if os.path.isdir(os.path.join(esb_services_dir, d)):
            idx[_norm(d)] = d
    return idx

def find_esb_service(activity_id, esb_idx):
    """
    Try to match activity_id to an ESB service directory name.
    Tries: exact, prefix-exact, common-substring.
    """
    aid_norm = _norm(activity_id)
    # Exact
    if aid_norm in esb_idx:
        return esb_idx[aid_norm]
    # Try dropping first token (system prefix): GET_PRODUCT_PREFERENCE_LIST -> getproductpreferencelist
    parts = activity_id.split("_")
    if len(parts) > 1:
        rest_norm = _norm("_".join(parts[1:]))
        if rest_norm in esb_idx:
            return esb_idx[rest_norm]
    # Try the full activity id matches a prefix of an ESB service name
    prefix = parts[0].lower()
    candidates = [(k, v) for k, v in esb_idx.items()
                  if k.startswith(prefix) and aid_norm in k]
    if len(candidates) == 1:
        return candidates[0][1]
    if not candidates:
        # Best substring match
        best_k, best_v, best_score = None, None, 0
        for k, v in esb_idx.items():
            score = sum(1 for ch in aid_norm if ch in k)
            ratio = score / max(len(aid_norm), len(k), 1)
            if ratio > 0.85 and score > best_score:
                best_score, best_k, best_v = score, k, v
        if best_v:
            return best_v
    return None

# ── 6. XSD field flattening ───────────────────────────────────────────────────
_CT_CACHE = {}  # xsd_path -> {typename: ET.Element}

def _collect_complex_types(xsd_path, visited=None):
    """Recursively collect complexType defs from an XSD and its imports."""
    if visited is None:
        visited = set()
    if xsd_path in visited or not os.path.isfile(xsd_path):
        return {}
    visited.add(xsd_path)
    if xsd_path in _CT_CACHE:
        return _CT_CACHE[xsd_path]
    ct = {}
    try:
        tree  = ET.parse(xsd_path)
        root_ = tree.getroot()
        for el in root_:
            if el.tag.split("}")[-1] == "complexType":
                name = el.get("name")
                if name:
                    ct[name] = el
        # Follow imports / includes
        for imp in root_:
            tag = imp.tag.split("}")[-1]
            if tag in ("import", "include"):
                loc = imp.get("schemaLocation", "")
                if loc:
                    imp_path = os.path.normpath(
                        os.path.join(os.path.dirname(xsd_path), loc))
                    ct.update(_collect_complex_types(imp_path, visited))
    except Exception:
        pass
    _CT_CACHE[xsd_path] = ct
    return ct

def _expand_elem(elem, prefix, fields, ct, depth, max_depth):
    if depth > max_depth:
        return
    is_arr  = elem.get("maxOccurs", "1") not in ("1", "0")
    req_val = "N" if elem.get("minOccurs", "1") == "0" else "Y"
    type_attr  = elem.get("type", "")
    local_type = type_attr.split(":")[-1] if ":" in type_attr else type_attr

    # Find complexType definition: inline first, then referenced
    inline_ct = None
    for child in elem:
        if child.tag.split("}")[-1] == "complexType":
            inline_ct = child
            break
    ref_ct    = ct.get(local_type)
    complex_el = inline_ct or ref_ct

    if complex_el is not None:
        # Recurse into sequence / all / choice
        for tag_suffix in ("sequence", "all", "choice"):
            container = None
            for child in complex_el:
                if child.tag.split("}")[-1] == tag_suffix:
                    container = child
                    break
            if container is not None:
                for child in container:
                    ctag = child.tag.split("}")[-1]
                    if ctag == "element":
                        cname = child.get("name", "?")
                        _expand_elem(child, f"{prefix}.{cname}",
                                     fields, ct, depth + 1, max_depth)
                    elif ctag in ("sequence", "all", "choice"):
                        for sub in child:
                            if sub.tag.split("}")[-1] == "element":
                                sname = sub.get("name", "?")
                                _expand_elem(sub, f"{prefix}.{sname}",
                                             fields, ct, depth + 1, max_depth)
                break
        else:
            fields.append((prefix, local_type or "object", req_val, is_arr))
    else:
        fields.append((prefix, local_type or type_attr or "string", req_val, is_arr))

def flatten_xsd_file(xsd_path, root_elem_filter=None, max_depth=6):
    """Return [(field_path, type, required, is_array)] from an XSD file."""
    if not os.path.isfile(xsd_path):
        return []
    try:
        tree  = ET.parse(xsd_path)
        root_ = tree.getroot()
    except Exception:
        return []
    ct   = _collect_complex_types(xsd_path)
    fields = []
    for el in root_:
        if el.tag.split("}")[-1] != "element":
            continue
        name = el.get("name", "")
        if root_elem_filter and name != root_elem_filter:
            continue
        _expand_elem(el, name, fields, ct, 0, max_depth)
    return fields

def flatten_inline_xsd(xsd_str, max_depth=5):
    """
    Parse inline XSD string from restInputReferNode or pd:startType.
    Works regardless of whether the root is <xs:schema>, <restInputReferNode>,
    or <pd:startType> — scans root's direct children for xs:element tags.
    """
    if not xsd_str:
        return []
    try:
        root_ = ET.fromstring(xsd_str)
    except Exception:
        return []

    # Collect all complexType definitions anywhere in the subtree
    ct = {}
    for el in root_.iter():
        if el.tag.split("}")[-1] == "complexType":
            name = el.get("name")
            if name:
                ct[name] = el

    fields = []
    # Look for xs:element children of the root (works for schema, restInputReferNode, pd:startType)
    for el in root_:
        if el.tag.split("}")[-1] == "element":
            _expand_elem(el, el.get("name", "root"), fields, ct, 0, max_depth)

    return fields

# ── 6b. Schema location resolver ──────────────────────────────────────────────
def _resolve_schema_loc(loc, common_schemas, alt_base=None):
    """
    Resolve schemaLocation like '/_SharedResources/Schemas/ESB/X/Y.xsd'
    to an absolute file path, trying common_schemas and alt_base.
    """
    # Strip leading '/_SharedResources/Schemas/' prefix (absolute TIBCO path)
    stripped = re.sub(r"^/?_?SharedResources/Schemas/", "", loc.lstrip("/"))
    cands = [os.path.join(common_schemas, stripped.replace("/", os.sep))]
    if alt_base:
        cands.append(os.path.join(alt_base, "_SharedResources", "Schemas",
                                  stripped.replace("/", os.sep)))
    # Also try the raw normalised path directly under each base
    raw = loc.replace("/", os.sep).lstrip(os.sep)
    for base in ([common_schemas] + ([alt_base] if alt_base else [])):
        cands.append(os.path.join(base, raw))
    for c in cands:
        nc = os.path.normpath(c)
        if os.path.isfile(nc):
            return nc
    return None

# ── 7. Parse FM subprocess for input schema ───────────────────────────────────
def parse_fm_schema(fm_base, fm_queue, common_schemas):
    """
    Returns [(field_path, type, req, is_array)] for the FM service input schema.
    fm_queue is the directory name under OMX-FM/Services/.
    """
    svc_dir = os.path.join(fm_base, "Services", fm_queue)
    if not os.path.isdir(svc_dir):
        # case-insensitive fallback
        svc_root = os.path.join(fm_base, "Services")
        if os.path.isdir(svc_root):
            for d in os.listdir(svc_root):
                if d.lower() == fm_queue.lower():
                    svc_dir = os.path.join(svc_root, d)
                    break
    if not os.path.isdir(svc_dir):
        return []

    PD = "http://xmlns.tibco.com/bw/process/2003"
    for fname in os.listdir(svc_dir):
        if not fname.endswith(".process") or fname.lower() == "main.process":
            continue
        ppath = os.path.join(svc_dir, fname)
        try:
            tree  = ET.parse(ppath)
            root_ = tree.getroot()

            # ── Approach 1: imported ESB request XSD ──────────────────────
            # Find all xsd:import elements; prefer ones whose schemaLocation
            # looks like an ESB service schema (under /Schemas/ESB/ or /INTX/ etc.)
            esb_schema_imports = []
            other_imports = []
            for imp in root_.findall(f".//{{{XSD_NS}}}import"):
                loc = imp.get("schemaLocation", "")
                if not loc:
                    continue
                # Skip FM-internal schemas (Schema.xsd, logging, etc.)
                if any(skip in loc for skip in
                       ("Schema.xsd", "Logging", "AuditLog", "EngineTypes",
                        "DeployedVars", "ErrorActivity")):
                    continue
                if "/ESB/" in loc or "/INTX/" in loc or "/CCBS/" in loc \
                        or "/VCARE/" in loc or "/OTA/" in loc:
                    esb_schema_imports.append(loc)
                else:
                    other_imports.append(loc)

            # Sort ESB imports by name similarity to the FM service name
            # so we pick the schema that matches this specific service, not
            # a co-imported schema from a different downstream call.
            fm_norm_full = _norm(fm_queue)
            fm_parts     = fm_queue.split("_", 1)
            fm_core_norm = _norm(fm_parts[1]) if len(fm_parts) > 1 else fm_norm_full

            def _import_score(loc):
                base = _norm(os.path.splitext(os.path.basename(loc))[0])
                if base == fm_norm_full:
                    return 100
                if base == fm_core_norm:
                    return 90
                if fm_core_norm and (fm_core_norm in base or base in fm_core_norm):
                    return 50
                return 0

            sorted_esb = sorted(esb_schema_imports,
                                key=_import_score, reverse=True)

            for loc in sorted_esb + other_imports:
                cand = _resolve_schema_loc(loc, common_schemas, fm_base)
                if not cand or not os.path.isfile(cand):
                    continue
                f2 = flatten_xsd_file(cand)
                if not f2:
                    continue
                # Prefer Req element; fall back to first elements found
                req_f = [x for x in f2 if "Req" in x[0]]
                if req_f:
                    return req_f
                return f2

            # ── Approach 2: pd:startType inline XSD ───────────────────────
            start = root_.find(f"{{{PD}}}startType")
            if start is not None:
                xsd_str = ET.tostring(start, encoding="unicode")
                fields  = flatten_inline_xsd(xsd_str)
                # Filter out purely internal fields (ESBUUID, OrderType, etc.)
                schema_fields = [f for f in fields if f[0] not in
                                 ("root.ESBUUID", "root.OrderType", "root")]
                if schema_fields:
                    return schema_fields
                if fields:
                    return fields
        except Exception:
            pass
    return []

# ── 8a. WSDL helpers ──────────────────────────────────────────────────────────
def _resolve_wsdl_path(loc, common_schemas):
    """Resolve /_SharedResources/WSDL/xxx.wsdl to an absolute file path."""
    PREFIXES = ("/_SharedResources/WSDL/", "/_SharedResources/")
    shared_root = os.path.dirname(common_schemas)          # OMX-COMMON/_SharedResources
    wsdl_root   = os.path.join(shared_root, "WSDL")
    for pfx in PREFIXES:
        if loc.startswith(pfx):
            rel = loc[len(pfx):]
            cand = os.path.normpath(os.path.join(wsdl_root, rel.replace("/", os.sep)))
            if os.path.isfile(cand):
                return cand
    # Try just the filename
    basename = os.path.basename(loc)
    cand = os.path.join(wsdl_root, basename)
    return cand if os.path.isfile(cand) else None


def _extract_wsdl_endpoint(wsdl_path):
    """Return SOAP address location URL from a WSDL, or '' if not found."""
    try:
        content = open(wsdl_path, encoding="utf-8", errors="ignore").read()
        m = re.search(r'<[^>]*:?address\s[^>]*location=["\']([^"\']+)["\']',
                      content, re.I)
        if m:
            url = m.group(1).strip()
            if url.startswith("http"):
                return url
    except Exception:
        pass
    return ""


_WSDL_SCHEMA_CACHE = {}

def _flatten_wsdl_types(wsdl_path, elem_filter=None, max_depth=5):
    """
    Parse a WSDL file's <wsdl:types> section and return
    [(field_path, type, required, is_array)] for request elements.

    elem_filter: if given, only return fields for this element name.
    """
    cache_key = (wsdl_path, elem_filter)
    if cache_key in _WSDL_SCHEMA_CACHE:
        return _WSDL_SCHEMA_CACHE[cache_key]

    WSDL_NS = "http://schemas.xmlsoap.org/wsdl/"
    results  = []
    try:
        tree  = ET.parse(wsdl_path)
        root_ = tree.getroot()

        # Find wsdl:types
        types_el = root_.find(f"{{{WSDL_NS}}}types")
        if types_el is None:
            types_el = root_.find("types")
        if types_el is None:
            _WSDL_SCHEMA_CACHE[cache_key] = []
            return []

        # Build a COMBINED complexType cache from ALL schema sections.
        # WSDLs often split operation elements (Schema[0]) from data types
        # (Schema[1], Schema[2]...) so we must merge all schemas.
        all_ct = {}
        for schema_el in types_el:
            for child in schema_el:
                if child.tag.split("}")[-1] == "complexType":
                    name = child.get("name")
                    if name:
                        all_ct[name] = child

        # Find and expand top-level element definitions using the combined ct
        for schema_el in types_el:
            for el in schema_el:
                tag  = el.tag.split("}")[-1]
                name = el.get("name", "")
                if tag != "element":
                    continue
                if elem_filter and name != elem_filter:
                    continue
                fields = []
                _expand_elem(el, name, fields, all_ct, 0, max_depth)
                results.extend(fields)
            if results:
                break
    except Exception:
        pass

    _WSDL_SCHEMA_CACHE[cache_key] = results
    return results


# ── 8. Parse ESB service for request schema + endpoint ────────────────────────
def scan_esb_service(esb_services_dir, svc_name, gvars, common_schemas):
    """
    Returns {protocol, method, endpoint, endpoint_var, auth,
             request_fields, response_fields, xsd_source}
    """
    svc_dir = os.path.join(esb_services_dir, svc_name)
    if not os.path.isdir(svc_dir):
        return {}

    PD = "http://xmlns.tibco.com/bw/process/2003"
    proc_files = [os.path.join(svc_dir, f)
                  for f in os.listdir(svc_dir) if f.endswith(".process")]

    rest_info    = None
    soap_info    = None
    xsd_imports  = []   # [(schemaLocation, process_file)]
    wsdl_imports = []   # [(wsdl_path, process_file)]
    pd_start_refs = []  # element names referenced via pd:startType ref=

    for pf in proc_files:
        try:
            content = open(pf, encoding="utf-8", errors="ignore").read()
            tree    = ET.parse(pf)
            root_   = tree.getroot()
        except Exception:
            continue

        # Collect xsd:import / xsd:include paths — split by .wsdl vs .xsd
        WSDL_NS_WSDL = "http://schemas.xmlsoap.org/wsdl/"
        for imp in (root_.findall(f".//{{{XSD_NS}}}import") +
                    root_.findall(f".//{{{XSD_NS}}}include") +
                    root_.findall(f".//{{{WSDL_NS_WSDL}}}import")):
            loc = imp.get("schemaLocation") or imp.get("location") or ""
            if not loc:
                continue
            if loc.lower().endswith(".wsdl"):
                wpath = _resolve_wsdl_path(loc, common_schemas)
                if wpath:
                    wsdl_imports.append((wpath, pf))
            else:
                xsd_imports.append((loc, pf))

        # Collect element refs from pd:startType (used by WSDL-backed services)
        for st in root_.findall(f"{{{PD}}}startType"):
            for ref_el in st.iter():
                ref = ref_el.get("ref", "")
                if ref and ":" in ref:
                    # strip namespace prefix: pfx8:l9MultiReverseCredit → l9MultiReverseCredit
                    pd_start_refs.append(ref.split(":")[-1])

        if rest_info is None and re.search(r"RestActivity|HttpClient", content):
            for act in root_.findall(f"{{{PD}}}activity"):
                act_type = act.findtext(f"{{{PD}}}type") or ""
                if "RestActivity" not in act_type and "HttpClient" not in act_type:
                    continue
                config = act.find("config")
                if config is None:
                    continue
                method   = (config.findtext("restMethodUI") or
                            config.findtext("method") or "POST").upper()
                auth     = config.findtext("authChoiceUI") or "None"
                xsd_node = config.find("restInputReferNode")
                xsd_str  = ET.tostring(xsd_node, encoding="unicode") if xsd_node is not None else ""
                # URI from inputBindings - extract GlobalVariables path from <URI> element
                uri_var = ""
                bindings = act.find(f"{{{PD}}}inputBindings")
                if bindings is not None:
                    raw_b = ET.tostring(bindings, encoding="unicode")
                    # Extract just the <URI>…</URI> block first to avoid matching
                    # unrelated substvar refs (e.g. TimeoutSec) that appear earlier.
                    uri_block_m = re.search(r"<URI[^>]*>(.*?)</URI>",
                                            raw_b, re.DOTALL)
                    uri_block = uri_block_m.group(1) if uri_block_m else ""
                    # Within the URI block, find the first GlobalVariables path
                    m = re.search(
                        r"GlobalVariables/(OMX_ESB/[A-Za-z0-9_/]+)",
                        uri_block) if uri_block else None
                    if not m:
                        # Fallback in full bindings: look for URI/URL/Endpoint keywords
                        m = re.search(
                            r"GlobalVariables/([^\s<>\"',&]*"
                            r"(?:URI|URL|Endpoint|Endpt|Address)"
                            r"[^\s<>\"',&]*)",
                            raw_b, re.I)
                    if m:
                        uri_var = m.group(1)
                rest_info = {"method": method, "auth": auth,
                             "xsd_str": xsd_str, "uri_var": uri_var}
                break

        if soap_info is None and re.search(r"SOAPSend|SOAPClient|\.wsdl", content, re.I):
            for act in root_.findall(f"{{{PD}}}activity"):
                act_type = act.findtext(f"{{{PD}}}type") or ""
                if "soap" not in act_type.lower():
                    continue
                config = act.find("config")
                if config is None:
                    continue
                soap_info = {
                    "operation": config.findtext("operation") or "",
                    "wsdl":      config.findtext("wsdlURL") or config.findtext("wsdl") or "",
                }
                break

    # ── Resolve fields ──────────────────────────────────────────────────────
    req_fields  = []
    resp_fields = []
    xsd_source  = ""

    if rest_info:
        # 1. Inline XSD
        if rest_info.get("xsd_str"):
            req_fields = flatten_inline_xsd(rest_info["xsd_str"])
            xsd_source = "inline"

        # 2. Imported XSD files
        if not req_fields:
            esb_module_base = os.path.dirname(esb_services_dir)  # OMX-ESB dir
            for loc, ref_file in xsd_imports:
                # Try proper path resolution first
                cand = _resolve_schema_loc(loc, common_schemas, esb_module_base)
                if not cand:
                    # Relative to the process file itself
                    cand2 = os.path.normpath(
                        os.path.join(os.path.dirname(ref_file), loc))
                    cand = cand2 if os.path.isfile(cand2) else None
                if cand and os.path.isfile(cand):
                    f2 = flatten_xsd_file(cand)
                    if f2:
                        req_fields  = [x for x in f2 if "Req" in x[0]]
                        resp_fields = [x for x in f2 if "Res" in x[0]]
                        if not req_fields:
                            req_fields = f2
                        xsd_source = os.path.basename(cand)
                        break
                if req_fields:
                    break

        # Resolve endpoint URL
        endpoint, ep_key = "", ""
        if rest_info.get("uri_var"):
            endpoint, ep_key = resolve_var(
                f"%%{rest_info['uri_var']}%%", gvars)
            if not endpoint:
                # Try appending OMX_ESB/ prefix if not already there
                uri_v = rest_info['uri_var']
                if not uri_v.startswith("OMX_ESB/"):
                    endpoint, ep_key = resolve_var(
                        f"%%OMX_ESB/{uri_v}%%", gvars)

        return {
            "protocol":       "REST",
            "method":         rest_info.get("method", "POST"),
            "endpoint":       endpoint,
            "endpoint_var":   rest_info.get("uri_var", ""),
            "auth":           rest_info.get("auth", ""),
            "request_fields": req_fields,
            "response_fields": resp_fields,
            "xsd_source":     xsd_source,
        }

    elif soap_info:
        # For SOAP, try to find WSDL-adjacent XSD
        wsdl_path = soap_info.get("wsdl", "")
        for loc, ref_file in xsd_imports:
            loc_norm = loc.replace("/", os.sep).lstrip(os.sep)
            cand = os.path.join(common_schemas, loc_norm)
            if os.path.isfile(cand):
                f2 = flatten_xsd_file(cand)
                req_fields.extend([x for x in f2 if "Req" in x[0]])
                resp_fields.extend([x for x in f2 if "Res" in x[0]])
                if not xsd_source:
                    xsd_source = os.path.basename(cand)

        endpoint, _ = resolve_var(wsdl_path, gvars)
        return {
            "protocol":       "SOAP",
            "method":         "POST",
            "endpoint":       endpoint or wsdl_path,
            "endpoint_var":   wsdl_path,
            "auth":           "WS-Security",
            "operation":      soap_info.get("operation", ""),
            "request_fields": req_fields,
            "response_fields": resp_fields,
            "xsd_source":     xsd_source,
        }

    # ── EJB / WSDL-backed pattern ────────────────────────────────────────────
    # Covers: CCBS_* (EJB via Tibco_CCBS_Client) and AR_* / SBM / BL etc.
    esb_module_base = os.path.dirname(esb_services_dir)  # OMX-ESB dir
    SKIP = ("Response", "Logging", "AuditLog", "EngineTypes",
            "DeployedVars", "ErrorActivity", "EmailContent",
            "SendLog", "AuditEvent", "CCPHeader")

    # Score a filename by similarity to the service name and pd:startType refs.
    # Higher score = better match.
    svc_norm = _norm(svc_name)
    svc_parts = svc_name.split("_", 1)
    svc_core  = _norm(svc_parts[1]) if len(svc_parts) > 1 else svc_norm
    ref_norms = [_norm(r) for r in pd_start_refs]

    def _score_name(filename):
        base = _norm(os.path.splitext(filename)[0])
        if base == svc_norm:
            return 200
        if base == svc_core:
            return 190
        for rn in ref_norms:
            if base == rn:
                return 180
            if rn and (rn in base or base in rn):
                return 100
        if svc_core and (svc_core in base or base in svc_core):
            return 50
        return 0

    # 1. WSDL imports: prefer WSDLs whose name/content matches service or ref
    # Strategy: for each pd_start_ref, find the WSDL that has that element,
    # then fall back to score-sorted WSDL list.
    endpoint    = ""
    wsdl_source = ""

    # Sort WSDLs: those containing a pd_start_ref element get priority
    def _wsdl_priority(item):
        wpath, _ = item
        fname = os.path.basename(wpath)
        score = _score_name(fname)
        # Boost if any ref name appears as an element in this WSDL
        for ref_name in pd_start_refs:
            f2 = _flatten_wsdl_types(wpath, elem_filter=ref_name)
            if f2:
                score += 500
                break
        return -score  # negate for ascending sort

    sorted_wsdls = sorted(wsdl_imports, key=_wsdl_priority)

    for wpath, _ in sorted_wsdls:
        ep = _extract_wsdl_endpoint(wpath)
        if ep and not endpoint:
            endpoint    = ep
            wsdl_source = os.path.basename(wpath)
        # Try each pd:startType ref element in THIS wsdl
        for ref_name in pd_start_refs:
            f2 = _flatten_wsdl_types(wpath, elem_filter=ref_name)
            if f2:
                req_fields = f2
                xsd_source = os.path.basename(wpath)
                break
        if req_fields:
            break
        # Fallback: first non-Response element from this WSDL
        if not req_fields and _score_name(os.path.basename(wpath)) > 0:
            all_f = _flatten_wsdl_types(wpath)
            req_f = [x for x in all_f if not any(
                     s in x[0] for s in ("Response", "Return", "Result"))]
            if req_f:
                req_fields = req_f
                xsd_source = os.path.basename(wpath)
                break

    # 2. Direct XSD imports (CCBS_* EJB pattern) — sort by service-name match
    if not req_fields:
        filtered_xsds = [
            (loc, ref_file) for loc, ref_file in xsd_imports
            if not any(s in loc for s in SKIP)
        ]
        scored_xsds = sorted(
            filtered_xsds,
            key=lambda x: -_score_name(os.path.basename(x[0])))
        for loc, ref_file in scored_xsds:
            cand = _resolve_schema_loc(loc, common_schemas, esb_module_base)
            if not cand:
                cand2 = os.path.normpath(
                    os.path.join(os.path.dirname(ref_file), loc))
                cand = cand2 if os.path.isfile(cand2) else None
            if cand and os.path.isfile(cand):
                f2 = flatten_xsd_file(cand)
                if f2:
                    req_f = [x for x in f2
                             if any(k in x[0] for k in ("Req", "Request", "Input"))
                             and "Response" not in x[0] and "Result" not in x[0]]
                    resp_f = [x for x in f2
                              if any(k in x[0] for k in ("Response", "Result", "Return"))]
                    if req_f:
                        req_fields  = req_f
                        resp_fields = resp_f
                        xsd_source  = os.path.basename(cand)
                        break

    if req_fields or wsdl_imports or (xsd_imports and
            not all(any(s in loc for s in SKIP) for loc, _ in xsd_imports)):
        protocol = "SOAP" if (wsdl_imports and endpoint) else "EJB"
        return {
            "protocol":       protocol,
            "method":         "POST",
            "endpoint":       endpoint,
            "endpoint_var":   wsdl_source,
            "auth":           "WS-Security" if wsdl_imports else "Java-EJB",
            "request_fields": req_fields,
            "response_fields": resp_fields,
            "xsd_source":     xsd_source,
        }

    return {}

# ── 9. Build complete mapping ─────────────────────────────────────────────────
def build_mapping(base, gvars):
    print("Parsing ProcessConfig files ...")
    processes = parse_all_processconfig(base)
    print(f"  -> {len(processes)} order processes")

    print("Loading activity -> FM mapping ...")
    act_map = load_activity_mapping()
    print(f"  -> {len(act_map)} activity entries")

    esb_base       = os.path.join(base, "OMX-ESB")
    fm_base        = os.path.join(base, "OMX-FM")
    common_base    = os.path.join(base, "OMX-COMMON")
    common_schemas = os.path.join(common_base, "_SharedResources", "Schemas")
    esb_svcs_dir   = os.path.join(esb_base, "Services")

    print("Building ESB and FM service indexes ...")
    esb_idx = build_esb_service_index(esb_svcs_dir)
    fm_idx  = build_esb_service_index(os.path.join(fm_base, "Services"))  # same logic
    print(f"  -> {len(esb_idx)} ESB services, {len(fm_idx)} FM services")

    # ── Collect which ESB services + FM queues we actually need ──────────────
    needed_esb = {}  # activity_id_upper -> esb_svc_name
    needed_fm  = {}  # activity_id_upper -> fm_dir_name

    for proc_name, activities in processes.items():
        for act in activities:
            aid = act["activity_id"].upper()
            info = act_map.get(aid, {})
            fm_q = ""
            if isinstance(info, dict):
                fm_q = info.get("fm_queue", "")
            # FM: use fm_queue if available, else fuzzy match from activity ID
            if fm_q:
                needed_fm[aid] = fm_q
            else:
                fm_svc = find_esb_service(aid, fm_idx)
                if fm_svc:
                    needed_fm[aid] = fm_svc
            # ESB: fuzzy match from activity ID
            esb_svc = find_esb_service(aid, esb_idx)
            if esb_svc:
                needed_esb[aid] = esb_svc

    print(f"  -> {len(needed_esb)} activities mapped to ESB services")
    print(f"  -> {len(set(needed_esb.values()))} unique ESB services to scan")

    # ── Scan each unique ESB service once ────────────────────────────────────
    print("Scanning ESB service schemas ...")
    esb_schema_cache = {}  # svc_name -> info dict
    for svc_name in sorted(set(needed_esb.values())):
        esb_schema_cache[svc_name] = scan_esb_service(
            esb_svcs_dir, svc_name, gvars, common_schemas)

    # ── Parse FM schemas ──────────────────────────────────────────────────────
    print("Parsing FM input schemas ...")
    fm_schema_cache = {}  # fm_dir_name -> [(path, type, req, arr)]
    for fm_q in sorted(set(needed_fm.values())):
        fm_schema_cache[fm_q] = parse_fm_schema(fm_base, fm_q, common_schemas)

    resolved_ep   = sum(1 for i in esb_schema_cache.values() if i.get("endpoint"))
    schema_ok     = sum(1 for i in esb_schema_cache.values() if i.get("request_fields"))
    print(f"  -> {len(esb_schema_cache)} ESB services scanned, "
          f"{resolved_ep} endpoints resolved, {schema_ok} schemas extracted")

    # ── Assemble rows ─────────────────────────────────────────────────────────
    chain_rows     = []
    param_rows     = []
    order_field_map = defaultdict(lambda: defaultdict(set))  # field -> process -> {aids}

    for proc_name, activities in sorted(processes.items()):
        for act in activities:
            aid    = act["activity_id"]
            aid_up = aid.upper()
            seq    = act["seq"]
            params = act["params"]
            xpath  = act["pre_exec"]

            system = aid.split("_")[0] if "_" in aid else aid

            # Order request fields from XPath condition
            ord_fields = extract_order_fields(xpath)
            for f in ord_fields:
                order_field_map[f][proc_name].add(aid)

            # Param rows
            for k, v in params:
                param_rows.append((proc_name, aid, system, k, v))

            # FM / ESB info
            fm_queue = needed_fm.get(aid_up, "")
            fm_schema = fm_schema_cache.get(fm_queue, [])

            esb_svc  = needed_esb.get(aid_up, "")
            esb_info = esb_schema_cache.get(esb_svc, {})

            protocol = esb_info.get("protocol", "")
            endpoint = esb_info.get("endpoint", "")
            method   = esb_info.get("method", "")
            auth     = esb_info.get("auth", "")

            req_fields = esb_info.get("request_fields", [])
            # Summary: show leaf fields (not truncated containers).
            # For generic JSON pass-through services, fall back to FM schema.
            generic_field_names = {"Parameters", "Query", "Header", "Body", "Text",
                                   "Form", "Binary", "Multipart", "content", "type",
                                   "param", "name", "filename"}
            leaf_req = [
                (fp, ft, fr, fa) for fp, ft, fr, fa in req_fields
                if not ft or ft in ("string", "int", "integer", "boolean",
                                    "dateTime", "date", "decimal", "float", "double")
                or (isinstance(ft, str) and ft.startswith("xs:"))
            ]
            is_generic = all(fp.split(".")[-1] in generic_field_names
                             for fp, *_ in req_fields[:5]) if req_fields else True
            if is_generic and fm_schema:
                # Use FM schema for request fields (more business-meaningful)
                top_req = [
                    f"{fp} ({ft})"
                    for fp, ft, fr, fa in fm_schema[:20]
                    if ft not in ("object",) and "?" not in fp
                ]
                req_summary = "(From FM schema)\n" + "\n".join(top_req)
            else:
                top_req = [f"{fp} ({ft})" for fp, ft, fr, fa in leaf_req[:20]]
                req_summary = "\n".join(top_req)

            # FM schema summary
            fm_summary_parts = []
            seen_fm = set()
            for fp, ft, fr, fa in fm_schema:
                root_seg = fp.split(".")[0]
                if root_seg not in seen_fm:
                    seen_fm.add(root_seg)
                if fp.count(".") <= 1:
                    fm_summary_parts.append(f"{fp} ({ft})")
            fm_summary = "\n".join(fm_summary_parts[:15])

            params_str = "\n".join(f"{k}={v}" for k, v in params)
            ord_str    = "\n".join(ord_fields)

            chain_rows.append({
                "process":      proc_name,
                "seq":          seq,
                "activity_id":  aid,
                "system":       system,
                "order_fields": ord_str,
                "params":       params_str,
                "fm_queue":     fm_queue,
                "fm_summary":   fm_summary,
                "esb_service":  esb_svc,
                "protocol":     protocol,
                "method":       method,
                "endpoint":     endpoint,
                "auth":         auth,
                "req_summary":  req_summary,
            })

    return {
        "chain_rows":       chain_rows,
        "param_rows":       param_rows,
        "order_field_map":  order_field_map,
        "esb_schema_cache": esb_schema_cache,
        "fm_schema_cache":  fm_schema_cache,
        "processes":        processes,
        "act_map":          act_map,
        "needed_esb":       needed_esb,
    }

# ── 10. Write Excel ───────────────────────────────────────────────────────────
def write_excel(data, source_folder):
    wb = Workbook()
    wb.remove(wb.active)

    chain_rows = data["chain_rows"]

    # ─── Sheet 1: E2E Chain (per activity) ───────────────────────────────────
    ws1 = wb.create_sheet("E2E Chain")
    hdrs1 = [
        "Order Process", "Seq", "Activity ID", "System",
        "Order Request Fields\n(from XPath conditions)",
        "Config Parameters\n(KEY=VALUE)",
        "FM Service\n(fm_queue)",
        "FM Input Schema Fields",
        "ESB Service",
        "Protocol", "Method", "Endpoint URL", "Auth",
        "API Request Fields\n(top-level)",
    ]
    ws1.append(hdrs1)
    _style_header(ws1, 1, COLORS["dark_blue"])
    ws1.row_dimensions[1].height = 40
    ws1.freeze_panes = "A2"

    prev_proc = None
    row_idx   = 2
    for r in chain_rows:
        proc = r["process"]
        row_data = [
            proc, r["seq"], r["activity_id"], r["system"],
            r["order_fields"], r["params"],
            r["fm_queue"], r["fm_summary"],
            r["esb_service"],
            r["protocol"], r["method"], r["endpoint"], r["auth"],
            r["req_summary"],
        ]
        ws1.append(row_data)
        if proc != prev_proc:
            _row_fill(ws1, row_idx, len(hdrs1), COLORS["light_blue"])
            prev_proc = proc
        elif row_idx % 2 == 0:
            _row_fill(ws1, row_idx, len(hdrs1), COLORS["row_alt"])
        h = max(15, 14 * max(1,
                              r["order_fields"].count("\n") + 1,
                              r["params"].count("\n") + 1,
                              r["req_summary"].count("\n") + 1))
        ws1.row_dimensions[row_idx].height = min(h, 200)
        for c in range(1, len(hdrs1) + 1):
            _apply_cell(ws1, row_idx, c)
        row_idx += 1

    _set_col_widths(ws1,
        [28, 5, 40, 14, 38, 38, 30, 38, 35, 8, 7, 55, 18, 45])

    # ─── Sheet 2: Order Request Fields ───────────────────────────────────────
    ws2 = wb.create_sheet("Order Request Fields")
    hdrs2 = ["Order Request Field (XPath)", "Used in\n# Activities",
             "Order Processes that Reference It",
             "Activities that Reference It"]
    ws2.append(hdrs2)
    _style_header(ws2, 1, COLORS["dark_green"])
    ws2.row_dimensions[1].height = 28
    ws2.freeze_panes = "A2"

    row_idx = 2
    ofd = data["order_field_map"]
    for field_path in sorted(ofd.keys()):
        proc_map = ofd[field_path]
        procs = sorted(proc_map.keys())
        acts  = sorted(set(a for v in proc_map.values() for a in v))
        ws2.append([
            field_path,
            len(acts),
            "\n".join(procs),
            "\n".join(acts[:25]),
        ])
        if row_idx % 2 == 0:
            _row_fill(ws2, row_idx, len(hdrs2), COLORS["light_green"])
        ws2.row_dimensions[row_idx].height = max(15, 14 * len(procs))
        for c in range(1, len(hdrs2) + 1):
            _apply_cell(ws2, row_idx, c)
        row_idx += 1

    _set_col_widths(ws2, [50, 12, 50, 60])

    # ─── Sheet 3: Config Parameters ──────────────────────────────────────────
    ws3 = wb.create_sheet("Config Parameters")
    hdrs3 = ["Order Process", "Activity ID", "System",
             "Parameter Key", "Parameter Value"]
    ws3.append(hdrs3)
    _style_header(ws3, 1, COLORS["dark_purple"])
    ws3.row_dimensions[1].height = 24
    ws3.freeze_panes = "A2"

    row_idx   = 2
    prev_proc = None
    for proc, aid, sys_, k, v in sorted(data["param_rows"], key=lambda x: (x[0], x[1])):
        ws3.append([proc, aid, sys_, k, v])
        if proc != prev_proc:
            _row_fill(ws3, row_idx, len(hdrs3), COLORS["light_purple"])
            prev_proc = proc
        elif row_idx % 2 == 0:
            _row_fill(ws3, row_idx, len(hdrs3), COLORS["row_alt"])
        for c in range(1, len(hdrs3) + 1):
            _apply_cell(ws3, row_idx, c)
        row_idx += 1

    _set_col_widths(ws3, [30, 45, 14, 35, 55])

    # ─── Sheet 4: API Request Schema (per ESB service) ───────────────────────
    ws4 = wb.create_sheet("API Request Schema")
    hdrs4 = [
        "ESB Service", "System", "Protocol", "Method",
        "Endpoint URL", "Auth",
        "Field Path (dot notation)", "Field Type", "Req?", "Array?",
        "XSD Source",
    ]
    ws4.append(hdrs4)
    _style_header(ws4, 1, COLORS["dark_red"])
    ws4.row_dimensions[1].height = 24
    ws4.freeze_panes = "A2"

    row_idx  = 2
    prev_svc = None
    for svc_name, info in sorted(data["esb_schema_cache"].items()):
        protocol   = info.get("protocol", "")
        method     = info.get("method", "")
        endpoint   = info.get("endpoint", "")
        auth       = info.get("auth", "")
        xsd_src    = info.get("xsd_source", "")
        req_fields = info.get("request_fields", [])
        system     = svc_name.split("_")[0] if "_" in svc_name else svc_name

        if not req_fields:
            ws4.append([svc_name, system, protocol, method, endpoint, auth,
                        "(schema not resolved)", "", "", "", xsd_src])
            _row_fill(ws4, row_idx, len(hdrs4), COLORS["light_orange"])
            for c in range(1, len(hdrs4) + 1):
                _apply_cell(ws4, row_idx, c)
            row_idx += 1
            prev_svc = svc_name
            continue

        for fp, ft, fr, fa in req_fields:
            first_of_svc = svc_name != prev_svc
            ws4.append([
                svc_name if first_of_svc else "",
                system   if first_of_svc else "",
                protocol if first_of_svc else "",
                method   if first_of_svc else "",
                endpoint if first_of_svc else "",
                auth     if first_of_svc else "",
                fp, ft, fr, "Y" if fa else "N", xsd_src,
            ])
            if first_of_svc:
                _row_fill(ws4, row_idx, len(hdrs4), COLORS["light_orange"])
                prev_svc = svc_name
            elif row_idx % 2 == 0:
                _row_fill(ws4, row_idx, len(hdrs4), COLORS["row_alt"])
            for c in range(1, len(hdrs4) + 1):
                _apply_cell(ws4, row_idx, c)
            row_idx += 1

    _set_col_widths(ws4, [35, 14, 8, 7, 55, 20, 45, 15, 5, 6, 30])

    # ─── Sheet 5: Activity -> API Quick Lookup ───────────────────────────────
    ws5 = wb.create_sheet("Activity-API Lookup")
    hdrs5 = [
        "Activity ID", "System", "FM Service", "ESB Service",
        "Protocol", "Method", "Endpoint URL", "Auth",
        "Request Fields Summary",
    ]
    ws5.append(hdrs5)
    _style_header(ws5, 1, COLORS["dark_teal"])
    ws5.row_dimensions[1].height = 24
    ws5.freeze_panes = "A2"

    row_idx = 2
    seen    = set()
    for r in sorted(chain_rows, key=lambda x: x["activity_id"]):
        aid = r["activity_id"]
        if aid in seen:
            continue
        seen.add(aid)
        if not r["esb_service"] and not r["fm_queue"]:
            continue
        esb_info = data["esb_schema_cache"].get(r["esb_service"], {})
        req_flds = esb_info.get("request_fields", [])
        # Leaf-level field names summary (no deeper than depth 2)
        field_names = [fp.split(".")[-1] for fp, *_ in req_flds if fp.count(".") <= 2]
        summary = ", ".join(dict.fromkeys(field_names[:20]).keys())

        ws5.append([
            aid, r["system"],
            r["fm_queue"], r["esb_service"],
            esb_info.get("protocol", r["protocol"]),
            esb_info.get("method", r["method"]),
            esb_info.get("endpoint", r["endpoint"]),
            esb_info.get("auth", r["auth"]),
            summary,
        ])
        if row_idx % 2 == 0:
            _row_fill(ws5, row_idx, len(hdrs5), COLORS["row_alt"])
        for c in range(1, len(hdrs5) + 1):
            _apply_cell(ws5, row_idx, c)
        ws5.row_dimensions[row_idx].height = max(15, 14 * (summary.count(",") // 6 + 1))
        row_idx += 1

    _set_col_widths(ws5, [42, 14, 30, 35, 8, 7, 55, 18, 65])

    # ─── Sheet 6: Field Lineage (Order Field -> Systems) ─────────────────────
    ws6 = wb.create_sheet("Field Lineage")
    hdrs6 = [
        "Order Request Field", "# Activities Using It",
        "Systems Driven by This Field",
        "Sample Activities (first 20)",
    ]
    ws6.append(hdrs6)
    _style_header(ws6, 1, COLORS["dark_blue"])
    ws6.row_dimensions[1].height = 24
    ws6.freeze_panes = "A2"

    row_idx  = 2
    act_map  = data["act_map"]
    needed_esb = data["needed_esb"]
    for field_path in sorted(data["order_field_map"].keys()):
        proc_map = data["order_field_map"][field_path]
        acts_all = sorted(set(a for v in proc_map.values() for a in v))
        systems  = set()
        for a in acts_all:
            esb_svc = needed_esb.get(a.upper(), "")
            sys_    = a.split("_")[0] if "_" in a else a
            systems.add(sys_)

        ws6.append([
            field_path,
            len(acts_all),
            ", ".join(sorted(systems)),
            "\n".join(acts_all[:20]),
        ])
        if row_idx % 2 == 0:
            _row_fill(ws6, row_idx, len(hdrs6), COLORS["light_blue"])
        ws6.row_dimensions[row_idx].height = max(15, 13 * min(len(acts_all), 20))
        for c in range(1, len(hdrs6) + 1):
            _apply_cell(ws6, row_idx, c)
        row_idx += 1

    _set_col_widths(ws6, [50, 14, 55, 65])

    # ─── Cover ───────────────────────────────────────────────────────────────
    ws0 = wb.create_sheet("Cover", 0)
    ws0.sheet_view.showGridLines = False
    ws0.column_dimensions["A"].width = 32
    ws0.column_dimensions["B"].width = 65

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cr  = data["chain_rows"]
    cover = [
        ("TRUEOMX End-to-End Field Mapping", ""),
        ("", ""),
        ("Source Folder",   source_folder),
        ("Generated",       now),
        ("Order Processes", str(len(data["processes"]))),
        ("Total Activities",str(len(cr))),
        ("With FM Mapping", str(sum(1 for r in cr if r["fm_queue"]))),
        ("With ESB / Endpoint",
         str(sum(1 for r in cr if r["endpoint"]))),
        ("Config Parameters", str(len(data["param_rows"]))),
        ("Order Request Fields", str(len(data["order_field_map"]))),
        ("ESB Services Scanned",str(len(data["esb_schema_cache"]))),
        ("ESB Schemas Resolved",
         str(sum(1 for i in data["esb_schema_cache"].values()
                 if i.get("request_fields")))),
        ("", ""),
        ("Sheet", "Description"),
        ("1. E2E Chain",
         "Per-activity chain: order fields > config params > FM > ESB > endpoint > API fields"),
        ("2. Order Request Fields",
         "All OrderData field paths from XPath conditions; usage across processes"),
        ("3. Config Parameters",
         "Static KEY=VALUE parameters per activity across all order processes"),
        ("4. API Request Schema",
         "Per ESB service: endpoint URL, protocol, auth, request field schema"),
        ("5. Activity-API Lookup",
         "Quick table: Activity ID -> FM service -> ESB service -> endpoint -> fields"),
        ("6. Field Lineage",
         "Order field -> which systems / activities it drives"),
    ]
    for r_idx, (label, value) in enumerate(cover, 1):
        c1 = ws0.cell(r_idx, 1, label)
        c2 = ws0.cell(r_idx, 2, value)
        if r_idx == 1:
            c1.font = Font(bold=True, size=16, color=COLORS["dark_blue"])
            ws0.row_dimensions[r_idx].height = 30
        elif label == "Sheet":
            c1.font = Font(bold=True, size=11, color=COLORS["med_blue"])
            c2.font = Font(bold=True, size=11, color=COLORS["med_blue"])
        elif label.startswith(("1.", "2.", "3.", "4.", "5.", "6.")):
            c1.font = Font(size=10, color=COLORS["dark_teal"])
            c2.font = Font(size=10, color="595959")
        elif label:
            c1.font = Font(bold=True, size=10)
            c2.font = Font(size=10)

    return wb

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    vars_dir = os.path.join(BASE, "OMX-ESB", "defaultVars")
    print("Loading substitution variables ...")
    gvars = load_global_vars(vars_dir)
    print(f"  -> {len(gvars)} variables loaded")

    data = build_mapping(BASE, gvars)

    out_path = os.path.join(_PROJECT_ROOT, "output", "summary", "TRUEOMX_Field_Mapping.xlsx")
    print(f"\nWriting workbook -> {out_path}")
    wb   = write_excel(data, os.path.basename(BASE))
    wb.save(out_path)

    cr = data["chain_rows"]
    print(f"\nDone!")
    print(f"  Order processes         : {len(data['processes'])}")
    print(f"  Total activities        : {len(cr)}")
    print(f"  Activities with FM      : {sum(1 for r in cr if r['fm_queue'])}")
    print(f"  Activities with endpoint: {sum(1 for r in cr if r['endpoint'])}")
    print(f"  Config parameters       : {len(data['param_rows'])}")
    print(f"  Order request fields    : {len(data['order_field_map'])}")
    print(f"  ESB services scanned    : {len(data['esb_schema_cache'])}")
    print(f"  ESB schemas resolved    : "
          f"{sum(1 for i in data['esb_schema_cache'].values() if i.get('request_fields'))}")
    print(f"\nOutput: {out_path}")

if __name__ == "__main__":
    main()
