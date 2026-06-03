import io
import os
import zipfile
import csv
import requests
import traceback
import sys

# Crucial fix for massive feeds: Tells Python to allow giant text fields without crashing
csv.field_size_limit(2147483647)

FEED_URL = "https://marketingfeeds.propertyfinder.net/eg/en/export/google/full/b5543c8e7a4bfc2ff66636569c135c73473535d37788cf024e2987035b3df4267c3a1f7330ea7d1dcb90f677be73e50de26776e7039b21db4715c1a0d03e8aef"
OUTPUT_FILE = "clean_display_feed.csv"

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
        
        print(f"Processing sequential data stream for: {internal_filename}")
        with zip_file.open(internal_filename, 'r') as f:
            # utf-8-sig strips any hidden Byte Order Marks
            text_stream = io.TextIOWrapper(f, encoding='utf-8-sig', errors='ignore')
            
            # STREAM-SAFE FIX: Read the header line directly without using .seek(0)
            header_line = text_stream.readline()
            if not header_line:
                print("CRITICAL ERROR: Feed file appears to be completely empty.")
                sys.exit(1)
                
            # Identify layout splitting structure via character counts
            tab_count = header_line.count('\t')
            comma_count = header_line.count(',')
            delimiter = '\t' if tab_count > comma_count else ','
            delim_name = 'TAB' if delimiter == '\t' else 'COMMA'
            print(f"Format delimiter detected: {delim_name}")
            
            # Parse the header list safely from that standalone string
            header_reader = csv.reader([header_line], delimiter=delimiter)
            raw_headers = next(header_reader)
            headers = [str(h).strip().lower() for h in raw_headers]
            
            print(f"SUCCESS: Read {len(headers)} columns from feed header.")
            
            # Explicit lookups matched directly to your master feed layout columns
            segment_idx = headers.index('client_segment') if 'client_segment' in headers else next((i for i, h in enumerate(headers) if 'segment' in h), None)
            depth_idx = headers.index('listings_depth') if 'listings_depth' in headers else next((i for i, h in enumerate(headers) if 'depth' in h), None)
            type_idx = headers.index('listing_type') if 'listing_type' in headers else next((i for i, h in enumerate(headers) if 'type' in h and 'property' not in h), None)
            
            if segment_idx is None or depth_idx is None or type_idx is None:
                print(f"CRITICAL LAYOUT ERROR: Missing filter columns. Headers found: {headers}")
                sys.exit(1)

            # Target standard output schema for Google Ads Catalog
            ads_headers = ["id", "title", "link", "image_link", "description", "price"]
            
            id_idx = headers.index('id') if 'id' in headers else 0
            title_idx = headers.index('title') if 'title' in headers else 1
            link_idx = headers.index('link') if 'link' in headers else 2
            img_idx = headers.index('image_link') if 'image_link' in headers else next((i for i, h in enumerate(headers) if 'image' in h and 'additional' not in h), 3)
            desc_idx = headers.index('description') if 'description' in headers else next((i for i, h in enumerate(headers) if 'desc' in h), 4)
            price_idx = headers.index('price') if 'price' in headers else next((i for i, h in enumerate(headers) if h == 'price' or ('price' in h and 'period' not in h and 'change' not in h)), 5)

            max_needed_idx = max(segment_idx, depth_idx, type_idx, id_idx, title_idx, link_idx, img_idx, desc_idx, price_idx)
            
            matched_count = 0
            lines_scanned = 0
            
            # QUOTE_NONE prevents unescaped measurement text strings (e.g. 24" tiles) from breaking line splits
            reader = csv.reader(text_stream, delimiter=delimiter, quoting=csv.QUOTE_NONE)
            
            with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.writer(outfile)
                writer.writerow(ads_headers)
                
                for row in reader:
                    lines_scanned += 1
                    if not row or len(row) <= max_needed_idx:
                        continue
                        
                    segment = row[segment_idx].strip().lower()
                    depth = row[depth_idx].strip().lower()
                    l_type = row[type_idx].strip().lower()
                    
                    # Core target match parameters: Diamond + (Premium OR Featured) + Buy (Sale)
                    if (segment == 'diamond' or segment == 'sapphire') and (depth == 'premium' or depth == 'featured' or depth == 'standard') and 'sale' in l_type:
                        matched_count += 1
                        p_id = row[id_idx].replace('"', '')
                        title = row[title_idx].replace('"', '')
                        link = row[link_idx]
                        img = row[img_idx]
                        desc = row[desc_idx].replace('"', '')[:145] 
                        price = row[price_idx]
                        
                        if price and "egp" not in price.lower():
                            price = f"{price} EGP"
                            
                        writer.writerow([p_id, title, link, img, desc, price])
                        
        print(f"Success! Scanned {lines_scanned} listings. Saved {matched_count} Buy properties.")

    except Exception as e:
        print("\n--- CRASH DIAGNOSTIC LOG ---")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
