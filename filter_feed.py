import io
import os
import zipfile
import csv
import requests
import traceback
import sys

FEED_URL = "https://marketingfeeds.propertyfinder.net/eg/en/export/google/full/b5543c8e7a4bfc2ff66636569c135c73473535d37788cf024e2987035b3df4267c3a1f7330ea7d1dcb90f677be73e50de26776e7039b21db4715c1a0d03e8aef"
OUTPUT_FILE = "clean_display_feed.csv"

def main():
    try:
        print("Downloading compressed data package...")
        response = requests.get(FEED_URL, stream=True, timeout=60)
        if response.status_code != 200:
            print(f"CRITICAL: Download failed with status code {response.status_code}")
            sys.exit(1)
            
        print("Reading ZIP archive structure...")
        try:
            zip_file = zipfile.ZipFile(io.BytesIO(response.content))
            internal_filename = zip_file.namelist()[0]
        except zipfile.BadZipFile:
            print("CRITICAL ERROR: The downloaded file is not a valid ZIP file.")
            sys.exit(1)
        
        print(f"Opening internal data stream for: {internal_filename}")
        with zip_file.open(internal_filename, 'r') as f:
            # utf-8-sig automatically handles and strips any hidden Byte Order Marks (BOM)
            text_stream = io.TextIOWrapper(f, encoding='utf-8-sig', errors='ignore')
            header_line = text_stream.readline()
            text_stream.seek(0)
            
            # Smart delimiter selection based on statistical character counts
            tab_count = header_line.count('\t')
            comma_count = header_line.count(',')
            delimiter = '\t' if tab_count > comma_count else ','
            print(f"Detected delimiter: {'TAB' if delimiter == '\t' else 'COMMA'} (Tabs: {tab_count}, Commas: {comma_count})")
            
            reader = csv.reader(text_stream, delimiter=delimiter)
            raw_headers = next(reader)
            headers = [str(h).strip().lower() for h in raw_headers]
            
            print(f"SUCCESS: Read {len(headers)} columns from feed header.")
            
            # Robust fuzzy searching for filter columns to completely avoid KeyError/ValueError
            segment_idx = next((i for i, h in enumerate(headers) if 'segment' in h), None)
            depth_idx = next((i for i, h in enumerate(headers) if 'depth' in h), None)
            type_idx = next((i for i, h in enumerate(headers) if 'type' in h and 'property' not in h), None)
            
            if segment_idx is None or depth_idx is None or type_idx is None:
                print("CRITICAL ERROR: Could not map the layout columns properly!")
                print(f"Available headers seen by script: {headers}")
                sys.exit(1)

            # STANDARD LOWERCASE GOOGLE HEADERS 
            ads_headers = ["id", "title", "link", "image_link", "description", "price"]
            
            id_idx = next((i for i, h in enumerate(headers) if h == 'id'), 0)
            title_idx = next((i for i, h in enumerate(headers) if 'title' in h), 1)
            link_idx = next((i for i, h in enumerate(headers) if 'link' in h and 'image' not in h and 'mobile' not in h and 'app' not in h), 2)
            img_idx = next((i for i, h in enumerate(headers) if 'image' in h and 'additional' not in h), 3)
            desc_idx = next((i for i, h in enumerate(headers) if 'desc' in h), 4)
            price_idx = next((i for i, h in enumerate(headers) if h == 'price' or ('price' in h and 'period' not in h and 'change' not in h)), 5)

            max_needed_idx = max(segment_idx, depth_idx, type_idx, id_idx, title_idx, link_idx, img_idx, desc_idx, price_idx)
            
            matched_count = 0
            with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.writer(outfile)
                writer.writerow(ads_headers)
                
                for row in reader:
                    if not row or len(row) <= max_needed_idx:
                        continue
                        
                    segment = row[segment_idx].strip().lower()
                    depth = row[depth_idx].strip().lower()
                    l_type = row[type_idx].strip().lower()
                    
                    # Filter matching: Diamond + (Premium OR Featured) + Buy (Sale)
                    if segment == 'diamond' and (depth == 'premium' or depth == 'featured') and 'sale' in l_type:
                        matched_count += 1
                        p_id = row[id_idx]
                        title = row[title_idx]
                        link = row[link_idx]
                        img = row[img_idx]
                        desc = row[desc_idx][:150]
                        price = row[price_idx]
                        
                        if price and "egp" not in price.lower():
                            price = f"{price} EGP"
                            
                        writer.writerow([p_id, title, link, img, desc, price])
                        
        print(f"Process complete! Filtered and saved {matched_count} matching Buy properties successfully.")

    except Exception as e:
        print("\n--- AN UNEXPECTED CRASH OCCURRED ---")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
