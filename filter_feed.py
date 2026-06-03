import io
import os
import zipfile
import requests
import traceback
import sys

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
        
        print(f"Processing text stream line-by-line for: {internal_filename}")
        with zip_file.open(internal_filename, 'r') as f:
            text_stream = io.TextIOWrapper(f, encoding='utf-8-sig', errors='ignore')
            
            header_line = text_stream.readline()
            if not header_line:
                print("CRITICAL ERROR: Feed file appears to be completely empty.")
                sys.exit(1)
            
            delimiter = '\t' if header_line.count('\t') > header_line.count(',') else ','
            print(f"Using layout delimiter: {'TAB' if delimiter == '\t' else 'COMMA'}")
            
            headers = [h.strip().lower() for h in header_line.split(delimiter)]
            print(f"SUCCESS: Located {len(headers)} master data columns.")
            
            try:
                segment_idx = headers.index('client_segment')
                depth_idx = headers.index('listings_depth')
                type_idx = headers.index('listing_type')
            except ValueError:
                segment_idx = next((i for i, h in enumerate(headers) if 'segment' in h), None)
                depth_idx = next((i for i, h in enumerate(headers) if 'depth' in h), None)
                type_idx = next((i for i, h in enumerate(headers) if 'type' in h and 'property' not in h), None)
            
            if segment_idx is None or depth_idx is None or type_idx is None:
                print(f"CRITICAL LAYOUT ERROR: Core filters missing. Headers: {headers}")
                sys.exit(1)
                
            id_idx = headers.index('id') if 'id' in headers else 0
            title_idx = headers.index('title') if 'title' in headers else 1
            link_idx = headers.index('link') if 'link' in headers else 2
            img_idx = next((i for i, h in enumerate(headers) if 'image_link' in h or ('image' in h and 'additional' not in h)), 3)
            desc_idx = next((i for i, h in enumerate(headers) if 'description' in h or 'desc' in h), 4)
            price_idx = next((i for i, h in enumerate(headers) if h == 'price' or ('price' in h and 'period' not in h and 'change' not in h)), 5)
            
            max_idx = max(segment_idx, depth_idx, type_idx, id_idx, title_idx, link_idx, img_idx, desc_idx, price_idx)
            
            matched_count = 0
            lines_scanned = 0
            
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
                outfile.write("ID,Item title,Final URL,Image URL,Item description,Price\n")
                
                for line in text_stream:
                    lines_scanned += 1
                    if not line.strip():
                        continue
                    
                    row = line.split(delimiter)
                    if len(row) <= max_idx:
                        continue
                        
                    segment = row[segment_idx].strip().lower()
                    depth = row[depth_idx].strip().lower()
                    l_type = row[type_idx].strip().lower()
                    
                    if segment == 'diamond' and (depth == 'premium' or depth == 'featured') and 'sale' in l_type:
                        matched_count += 1
                        
                        p_id = row[id_idx].strip().replace('"', '').replace(',', '')
                        title = row[title_idx].strip().replace('"', '').replace(',', ' ')
                        link = row[link_idx].strip().replace('"', '')
                        img = row[img_idx].strip().replace('"', '')
                        desc = row[desc_idx].strip().replace('"', '').replace(',', ' ').replace('\n', ' ').replace('\r', ' ')[:145]
                        price = row[price_idx].strip().replace('"', '')
                        
                        clean_price = "".join([c for c in price if c.isdigit() or c == '.'])
                        
                        outfile.write(f'"{p_id}","{title}","{link}","{img}","{desc}","{clean_price}"\n')
                        
        print(f"OUTPUT VALIDATION SUMMARY:")
        print(f"Total listings scanned: {lines_scanned}")
        print(f"Total clean rows written to CSV: {matched_count}")
        
    except Exception as e:
        print("\n--- CRASH DIAGNOSTIC LOG ---")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
