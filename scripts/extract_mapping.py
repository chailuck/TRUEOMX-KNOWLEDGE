"""
Extract the authoritative ActivityID -> FM JMS queue mapping from:
1. OMX-OM/Channels/OMXFMConnectionRequest.channel  (event name -> FM queue)
2. OMX-OM/Rules/OMConsumers/OMXFM/Request/*.rule   (ActivityID -> event name)
3. OMX-OM/Channels/OMXFMConnectionResponse.channel (FM response queue mapping)

Then rebuild the full integration chain with correct FM service links.
"""

import os, re, json, sys

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

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

BASE     = _resolve_base()
OM_DIR   = os.path.join(BASE, "OMX-OM")
OUT_JSON = os.path.join(_SCRIPT_DIR, "activity_fm_mapping.json")


# ── Step 1: Parse OMXFMConnectionRequest.channel ─────────────────────────────
# Structure: <destinations name="EVENT_NAME" ...>
#              <properties name="Name" value="...FM/QUEUE_SUFFIX.Req%%"/>
def parse_fm_channel(channel_path):
    """Return dict: event_name -> fm_queue_suffix (e.g. 'ActivateSubscriber')"""
    mapping = {}
    try:
        content = open(channel_path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return mapping

    # Split on <destinations  to get individual destination blocks
    blocks = re.split(r'<destinations\s', content)
    for block in blocks[1:]:  # skip first (before first <destinations)
        # Get destination name (the Event name)
        name_m = re.search(r'name="([^"]+)"', block)
        if not name_m:
            continue
        evt_name = name_m.group(1)

        # Get the JMS Queue value
        queue_m = re.search(r'name="Name"\s+value="([^"]+)"', block)
        if not queue_m:
            continue
        full_queue = queue_m.group(1)

        # Extract FM destination suffix: .../FM/SuffixName.Req%%
        fm_m = re.search(r'Destinations/FM/([^.%]+)', full_queue)
        if fm_m:
            mapping[evt_name] = fm_m.group(1)

    return mapping


# ── Step 2: Parse Request_*.rule files ───────────────────────────────────────
# Each rule file encodes: ActivityID -> what Event type it sends
# The event type name = destination name in channel = key in event->FM mapping
def parse_request_rules(rules_dir):
    """
    Return dict: activity_id -> {
        'rule_file': str,
        'event_name': str,       # Events.OMConsumers.OMXFM.Request.<NAME>
        'request_schema': str,   # XSD namespace from XSLT
        'payload_root': str,     # Root element of payload
    }
    """
    result = {}
    req_dir = os.path.join(rules_dir, "OMConsumers", "OMXFM", "Request")
    if not os.path.isdir(req_dir):
        return result

    for fname in sorted(os.listdir(req_dir)):
        if not fname.endswith(".rule"):
            continue
        fpath = os.path.join(req_dir, fname)
        try:
            content = open(fpath, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue

        # Extract ActivityID from when clause
        aid_m = re.search(r'orderCurrentActivity\.ActivityID\s*==\s*"([^"]+)"', content)
        if not aid_m:
            # fallback: derive from filename
            aid = fname.replace("Request_", "").replace(".rule", "")
        else:
            aid = aid_m.group(1)

        # Extract event type from: Events.OMConsumers.OMXFM.Request.<NAME> reqEvent = Event.createEvent
        event_m = re.search(r'Events\.OMConsumers\.OMXFM\.Request\.([A-Za-z0-9_]+)\s+reqEvent', content)
        if not event_m:
            # try alternate pattern: Event.createEvent("xslt://{{/Events/OMConsumers/OMXFM/Request/NAME}}
            event_m = re.search(r'Events/OMConsumers/OMXFM/Request/([A-Za-z0-9_]+)}', content)
        event_name = event_m.group(1) if event_m else aid

        # Extract XSD schema namespace from XSLT inside the rule (ns1:xxx or ns:xxx in payload)
        payload_m = re.search(r'<xsl:if test="\$[^/]+//[^"]+">.*?<payload>.*?<([^:>]+):([A-Za-z]+)Request',
                               content, re.DOTALL)
        payload_root = ""
        if payload_m:
            payload_root = payload_m.group(1) + ":" + payload_m.group(2) + "Request"
        else:
            # simpler: find <ns:XXXRequest or <ns1:XXXRequest
            pr_m = re.search(r'<(ns\d*:[A-Za-z]+(?:Request|Response))', content)
            if pr_m:
                payload_root = pr_m.group(1)

        result[aid] = {
            "rule_file":    fname,
            "event_name":   event_name,
            "payload_root": payload_root,
        }

    return result


# ── Step 3: Also parse OMXFMConnectionResponse.channel ──────────────────────
def parse_response_channel(channel_path):
    """Return dict: event_name -> fm_response_queue_suffix"""
    mapping = {}
    try:
        content = open(channel_path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return mapping

    blocks = re.split(r'<destinations\s', content)
    for block in blocks[1:]:
        name_m = re.search(r'name="([^"]+)"', block)
        if not name_m:
            continue
        evt_name = name_m.group(1)
        queue_m = re.search(r'name="Name"\s+value="([^"]+)"', block)
        if not queue_m:
            continue
        full_queue = queue_m.group(1)
        fm_m = re.search(r'Destinations/(?:FM|OM)/([^.%]+)', full_queue)
        if fm_m:
            mapping[evt_name] = fm_m.group(1)
    return mapping


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    req_channel  = os.path.join(OM_DIR, "Channels", "OMXFMConnectionRequest.channel")
    resp_channel = os.path.join(OM_DIR, "Channels", "OMXFMConnectionResponse.channel")
    rules_dir    = os.path.join(OM_DIR, "Rules")

    print("Parsing FM request channel ...")
    event_to_fm = parse_fm_channel(req_channel)
    print(f"  -> {len(event_to_fm)} event->FM queue mappings")

    print("Parsing response channel ...")
    resp_mapping = parse_response_channel(resp_channel)
    print(f"  -> {len(resp_mapping)} response queue mappings")

    print("Parsing BE rule files ...")
    activity_rules = parse_request_rules(rules_dir)
    print(f"  -> {len(activity_rules)} activity rule mappings")

    # Combine: ActivityID -> FM queue suffix -> FM service info
    combined = {}
    for aid, rule_data in sorted(activity_rules.items()):
        evt_name  = rule_data["event_name"]
        fm_queue  = event_to_fm.get(evt_name, "")

        # If event_name not in channel, try with _SUBS -> Subscriber substitution
        if not fm_queue:
            # try alternate: the event name and destination name may differ
            # search by partial match on the activity_id
            for ch_evt, ch_fm in event_to_fm.items():
                if ch_evt == evt_name or ch_evt.replace("_","") == evt_name.replace("_",""):
                    fm_queue = ch_fm
                    break

        combined[aid] = {
            "rule_file":    rule_data["rule_file"],
            "event_name":   evt_name,
            "fm_queue":     fm_queue,                # e.g. "GetSubscriberHeader"
            "payload_root": rule_data["payload_root"],
            "req_queue":    f"...FM/{fm_queue}.Req" if fm_queue else "",
            "resp_queue":   f"...OM/{resp_mapping.get(evt_name,'')}.Res" if resp_mapping.get(evt_name) else "",
        }

    # Show summary
    matched   = sum(1 for v in combined.values() if v["fm_queue"])
    unmatched = sum(1 for v in combined.values() if not v["fm_queue"])
    print(f"\nSummary:")
    print(f"  Total activity rules: {len(combined)}")
    print(f"  Matched to FM queue:  {matched}")
    print(f"  Unmatched:            {unmatched}")

    # Show samples
    print("\nSamples (first 20):")
    for aid, data in list(combined.items())[:20]:
        print(f"  {aid:45s} -> FM queue: {data['fm_queue']:35s} event: {data['event_name']}")

    # Show unmatched
    print("\nUnmatched (no FM queue found):")
    for aid, data in combined.items():
        if not data["fm_queue"]:
            print(f"  {aid:45s} event: {data['event_name']}")

    # Save JSON for use in Excel generator
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)
    print(f"\nSaved mapping to {OUT_JSON}")

    return combined


if __name__ == "__main__":
    main()
