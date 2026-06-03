import io
import os
import zipfile
import csv
import requests
import traceback
import sys

# High limit patch to handle large property descriptions securely
csv.field_size_limit(2147483647)

FEED_URL = "https://marketingfeeds.propertyfinder.net/eg/en/export/google/full/b5543c8e7a4bfc2ff66636569c135c73473535d37788cf024e2987035b3df4267c3a1f7330ea7d1dcb90f677be73e50de26776e7039b21db4715c1a0d03e8aef"

# ── OUTPUT FILES ─────────────────────────────────────────────────────────────
# File 1: Custom Dynamic Feed  → used by DSA / standard display campaigns
# File 2: Page Feed            → used by Performance Max campaigns
# Both are written in a single pass — no double download, no double processing.
# ─────────────────────────────────────────────────────────────────────────────
OUTPUT_CUSTOM_FEED = "clean_display_feed.csv"
OUTPUT_PAGE_FEED   = "pmax_page_feed.csv"

# Page feed custom label applied to every matched row.
# In your PMax campaign → Asset group → URL rules, target: custom_label = "diamond-sale-eg"
PAGE_FEED_LABEL = "diamond-sale-eg"

def main():
    try:
        print("Downloading compressed data package from Property Finder...")
        response = requests.get(FEED_URL, stream=True, timeout=90)
        if response.status_code != 200:
            print(f"CRITICAL: Download failed with status code {response.status_code}")
            sys.exit(1)

        print("Opening ZIP archive structure...")
        try:
            zip_file = zipfile.ZipFile(io.BytesIO(response.content))
            internal_filename = zip_file.namelist()[0]
        except zipfile.BadZipFile:
            print("CRITICAL ERROR: File downloaded is not a valid ZIP archive.")
            sys.exit(1)

        print(f"Processing data stream for: {internal_filename}")
        with zip_file.open(internal_filename, 'r') as f:
            # utf-8-sig on INPUT strips BOM from the source feed
            text_stream = io.TextIOWrapper(f, encoding='utf-8-sig', errors='ignore')

            header_line = text_stream.readline()
            if not header_line:
                print("CRITICAL ERROR: Feed file appears to be completely empty.")
                sys.exit(1)

            tab_count   = header_line.count('\t')
            comma_count = header_line.count(',')
            delimiter   = '\t' if tab_count > comma_count else ','
            delim_name  = 'TAB' if delimiter == '\t' else 'COMMA'
            print(f"Format delimiter detected: {delim_name}")

            header_reader = csv.reader([header_line], delimiter=delimiter)
            raw_headers   = next(header_reader)
            headers       = [str(h).strip().lower() for h in raw_headers]
            print(f"SUCCESS: Found {len(headers)} columns in master feed.")
            print(f"First 10 headers: {headers[:10]}")

            # ── FILTER COLUMN INDICES ─────────────────────────────────────────
            segment_idx = headers.index('client_segment') if 'client_segment' in headers else next((i for i, h in enumerate(headers) if 'segment' in h), None)
            depth_idx   = headers.index('listings_depth') if 'listings_depth' in headers else next((i for i, h in enumerate(headers) if 'depth' in h), None)
            type_idx    = headers.index('listing_type')   if 'listing_type'   in headers else next((i for i, h in enumerate(headers) if 'type' in h and 'property' not in h), None)

            if segment_idx is None or depth_idx is None or type_idx is None:
                print("CRITICAL LAYOUT ERROR: Missing matching filter columns.")
                print(f"  segment_idx={segment_idx}, depth_idx={depth_idx}, type_idx={type_idx}")
                sys.exit(1)

            # ── OUTPUT COLUMN INDICES ─────────────────────────────────────────
            id_idx    = headers.index('id')    if 'id'    in headers else 0
            title_idx = headers.index('title') if 'title' in headers else 1
            link_idx  = headers.index('link')  if 'link'  in headers else 2
            img_idx   = next((i for i, h in enumerate(headers) if 'image_link' in h or ('image' in h and 'additional' not in h)), 3)
            desc_idx  = next((i for i, h in enumerate(headers) if 'description' in h or 'desc' in h), 4)
            price_idx = next((i for i, h in enumerate(headers) if h == 'price' or ('price' in h and 'period' not in h and 'change' not in h)), 5)

            max_needed_idx = max(segment_idx, depth_idx, type_idx, id_idx, title_idx, link_idx, img_idx, desc_idx, price_idx)

            matched_count = 0
            lines_scanned = 0

            reader = csv.reader(text_stream, delimiter=delimiter)

            # ── OPEN BOTH OUTPUT FILES SIMULTANEOUSLY ─────────────────────────
            # Single loop pass writes to both files — feed is only downloaded once.
            # Both files use plain utf-8 (NO BOM) to prevent Google Ads header errors.
            # ─────────────────────────────────────────────────────────────────────
            with open(OUTPUT_CUSTOM_FEED, 'w', newline='', encoding='utf-8') as custom_file, \
                 open(OUTPUT_PAGE_FEED,   'w', newline='', encoding='utf-8') as page_file:

                custom_writer = csv.writer(custom_file, quoting=csv.QUOTE_MINIMAL)
                page_writer   = csv.writer(page_file,   quoting=csv.QUOTE_MINIMAL)

                # Custom feed headers (DSA / Display)
                custom_writer.writerow(["ID", "Item title", "Final URL", "Image URL", "Item description", "Price"])

                # Page feed headers (PMax) — Google Ads requires exactly these two column names
                page_writer.writerow(["Page URL", "Custom label"])

                for row in reader:
                    lines_scanned += 1
                    if not row or len(row) <= max_needed_idx:
                        continue

                    segment = row[segment_idx].strip().lower()
                    depth   = row[depth_idx].strip().lower()
                    l_type  = row[type_idx].strip().lower()

                    # FILTER: Diamond + (Premium OR Featured) + Sale only
                    if segment == 'diamond' and (depth == 'premium' or depth == 'featured') and 'sale' in l_type:

                        p_id  = row[id_idx].strip()
                        link  = row[link_idx].strip()
                        img   = row[img_idx].strip()

                        # Skip rows missing critical fields — avoids Google Ads validation errors
                        if not p_id or not link or not img:
                            continue

                        matched_count += 1

                        # ── Write to Custom Feed (DSA / Display) ──────────────
                        title = row[title_idx].strip()
                        desc  = row[desc_idx].strip().replace('\n', ' ').replace('\r', ' ')[:145]
                        price = row[price_idx].strip()
                        clean_price = "".join([c for c in price if c.isdigit() or c == '.'])
                        custom_writer.writerow([p_id, title, link, img, desc, clean_price])

                        # ── Write to Page Feed (PMax) ─────────────────────────
                        # Page feed only needs the URL + label. Same filter = same URLs.
                        # Label lets you target this exact subset in your PMax asset group.
                        page_writer.writerow([link, PAGE_FEED_LABEL])

        print(f"\n OUTPUT VALIDATION SUMMARY")
        print(f"  Total listings scanned       : {lines_scanned:,}")
        print(f"  Total matched rows           : {matched_count:,}")
        print(f"  Custom feed (DSA/Display)    : {OUTPUT_CUSTOM_FEED}")
        print(f"  Page feed (PMax)             : {OUTPUT_PAGE_FEED}")
        print(f"  Page feed label applied      : '{PAGE_FEED_LABEL}'")

        if matched_count == 0:
            print("\n  WARNING: Zero rows matched. Check filter criteria against live feed values.")
            sys.exit(1)

    except Exception as e:
        print("\n--- CRASH DIAGNOSTIC LOG ---")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
