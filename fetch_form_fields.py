import urllib.request, re, sys

url = "https://docs.google.com/forms/d/e/1FAIpQLSedV4ca8NSItkayTczjXGSQDETcUDpt4u936FxE9ul1rsVl4g/viewform"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
except Exception as e:
    print("FETCH ERROR:", e)
    sys.exit(1)

# Extract all unique entry IDs
entries = list(dict.fromkeys(re.findall(r"entry\.(\d+)", html)))
print("entry IDs found:", entries)

# Try FB_PUBLIC_LOAD_DATA_ block
m = re.search(r"FB_PUBLIC_LOAD_DATA_\s*=\s*(\[.+?(?=;\s*(?:var |</script>)))", html, re.DOTALL)
if m:
    print("\nRaw data slice (first 3000 chars):")
    print(m.group(1)[:3000])
else:
    # Grab context around each entry ID
    for eid in entries:
        idx = html.find("entry." + eid)
        print(f"\nentry.{eid} context:\n  {html[max(0,idx-120):idx+60]}")
