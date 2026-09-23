"""
Generate OpenAPI 3.0 (Swagger) spec + HTML documentation
for non-EJB outbound integrations (REST + SOAP) in TRUEOMX ESB.

Endpoint URLs are resolved from TIBCO substitution variable files (*.substvar).

Outputs (written to project root):
  TRUEOMX_REST_SOAP_API.json  — OpenAPI 3.0 JSON specification
  TRUEOMX_REST_SOAP_API.yaml  — OpenAPI 3.0 YAML specification
  TRUEOMX_REST_SOAP_API.html  — Interactive Swagger UI documentation (requires internet for CDN)
  TRUEOMX_REST_SOAP_Static.html — Static HTML report (fully offline)
"""

import os, re, json, sys, xml.etree.ElementTree as ET
from datetime import date
from collections import defaultdict


# ── Config / paths ─────────────────────────────────────────────────────────────
def _resolve_base():
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

_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

BASE     = _resolve_base()
ESB_DIR  = os.path.join(BASE, "OMX-ESB", "Services")
VARS_DIR = os.path.join(BASE, "OMX-ESB", "defaultVars")

OUT_JSON        = os.path.join(_PROJECT_ROOT, "output", "summary", "TRUEOMX_REST_SOAP_API.json")
OUT_YAML        = os.path.join(_PROJECT_ROOT, "output", "summary", "TRUEOMX_REST_SOAP_API.yaml")
OUT_HTML        = os.path.join(_PROJECT_ROOT, "output", "summary", "TRUEOMX_REST_SOAP_API.html")
OUT_HTML_STATIC = os.path.join(_PROJECT_ROOT, "output", "summary", "TRUEOMX_REST_SOAP_Static.html")


# ── HTTP status descriptions ───────────────────────────────────────────────────
HTTP_STATUS = {
    "200": "OK", "201": "Created", "202": "Accepted", "204": "No Content",
    "400": "Bad Request", "401": "Unauthorized", "403": "Forbidden",
    "404": "Not Found", "408": "Request Timeout", "409": "Conflict",
    "500": "Internal Server Error", "502": "Bad Gateway", "503": "Service Unavailable",
}

# ── Backend system descriptions ────────────────────────────────────────────────
SYSTEM_DESC = {
    "AA":     "AA – True/DTAC provisioning (Inventory/Network)",
    "APIGW":  "APIGW – API Gateway (OAuth token + routed APIs)",
    "ATS":    "ATS – Campaign & Promotion REST API",
    "BDH":    "BDH – Big Data Hub REST API",
    "CAT":    "CAT – Product Catalog (CCBS EJB via REST wrapper)",
    "CCP":    "CCP – Customer Control Portal REST API",
    "CIA":    "CIA – Customer Intelligence & Analytics REST API",
    "CJ":     "CJ – Customer Journey REST API",
    "CRM":    "CRM – Customer Relationship Management REST API",
    "GCS":    "GCS – GreenCard/SIM Validation REST API",
    "INT":    "INT – CCBs Integration SOAP services (billing, balance)",
    "INTX":   "INTX – INTX SIM management SOAP services",
    "OMXN":   "OMXN – OMX-N internal notification REST",
    "VCA":    "VCA – VCARE SOAP service",
    "VCARE":  "VCARE – VCARE SOAP service (alternate prefix)",
    "CDB":    "CDB – Customer Database SOAP/HTTP service",
    "MCS":    "MCS – Mediation SOAP service",
    "NTF":    "NTF – Notification REST service",
    "KNOX":   "KNOX – Samsung Knox MDM REST API",
    "REDIS":  "REDIS – Redis cache REST API",
}


# ── Step 1: Load global substitution variables from *.substvar files ───────────
def load_global_vars(vars_dir):
    """
    Walk OMX-ESB/defaultVars recursively and build:
      {  "OMX_ESB/Env/GCS/GCS_ValidateByPass/URI_ValidateByPass": "https://...",  ...  }
    """
    gvars = {}
    if not os.path.isdir(vars_dir):
        return gvars

    for root, _, files in os.walk(vars_dir):
        for fname in files:
            if not fname.endswith(".substvar"):
                continue
            fpath = os.path.join(root, fname)
            # Derive the variable namespace from the file path relative to vars_dir
            rel = os.path.relpath(root, vars_dir).replace("\\", "/")
            # e.g., "OMX_ESB/Env/GCS/GCS_ValidateByPass"
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


def resolve_endpoint(var_ref, gvars):
    """
    Resolve %%OMX_ESB/Env/X/Y/VAR_NAME%% -> actual URL from substvar files.
    Also handles partial refs like %%OMX_ESB/Env/X/EndpointURL%%.
    """
    if not var_ref:
        return "", ""
    # Already a URL
    if var_ref.startswith("http"):
        return var_ref, ""
    # Look up in gvars
    clean = var_ref.strip("%").strip()
    value = gvars.get(clean, "")
    if value:
        return value, clean
    # Try without leading OMX_ESB/ prefix
    short = re.sub(r'^OMX_ESB/', '', clean)
    for k, v in gvars.items():
        if k.endswith("/" + short.split("/")[-1]) and short.split("/")[-1] in k:
            return v, k
    return "", clean


# ── Step 2: Classify ESB service backend type ─────────────────────────────────
def classify_backend(content):
    if re.search(r"com\.tibco\.plugin\.json\.activities\.RestActivity|RestActivity", content):
        return "REST"
    if re.search(r"com\.tibco\.plugin\.soap|SOAPSendReceive|SOAPSend|\.wsdl", content):
        return "SOAP"
    if re.search(r"JMSQueueRequestReply", content) and re.search(r"adapter\.", content, re.I):
        return "JMS-Adapter"
    if re.search(r"Tibco_CCBS_Client", content):
        return "EJB"
    if re.search(r"JMSQueueRequestReply|JMSSend", content):
        return "JMS-Internal"
    return "Unknown"


# ── Step 3: XSD → JSON Schema converter ───────────────────────────────────────
_XSD_TYPE_MAP = {
    "xsd:string":      {"type": "string"},
    "xsd:integer":     {"type": "integer", "format": "int32"},
    "xsd:int":         {"type": "integer", "format": "int32"},
    "xsd:long":        {"type": "integer", "format": "int64"},
    "xsd:double":      {"type": "number",  "format": "double"},
    "xsd:float":       {"type": "number",  "format": "float"},
    "xsd:decimal":     {"type": "number"},
    "xsd:boolean":     {"type": "boolean"},
    "xsd:date":        {"type": "string",  "format": "date"},
    "xsd:dateTime":    {"type": "string",  "format": "date-time"},
    "xsd:base64Binary":{"type": "string",  "format": "byte"},
    "xsd:anyType":     {"type": "object"},
    "xsd:anySimpleType":{"type": "string"},
}

def xsd_elements_to_schema(xsd_str, depth=0):
    """Parse a fragment of XSD and return an OpenAPI-compatible JSON Schema dict."""
    if depth > 4 or not xsd_str:
        return {"type": "object"}

    props = {}
    required = []

    for m in re.finditer(
        r'<xsd:element\s([^>]*?)(?:/>|>(.*?)</xsd:element>)',
        xsd_str, re.DOTALL
    ):
        attrs = m.group(1)
        inner = m.group(2) or ""

        name_m = re.search(r'name="([^"]+)"', attrs)
        if not name_m:
            continue
        name = name_m.group(1)

        type_m      = re.search(r'\btype="([^"]+)"', attrs)
        min_occ_m   = re.search(r'minOccurs="([^"]+)"', attrs)
        max_occ_m   = re.search(r'maxOccurs="([^"]+)"', attrs)

        is_optional = min_occ_m and min_occ_m.group(1) == "0"
        is_array    = max_occ_m and max_occ_m.group(1) in ("unbounded", "2", "3", "4", "5", "10", "99")

        if not is_optional:
            required.append(name)

        if type_m:
            prop = dict(_XSD_TYPE_MAP.get(type_m.group(1), {"type": "string"}))
        elif "<xsd:complexType" in inner:
            seq_m = re.search(r'<xsd:sequence>(.*?)</xsd:sequence>', inner, re.DOTALL)
            if seq_m:
                nested = xsd_elements_to_schema(seq_m.group(1), depth + 1)
                prop = {"type": "object"}
                if nested.get("properties"):
                    prop["properties"] = nested["properties"]
            else:
                prop = {"type": "object"}
        elif "<xsd:simpleType" in inner:
            enum_vals = re.findall(r'<xsd:enumeration value="([^"]+)"', inner)
            prop = {"type": "string"}
            if enum_vals:
                prop["enum"] = enum_vals
        else:
            prop = {"type": "string"}

        props[name] = {"type": "array", "items": prop} if is_array else prop

    result = {"type": "object"}
    if props:
        result["properties"] = props
    if required:
        result["required"] = required
    return result


def extract_input_schema(xsd_str):
    """
    From restInputReferNode XSD, extract request body schema.
    Returns (query_params[], header_names[], body_schema, content_type).
    """
    query_params = []
    header_names = []
    body_schema  = {}
    content_type = "application/json"

    # Get the Parameters > sequence
    seq_m = re.search(
        r'<xsd:element name="Parameters"[^>]*>.*?<xsd:sequence>(.*?)</xsd:sequence>',
        xsd_str, re.DOTALL
    )
    if not seq_m:
        return query_params, header_names, body_schema, content_type

    top = xsd_elements_to_schema(seq_m.group(1), depth=0)
    top_props = top.get("properties", {})

    # Query parameters
    if "Query" in top_props:
        q = top_props["Query"]
        for pname, pschema in q.get("properties", {}).items():
            query_params.append({"name": pname, "schema": pschema})

    # Header parameters
    if "Header" in top_props:
        h = top_props["Header"]
        header_names = list(h.get("properties", {}).keys())

    # Body
    if "Body" in top_props:
        body = top_props["Body"]
        body_p = body.get("properties", {})
        if "Form" in body_p:
            content_type = "application/x-www-form-urlencoded"
            body_schema  = body_p["Form"]
        elif "Text" in body_p:
            content_type = "application/json"
            body_schema  = {"type": "string", "description": "JSON body (passed as raw text to backend)"}
        elif "Binary" in body_p:
            content_type = "application/octet-stream"
            body_schema  = {"type": "string", "format": "binary"}
        else:
            body_schema = body

    return query_params, header_names, body_schema, content_type


# ── Step 4: Parse individual REST service ─────────────────────────────────────
def parse_rest_service(svc_path, svc_name, gvars):
    rec = {
        "name":         svc_name,
        "type":         "REST",
        "method":       "POST",
        "endpoint":     "",
        "endpoint_var": "",
        "content_type": "application/json",
        "response_type":"JSON",
        "auth":         "None",
        "timeout_sec":  "",
        "query_params": [],
        "header_names": [],
        "body_schema":  {},
        "response_schema": {},
        "status_codes": [],
        "form_fields":  [],
    }

    combined = ""
    for fname in sorted(os.listdir(svc_path)):
        if fname.endswith(".process"):
            try:
                combined += open(os.path.join(svc_path, fname), encoding="utf-8", errors="ignore").read()
            except Exception:
                pass
    if not combined:
        return rec

    # HTTP method
    m = re.search(r'<restMethodUI>([^<]+)</restMethodUI>', combined)
    if m:
        rec["method"] = m.group(1).strip().upper()

    # Response content type
    m = re.search(r'<restResponseType>([^<]+)</restResponseType>', combined)
    if m:
        rec["response_type"] = m.group(1).strip()

    # Auth
    m = re.search(r'<authChoiceUI>([^<]+)</authChoiceUI>', combined)
    if m:
        rec["auth"] = m.group(1).strip()

    # Timeout
    m = re.search(r'<Timeout>\s*<xsl:value-of select="[^"]*TimeoutSec\s*\*\s*1000"', combined)
    if not m:
        m = re.search(r'<timeout>([^<%%\n]+)</timeout>', combined)
    if m and hasattr(m, 'group') and m.lastindex:
        rec["timeout_sec"] = m.group(1).strip() if m.lastindex >= 1 else ""

    # Endpoint variable reference
    var_m = re.search(
        r'<URI>\s*<xsl:value-of\s+select="\$_globalVariables[^/]*/([^"]+)"',
        combined
    )
    if var_m:
        var_path = var_m.group(1).replace("/ns2:GlobalVariables/", "")
        var_path = re.sub(r'^[^/]+/', '', var_path)  # remove namespace prefix
        # Try resolving the variable path
        rec["endpoint_var"] = var_path
        rec["endpoint"], _ = resolve_endpoint(var_path, gvars)
    else:
        # Direct URL
        url_m = re.search(r'<URI>(https?://[^<]+)</URI>', combined)
        if url_m:
            rec["endpoint"] = url_m.group(1).strip()

    # Status codes from flow transitions
    for sc in re.findall(r'StatusCode\s*[=>"]+\s*"?(\d{3})"?', combined):
        if sc not in rec["status_codes"]:
            rec["status_codes"].append(sc)

    # Input schema from restInputReferNode XSD
    in_m = re.search(r'<restInputReferNode>(.*?)</restInputReferNode>', combined, re.DOTALL)
    if in_m:
        qp, hn, bs, ct = extract_input_schema(in_m.group(1))
        rec["query_params"]  = qp
        rec["header_names"]  = hn
        rec["body_schema"]   = bs
        rec["content_type"]  = ct

    # Form fields fallback (from XSLT)
    if not rec["body_schema"] and "Form" in combined:
        for field in re.findall(
            r'<([A-Za-z_][A-Za-z0-9_]+)>\s*<xsl:value-of select="\$Start/root/([^"]+)"',
            combined
        ):
            if field[0] not in ("URI", "Timeout", "content", "type"):
                rec["form_fields"].append(field[0])
        if rec["form_fields"]:
            rec["content_type"] = "application/x-www-form-urlencoded"

    # Additional headers from XSLT (Authorization, Content-Type, etc.)
    extra_headers = re.findall(
        r'<(Authorization|Content-Type|X-[A-Za-z0-9-]+|ApiKey|api[_-]key)>',
        combined
    )
    for h in extra_headers:
        if h not in rec["header_names"]:
            rec["header_names"].append(h)

    return rec


# ── Step 5: Parse individual SOAP service ─────────────────────────────────────
def parse_soap_service(svc_path, svc_name, gvars):
    rec = {
        "name":            svc_name,
        "type":            "SOAP",
        "method":          "POST",
        "operation":       "",
        "service":         "",
        "port":            "",
        "wsdl":            "",
        "soap_action":     "",
        "endpoint":        "",
        "endpoint_var":    "",
        "auth":            "NONE",
        "timeout_sec":     "",
        "request_fields":  {},
        "response_fields": {},
    }

    combined = ""
    for fname in sorted(os.listdir(svc_path)):
        if fname.endswith(".process"):
            try:
                combined += open(os.path.join(svc_path, fname), encoding="utf-8", errors="ignore").read()
            except Exception:
                pass
    if not combined:
        return rec

    for tag, key in [("operation", "operation"), ("service", "service"),
                     ("servicePort", "port"), ("authScheme", "auth"),
                     ("soapAction", "soap_action")]:
        m = re.search(rf'<{tag}>([^<]+)</{tag}>', combined)
        if m:
            rec[key] = m.group(1).strip()

    # WSDL reference
    m = re.search(r'schemaLocation="[^"]*?([A-Za-z0-9_-]+\.wsdl)"', combined)
    if m:
        rec["wsdl"] = m.group(1)

    # Endpoint URL from substvar
    ep_m = re.search(r'<endpointURL>%%([^%]+)%%</endpointURL>', combined)
    if ep_m:
        var_path = ep_m.group(1).strip()
        rec["endpoint_var"] = var_path
        rec["endpoint"], _ = resolve_endpoint(var_path, gvars)
    else:
        ep_direct = re.search(r'<endpointURL>(https?://[^<]+)</endpointURL>', combined)
        if ep_direct:
            rec["endpoint"] = ep_direct.group(1).strip()

    # Timeout
    m = re.search(r'<timeout>([^<%%\n]+)</timeout>', combined)
    if m:
        rec["timeout_sec"] = m.group(1).strip()

    # Request fields from inputMessage XSLT
    in_m = re.search(r'<inputMessage>(.*?)</inputMessage>', combined, re.DOTALL)
    if in_m:
        for f in re.findall(r'<([a-zA-Z][a-zA-Z0-9_]+)>\s*(?:<xsl:copy-of|<xsl:value-of)', in_m.group(1)):
            if f not in ("headers", "username", "password", "Header"):
                rec["request_fields"][f] = {"type": "string"}

    # Response fields from returnBindings XSLT
    ret_m = re.search(r'<pd:returnBindings>(.*?)</pd:returnBindings>', combined, re.DOTALL)
    if ret_m:
        for f in re.findall(r'<xsl:value-of select="[^"]*?/([a-zA-Z][a-zA-Z0-9_]+)"', ret_m.group(1)):
            if f not in ("xsi", "nil", "type"):
                rec["response_fields"][f] = {"type": "string"}

    return rec


# ── Step 6: Scan all ESB services, filter non-EJB ─────────────────────────────
def parse_all_services(esb_dir, gvars):
    services = []
    if not os.path.isdir(esb_dir):
        raise FileNotFoundError(f"ESB services dir not found: {esb_dir}")

    svc_names = sorted(os.listdir(esb_dir))
    print(f"  Scanning {len(svc_names)} ESB service directories ...")

    rest_n = soap_n = skip_n = 0
    for svc_name in svc_names:
        svc_path = os.path.join(esb_dir, svc_name)
        if not os.path.isdir(svc_path):
            continue

        combined = ""
        for fname in os.listdir(svc_path):
            if fname.endswith(".process"):
                try:
                    combined += open(os.path.join(svc_path, fname), encoding="utf-8", errors="ignore").read()
                except Exception:
                    pass
        if not combined:
            continue

        backend = classify_backend(combined)

        if backend == "REST":
            svc = parse_rest_service(svc_path, svc_name, gvars)
            services.append(svc)
            rest_n += 1
        elif backend == "SOAP":
            svc = parse_soap_service(svc_path, svc_name, gvars)
            services.append(svc)
            soap_n += 1
        else:
            skip_n += 1

    print(f"  REST: {rest_n}  |  SOAP: {soap_n}  |  Skipped (EJB/JMS): {skip_n}")
    return services


# ── Step 7: Build OpenAPI 3.0 spec ────────────────────────────────────────────
def build_openapi_spec(services, source_folder):
    rest_n = sum(1 for s in services if s["type"] == "REST")
    soap_n = sum(1 for s in services if s["type"] == "SOAP")

    # Group by system prefix
    systems = defaultdict(list)
    for svc in services:
        prefix = svc["name"].split("_")[0]
        systems[prefix].append(svc)

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "TRUEOMX ESB Non-EJB Outbound Integration API",
            "version": "1.0.0",
            "description": (
                f"Outbound REST and SOAP integration specification extracted from TIBCO OMX Order Management.\n\n"
                f"**Source folder**: `{source_folder}`  \n"
                f"**Generated**: {date.today().isoformat()}  \n\n"
                f"**Scope**: Non-EJB outbound only — REST ({rest_n} services) + SOAP ({soap_n} services).  \n"
                f"EJB (CCBS-Client), JMS-Adapter, and JMS-Internal integrations are excluded.\n\n"
                f"**Endpoint resolution**: URLs are resolved from TIBCO global substitution variables "
                f"(`*.substvar` files). Displayed URLs are UAT/default values.\n\n"
                f"**Total services**: {len(services)}"
            ),
            "contact": {"name": "DTAC TRUEOMX Transformation Team"},
            "x-generated-by": "TRUEOMX AI Discovery — generate_swagger_spec.py",
        },
        "tags": [],
        "servers": [
            {
                "url": "https://{host}/esb",
                "description": "TIBCO ESB (endpoint resolved from global vars at runtime)",
                "variables": {
                    "host": {
                        "default": "uat.truecorp.co.th",
                        "description": "Backend host — overridden per environment via substitution variables"
                    }
                }
            }
        ],
        "paths": {},
        "components": {
            "schemas": {
                "ErrorResponse": {
                    "type": "object",
                    "description": "Standard TIBCO ESB error response",
                    "properties": {
                        "errorCode":    {"type": "string", "description": "Error code from backend"},
                        "errorMessage": {"type": "string", "description": "Human-readable error message"},
                        "activityId":   {"type": "string", "description": "OMX Activity ID that triggered the call"},
                        "timestamp":    {"type": "string", "format": "date-time"},
                    }
                }
            }
        }
    }

    # Tags (one per system prefix)
    for prefix in sorted(systems.keys()):
        svcs = systems[prefix]
        r = sum(1 for s in svcs if s["type"] == "REST")
        s = sum(1 for s in svcs if s["type"] == "SOAP")
        tag_desc = SYSTEM_DESC.get(prefix, f"{prefix} backend system")
        spec["tags"].append({
            "name": prefix,
            "description": f"{tag_desc} — {len(svcs)} operations ({r} REST, {s} SOAP)"
        })

    # Paths
    for svc in services:
        prefix = svc["name"].split("_")[0]
        path_key = f"/{svc['name']}"
        method   = svc["method"].lower()

        if svc["type"] == "REST":
            operation = _build_rest_op(svc, prefix)
        else:
            operation = _build_soap_op(svc, prefix)
            method    = "post"

        spec["paths"][path_key] = {method: operation}

    return spec


def _build_rest_op(svc, tag):
    ep      = svc.get("endpoint", "")
    ep_var  = svc.get("endpoint_var", "")
    ep_line = f"`{ep}`" if ep else f"*(variable: `{ep_var}`)*"

    desc = [f"**Endpoint**: {ep_line}"]
    if svc.get("auth") and "No Auth" not in svc["auth"]:
        desc.append(f"**Auth**: {svc['auth']}")
    if svc.get("timeout_sec"):
        desc.append(f"**Timeout**: {svc['timeout_sec']} s")
    desc.append(f"**Response format**: {svc.get('response_type','JSON')}")
    desc.append(f"**ESB service**: `{svc['name']}`")

    params = []

    # Query params
    for qp in svc.get("query_params", []):
        params.append({
            "name": qp["name"], "in": "query",
            "schema": qp["schema"]
        })

    # Header params
    for h in svc.get("header_names", []):
        params.append({
            "name": h, "in": "header",
            "schema": {"type": "string"},
            "required": h in ("Authorization",)
        })

    op = {
        "tags":        [tag],
        "summary":     svc["name"].replace("_", " "),
        "operationId": svc["name"],
        "description": "  \n".join(desc),
        "responses":   {},
        "x-endpoint":  ep,
        "x-endpoint-variable": f"%%{ep_var}%%" if ep_var else "",
        "x-tibco-esb-service": svc["name"],
    }
    if params:
        op["parameters"] = params

    # Request body
    if svc["method"] in ("POST", "PUT", "PATCH"):
        ct    = svc.get("content_type", "application/json")
        body  = svc.get("body_schema") or {}
        ff    = svc.get("form_fields", [])

        if not body and ff:
            body = {"type": "object", "properties": {f: {"type": "string"} for f in ff}}

        if not isinstance(body, dict):
            body = {"type": "object"}

        if body and "type" not in body:
            body = {"type": "object", "properties": body}

        op["requestBody"] = {
            "required": True,
            "content":  {ct: {"schema": body}}
        }

    # Responses
    codes = list(dict.fromkeys(svc.get("status_codes") or ["200"]))
    for sc in codes:
        op["responses"][sc] = {
            "description": HTTP_STATUS.get(sc, f"HTTP {sc}"),
            "content": {"application/json": {"schema": {"type": "object"}}}
        }
    if "200" not in op["responses"]:
        op["responses"]["200"] = {"description": "Success"}
    op["responses"]["default"] = {
        "description": "Error",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}
    }

    return op


def _build_soap_op(svc, tag):
    ep     = svc.get("endpoint", "")
    ep_var = svc.get("endpoint_var", "")
    ep_line = f"`{ep}`" if ep else f"*(variable: `{ep_var}`)*"
    op_name = svc.get("operation", svc["name"])

    desc = [
        f"**WSDL**: `{svc.get('wsdl') or 'see _SharedResources/WSDL/'}`",
        f"**Operation**: `{op_name}`",
    ]
    if svc.get("service"):
        desc.append(f"**Service/Port**: `{svc['service']}` / `{svc.get('port','')}`")
    desc.append(f"**Endpoint**: {ep_line}")
    if svc.get("auth") and svc["auth"] != "NONE":
        desc.append(f"**Auth**: {svc['auth']}")
    if svc.get("timeout_sec"):
        desc.append(f"**Timeout**: {svc['timeout_sec']} s")
    desc.append(f"**ESB service**: `{svc['name']}`")

    req_props  = svc.get("request_fields")  or {}
    resp_props = svc.get("response_fields") or {}

    op = {
        "tags":        [tag],
        "summary":     f"{svc['name'].replace('_',' ')} [{op_name}]",
        "operationId": svc["name"],
        "description": "  \n".join(desc),
        "parameters": [
            {
                "name": "SOAPAction", "in": "header",
                "description": f"SOAP action for `{op_name}`",
                "schema": {"type": "string"},
                "required": False
            }
        ],
        "requestBody": {
            "required": True,
            "content": {
                "application/soap+xml": {
                    "schema": {
                        "type": "object",
                        "description": f"SOAP envelope body for operation `{op_name}`",
                        "properties": req_props if req_props else {
                            "soapBody": {"type": "string", "description": "Serialized SOAP body XML"}
                        }
                    }
                }
            }
        },
        "responses": {
            "200": {
                "description": "SOAP Response",
                "content": {
                    "application/soap+xml": {
                        "schema": {
                            "type": "object",
                            "properties": resp_props if resp_props else {
                                "soapBody": {"type": "string", "description": "Serialized SOAP response XML"}
                            }
                        }
                    }
                }
            },
            "500": {
                "description": "SOAP Fault",
                "content": {
                    "application/soap+xml": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                }
            }
        },
        "x-endpoint":  ep,
        "x-endpoint-variable": f"%%{ep_var}%%" if ep_var else "",
        "x-wsdl":      svc.get("wsdl", ""),
        "x-soap-operation": op_name,
        "x-tibco-esb-service": svc["name"],
    }
    return op


# ── Step 8: YAML serializer (no external dependency) ──────────────────────────
def _yaml_val(v, depth=0):
    pad = "  " * depth
    if v is None:          return "null"
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, int):  return str(v)
    if isinstance(v, float):return str(v)
    if isinstance(v, str):
        if not v:           return '""'
        specials = set('\n\r\t:"\'#{}&*?|<>=!%@`[]')
        if (any(c in v for c in specials)
                or v[0] in ('-', ' ')
                or v.lower() in ('true', 'false', 'null', 'yes', 'no', 'on', 'off')
                or re.match(r'^[\d.+-]', v)):
            safe = v.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            return f'"{safe}"'
        return v
    if isinstance(v, list):
        if not v: return "[]"
        parts = []
        for item in v:
            if isinstance(item, dict) and item:
                kv = list(item.items())
                first = f"{pad}- {kv[0][0]}: {_yaml_val(kv[0][1], depth+1)}"
                rest  = [f"{pad}  {k}: {_yaml_val(val, depth+1)}" for k, val in kv[1:]]
                parts.append("\n".join([first] + rest))
            elif isinstance(item, list):
                parts.append(f"{pad}-\n{_yaml_val(item, depth+1)}")
            else:
                parts.append(f"{pad}- {_yaml_val(item, depth)}")
        return "\n".join(parts)
    if isinstance(v, dict):
        if not v: return "{}"
        parts = []
        for k, val in v.items():
            key = f'"{k}"' if any(c in str(k) for c in ':#{}[]') else str(k)
            if isinstance(val, (dict, list)) and val:
                parts.append(f"{pad}{key}:")
                parts.append(_yaml_val(val, depth+1))
            else:
                parts.append(f"{pad}{key}: {_yaml_val(val, depth)}")
        return "\n".join(parts)
    return str(v)


def spec_to_yaml(spec):
    lines = [
        f'openapi: "{spec["openapi"]}"',
        "",
        _yaml_val({"info": spec["info"]}),
        "",
        _yaml_val({"servers": spec["servers"]}),
        "",
        _yaml_val({"tags": spec["tags"]}),
        "",
        "paths:",
    ]
    for path, methods in spec["paths"].items():
        lines.append(f'  "{path}":')
        for method, op in methods.items():
            lines.append(f"    {method}:")
            lines.append(_yaml_val(op, depth=3))
    lines.append("")
    lines.append(_yaml_val({"components": spec["components"]}))
    return "\n".join(lines)


# ── Step 9: Generate Swagger UI HTML ──────────────────────────────────────────
_SWAGGER_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TRUEOMX ESB Non-EJB API Documentation</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css">
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #f0f2f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    .top-bar {
      background: linear-gradient(135deg, #1F3864 0%, #2E75B6 100%);
      color: #fff; padding: 14px 24px;
      display: flex; align-items: center; gap: 12px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    .top-bar h1 { margin: 0; font-size: 17px; font-weight: 600; flex: 1; }
    .badge {
      background: rgba(255,255,255,0.2); padding: 3px 10px;
      border-radius: 12px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
    }
    .badge.rest { background: #00B0F0; color: #fff; }
    .badge.soap { background: #FFC000; color: #1F3864; }
    .info-strip {
      background: #fff; border-bottom: 1px solid #d9e3f0;
      padding: 8px 24px; font-size: 12px; color: #555;
      display: flex; gap: 20px; flex-wrap: wrap;
    }
    .info-strip span strong { color: #1F3864; }
    .offline-warn {
      display: none; background: #fff8e1; border: 1px solid #ffc107;
      padding: 10px 24px; text-align: center; font-size: 13px;
    }
    #swagger-ui { max-width: 1400px; margin: 0 auto; padding: 0 0 40px; }
    .swagger-ui .topbar { display: none; }
    .swagger-ui .info { margin: 20px 0 10px; }
    .swagger-ui .scheme-container { padding: 10px 0; }
  </style>
</head>
<body>
  <div class="top-bar">
    <h1>TRUEOMX ESB &mdash; Non-EJB Outbound Integration API</h1>
    <span class="badge rest">REST __REST_COUNT__</span>
    <span class="badge soap">SOAP __SOAP_COUNT__</span>
    <span class="badge">OpenAPI 3.0</span>
  </div>
  <div class="info-strip">
    <span>Source: <strong>__SOURCE_FOLDER__</strong></span>
    <span>Generated: <strong>__GENERATED_DATE__</strong></span>
    <span>Total services: <strong>__TOTAL_COUNT__</strong></span>
    <span>Endpoints resolved from TIBCO global substitution variables (*.substvar)</span>
  </div>
  <div class="offline-warn" id="offline-warn">
    &#9888; Swagger UI requires internet (CDN). If offline, open
    <code>TRUEOMX_REST_SOAP_API.json</code> at
    <a href="https://editor.swagger.io" target="_blank">editor.swagger.io</a>.
  </div>
  <div id="swagger-ui"></div>

  <script>
    window.addEventListener('error', function(e) {
      if (e.target && (e.target.tagName === 'LINK' || e.target.tagName === 'SCRIPT')) {
        document.getElementById('offline-warn').style.display = 'block';
      }
    }, true);
  </script>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js" crossorigin></script>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js" crossorigin></script>
  <script>
    window.onload = function() {
      const spec = __SPEC_JSON__;
      SwaggerUIBundle({
        spec: spec,
        dom_id: '#swagger-ui',
        deepLinking: true,
        filter: true,
        showExtensions: true,
        showCommonExtensions: true,
        tryItOutEnabled: false,
        displayRequestDuration: true,
        defaultModelsExpandDepth: 1,
        defaultModelExpandDepth: 2,
        docExpansion: 'list',
        syntaxHighlight: { activated: true, theme: 'nord' },
        presets: [ SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset ],
        plugins: [ SwaggerUIBundle.plugins.DownloadUrl ],
        layout: "StandaloneLayout"
      });
    };
  </script>
</body>
</html>"""


def generate_swagger_html(spec, services, source_folder):
    rest_n  = sum(1 for s in services if s["type"] == "REST")
    soap_n  = sum(1 for s in services if s["type"] == "SOAP")
    spec_js = json.dumps(spec, ensure_ascii=False)

    html = _SWAGGER_HTML_TEMPLATE
    html = html.replace("__REST_COUNT__",    str(rest_n))
    html = html.replace("__SOAP_COUNT__",    str(soap_n))
    html = html.replace("__SOURCE_FOLDER__", source_folder)
    html = html.replace("__GENERATED_DATE__",date.today().isoformat())
    html = html.replace("__TOTAL_COUNT__",   str(len(services)))
    html = html.replace("__SPEC_JSON__",     spec_js)
    return html


# ── Step 10: Generate static offline HTML report ──────────────────────────────
_ROW_COLORS = {
    "REST":  "#e8f7ff",
    "SOAP":  "#fff8e1",
}

def generate_static_html(services, source_folder):
    rest_n = sum(1 for s in services if s["type"] == "REST")
    soap_n = sum(1 for s in services if s["type"] == "SOAP")

    rows = []
    for svc in services:
        ep   = svc.get("endpoint", "")
        evar = svc.get("endpoint_var", "")
        ep_display = ep if ep else f"%%{evar}%%"

        if svc["type"] == "REST":
            method = svc.get("method", "POST")
            detail = svc.get("content_type", "application/json")
            proto  = "REST"
        else:
            method = "SOAP"
            detail = svc.get("operation", "")
            proto  = "SOAP"

        wsdl    = svc.get("wsdl", "")
        timeout = svc.get("timeout_sec", "")
        auth    = svc.get("auth", "")
        status  = ", ".join(svc.get("status_codes", []))

        bg = _ROW_COLORS.get(proto, "#fff")
        rows.append(f"""
        <tr style="background:{bg}">
          <td><strong>{svc['name']}</strong></td>
          <td><span class="tag tag-{proto.lower()}">{proto}</span></td>
          <td><span class="method">{method}</span></td>
          <td class="ep">{ep_display}</td>
          <td>{detail}</td>
          <td>{wsdl}</td>
          <td>{timeout}</td>
          <td>{auth}</td>
          <td>{status}</td>
        </tr>""")

    rows_html = "\n".join(rows)

    systems_stats = defaultdict(lambda: {"rest": 0, "soap": 0})
    for svc in services:
        prefix = svc["name"].split("_")[0]
        systems_stats[prefix][svc["type"].lower()] += 1

    stat_rows = []
    for prefix in sorted(systems_stats.keys()):
        s = systems_stats[prefix]
        total = s["rest"] + s["soap"]
        desc = SYSTEM_DESC.get(prefix, prefix)
        stat_rows.append(f"""
        <tr>
          <td><strong>{prefix}</strong></td>
          <td>{desc}</td>
          <td>{s['rest']}</td>
          <td>{s['soap']}</td>
          <td>{total}</td>
        </tr>""")
    stat_rows_html = "\n".join(stat_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>TRUEOMX REST/SOAP API — Static Report</title>
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #f5f7fa; color: #222; }}
    .header {{ background: linear-gradient(135deg,#1F3864,#2E75B6); color:#fff; padding:18px 30px; }}
    .header h1 {{ margin:0; font-size:20px; }}
    .header p  {{ margin:4px 0 0; font-size:13px; opacity:.85; }}
    .meta {{ background:#fff; border-bottom:1px solid #ddd; padding:8px 30px; font-size:12px; color:#555; display:flex; gap:20px; }}
    .section {{ margin:20px 30px; }}
    h2 {{ font-size:15px; color:#1F3864; border-bottom:2px solid #2E75B6; padding-bottom:6px; }}
    .summary-grid {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }}
    .card {{ background:#fff; border-radius:8px; padding:16px 24px; box-shadow:0 1px 4px rgba(0,0,0,.1);
             min-width:120px; text-align:center; }}
    .card .num {{ font-size:28px; font-weight:700; color:#1F3864; }}
    .card .lbl {{ font-size:11px; color:#888; margin-top:2px; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; background:#fff;
             border-radius:8px; overflow:hidden; box-shadow:0 1px 4px rgba(0,0,0,.1); }}
    th {{ background:#1F3864; color:#fff; padding:9px 10px; text-align:left; font-size:11px; }}
    td {{ padding:7px 10px; border-bottom:1px solid #eee; vertical-align:top; }}
    tr:hover td {{ background:#f0f7ff; }}
    .tag {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:600; }}
    .tag-rest {{ background:#00B0F0; color:#fff; }}
    .tag-soap {{ background:#FFC000; color:#1F3864; }}
    .method {{ display:inline-block; padding:2px 7px; border-radius:4px; font-size:10px;
               font-weight:700; background:#375623; color:#fff; font-family:monospace; }}
    .ep {{ font-family:monospace; font-size:11px; word-break:break-all; color:#1a5276; }}
    footer {{ text-align:center; padding:20px; font-size:11px; color:#aaa; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>TRUEOMX ESB &mdash; Non-EJB Outbound Integration API</h1>
    <p>REST and SOAP backend service specifications | Static offline report</p>
  </div>
  <div class="meta">
    <span>Source: <strong>{source_folder}</strong></span>
    <span>Generated: <strong>{date.today().isoformat()}</strong></span>
    <span>Scope: REST + SOAP only (EJB / JMS excluded)</span>
  </div>

  <div class="section">
    <h2>Summary</h2>
    <div class="summary-grid">
      <div class="card"><div class="num">{len(services)}</div><div class="lbl">Total Services</div></div>
      <div class="card"><div class="num" style="color:#0070C0">{rest_n}</div><div class="lbl">REST</div></div>
      <div class="card"><div class="num" style="color:#BF8C00">{soap_n}</div><div class="lbl">SOAP</div></div>
    </div>

    <h2>Services by Backend System</h2>
    <table>
      <thead><tr>
        <th>System</th><th>Description</th><th>REST</th><th>SOAP</th><th>Total</th>
      </tr></thead>
      <tbody>{stat_rows_html}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>All Services ({len(services)})</h2>
    <table>
      <thead><tr>
        <th>Service Name</th><th>Type</th><th>Method</th>
        <th>Endpoint / Variable</th><th>Content-Type / Operation</th>
        <th>WSDL</th><th>Timeout</th><th>Auth</th><th>Status Codes</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  <footer>Generated by TRUEOMX AI Discovery | scripts/generate_swagger_spec.py</footer>
</body>
</html>"""


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    source_folder = os.path.basename(BASE)

    print("Step 1: Loading TIBCO global substitution variables ...")
    gvars = load_global_vars(VARS_DIR)
    print(f"  Loaded {len(gvars)} substitution variables")

    print("\nStep 2: Parsing ESB services (REST + SOAP only) ...")
    services = parse_all_services(ESB_DIR, gvars)
    if not services:
        print("  No REST/SOAP services found — check ESB_DIR path")
        return

    print("\nStep 3: Building OpenAPI 3.0 specification ...")
    spec = build_openapi_spec(services, source_folder)
    print(f"  {len(spec['paths'])} paths | {len(spec['tags'])} tags")

    print("\nStep 4: Saving outputs ...")

    # JSON
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    size_json = os.path.getsize(OUT_JSON) / 1024
    print(f"  JSON: {OUT_JSON}  ({size_json:.0f} KB)")

    # YAML
    try:
        import yaml as _yaml
        class _Dumper(_yaml.Dumper):
            pass
        _Dumper.add_representer(
            str,
            lambda d, s: d.represent_scalar('tag:yaml.org,2002:str', s,
                                             style='|' if '\n' in s else None)
        )
        yaml_str = _yaml.dump(spec, Dumper=_Dumper, default_flow_style=False,
                               allow_unicode=True, sort_keys=False, width=120)
    except ImportError:
        yaml_str = spec_to_yaml(spec)

    with open(OUT_YAML, "w", encoding="utf-8") as f:
        f.write(yaml_str)
    size_yaml = os.path.getsize(OUT_YAML) / 1024
    print(f"  YAML: {OUT_YAML}  ({size_yaml:.0f} KB)")

    # Swagger UI HTML
    html_swagger = generate_swagger_html(spec, services, source_folder)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_swagger)
    size_html = os.path.getsize(OUT_HTML) / 1024
    print(f"  HTML (Swagger UI): {OUT_HTML}  ({size_html:.0f} KB)")

    # Static offline HTML
    html_static = generate_static_html(services, source_folder)
    with open(OUT_HTML_STATIC, "w", encoding="utf-8") as f:
        f.write(html_static)
    size_static = os.path.getsize(OUT_HTML_STATIC) / 1024
    print(f"  HTML (Static):     {OUT_HTML_STATIC}  ({size_static:.0f} KB)")

    # Endpoint resolution stats
    resolved   = sum(1 for s in services if s.get("endpoint"))
    unresolved = len(services) - resolved
    print(f"\nEndpoint resolution: {resolved} resolved | {unresolved} still use variable placeholder")

    # Sample output
    print("\nSample services:")
    for svc in services[:5]:
        ep = svc.get("endpoint") or f"%%{svc.get('endpoint_var','?')}%%"
        t  = svc["type"]
        m  = svc.get("method","POST") if t == "REST" else svc.get("operation","")
        print(f"  [{t:4}] {svc['name']:40s} {m:6}  {ep[:60]}")

    print("\nDone.")


if __name__ == "__main__":
    main()
