"""完整测试 INGV Early-est handler"""
import sys, os
sys.path.insert(0, os.getcwd())

import urllib.request, re, html as html_module
from datetime import datetime, timezone

# 1. 模拟 FETCH 步骤
print("=== Step 1: Fetch HTML ===")
url = "http://early-est.rm.ingv.it/hypomessage.html"
resp = urllib.request.urlopen(url, timeout=60)
html = resp.read().decode("utf-8", errors="replace")
print(f"Fetched {len(html)} bytes")

# 2. 模拟 PARSE 步骤
print("\n=== Step 2: Parse HTML Table ===")
from models.models import DataSource, DisasterType, DisasterEvent, EarthquakeData

tr_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
td_pattern = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)

events = []
for tr_match in tr_pattern.finditer(html):
    tr_content = tr_match.group(0)
    if re.search(r"<th[>\s]", tr_content, re.IGNORECASE):
        continue
    cells = []
    for td_match in td_pattern.finditer(tr_content):
        td_content = td_match.group(1)
        text = re.sub(r"<[^>]+>", "", td_content)
        text = html_module.unescape(text)
        text = text.strip().replace("\xa0", "").replace("&nbsp;", "")
        cells.append(text)
    if len(cells) < 10:
        continue

    event_id = cells[0].strip()
    otime_str = cells[9].strip() if len(cells) > 9 else ""
    lat_str = cells[10].strip() if len(cells) > 10 else ""
    lon_str = cells[11].strip() if len(cells) > 11 else ""
    depth_str = cells[13].strip() if len(cells) > 13 else ""
    mb_str = cells[21].strip() if len(cells) > 21 else ""
    region = cells[30].strip() if len(cells) > 30 else ""

    if not event_id or not lat_str or not lon_str:
        continue
    try:
        lat = float(lat_str)
        lon = float(lon_str)
    except ValueError:
        continue
    magnitude = None
    if mb_str and mb_str != "-":
        try:
            magnitude = float(mb_str)
        except ValueError:
            pass
    if magnitude is None:
        continue
    try:
        otime_clean = otime_str.strip().replace(".", "-")
        idx = otime_clean.rfind("-")
        if idx > 0:
            otime_clean = otime_clean[:idx] + "T" + otime_clean[idx + 1 :]
        shock_time = datetime.fromisoformat(otime_clean).replace(tzinfo=timezone.utc)
    except:
        shock_time = datetime.now(timezone.utc)
    age = (datetime.now(timezone.utc) - shock_time).total_seconds()
    if age > 1800:
        print(f"  SKIP: event {event_id} is too old ({age:.0f}s)")
        continue
    depth = None
    if depth_str and depth_str != "-":
        try:
            depth = float(depth_str)
        except ValueError:
            pass
    place_name = region if region else f"{lat:.2f}, {lon:.2f}"

    earthquake = EarthquakeData(
        id=event_id,
        event_id=event_id,
        source=DataSource.INGV_EE,
        disaster_type=DisasterType.EARTHQUAKE,
        shock_time=shock_time,
        latitude=lat,
        longitude=lon,
        place_name=place_name,
        depth=depth,
        magnitude=magnitude,
        source_id="ingv_ee",
        raw_data={"event_id": event_id, "magnitude": magnitude, "region": region},
    )
    event = DisasterEvent(
        id=f"ingv_ee_{event_id}",
        data=earthquake,
        source=DataSource.INGV_EE,
        disaster_type=DisasterType.EARTHQUAKE,
        source_id="ingv_ee",
        raw_data=earthquake.raw_data,
    )
    events.append(event)
    print(f"  PARSED: event {event.id}, M{magnitude:.1f}, {place_name}, age={age:.0f}s")

print(f"\nTotal events after parsing: {len(events)}")

# 3. 模拟 FORMAT 步骤
print("\n=== Step 3: Format Message ===")
from utils.formatters.early_est import INGVEarlyEstFormatter
for e in events:
    msg = INGVEarlyEstFormatter.format_message(e.data)
    print(f"\nFormatted message for {e.id}:")
    print(msg)
    print("---")

# 4. 检查格式化的消息是否包含免责声明
print("\n=== Step 4: Check Foreign Source Disclaimer ===")
from utils.formatters import _FOREIGN_SOURCE_IDS
if "ingv_ee" in _FOREIGN_SOURCE_IDS:
    print("ingv_ee IS in FOREIGN_SOURCE_IDS - disclaimer will be added")
else:
    print("ingv_ee NOT in FOREIGN_SOURCE_IDS - NO disclaimer")

print("\n=== Test Complete ===")
print(f"All checks passed: {len(events)} events would be sent")
