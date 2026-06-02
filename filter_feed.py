import io
import os
import zipfile
import csv
import requests

# 1. Your Property Finder Google Format URL
FEED_URL = "https://marketingfeeds.propertyfinder.net/eg/en/export/google/full/b5543c8e7a4bfc2ff66636569c135c73473535d37788cf024e2987035b3df4267c3a1f7330ea7d1dcb90f677be73e50de26776e7039b21db4715c1a0d03e8aef"
OUTPUT_FILE = "clean_display_feed.csv"

def main():
    print("Downloading compressed data package from Property Finder...")
    response = requests.get(FEED_URL, stream=True)
    if response.status_code != 200:
        raise Exception(f"Failed to download feed. Status code: {response.status_code}")
        
    print("Extracting archive in-memory...")
    zip_file = zipfile.ZipFile(io.BytesIO(response.content))
    internal_filename = zip_file.namelist()[0]
    
    print(f"Streaming and parsing file: {internal_filename}...")
    # Open the file inside the zip as a text stream
    with zip_file.open(internal_filename, 'r') as f:
        # Wrap the binary stream into text mode
        text_stream = io.TextIOWrapper(f, encoding='utf-8')
        
        # Sneak peek at the first line to detect if it's Tab or Comma separated
        sample = text_stream.readline()
        delimiter = '\t' if '\t' in sample else ','
        text_stream.seek(0) # Reset stream back to the beginning
        
        reader = csv.reader(text_stream, delimiter=delimiter)
        headers = next(reader)
        
        # Clean up header white spaces
        headers = [h.strip().lower() for h in headers]
        
        # Dynamically locate your filter columns
        try:
            segment_idx = headers.index('client_segment')
            depth_idx = headers.index('listings_depth')
        except ValueError:
            print(f"CRITICAL ERROR: Filter columns not found. Headers available: {headers}")
            return

        # Core headers required for a standard Google Ads Custom Display Feed
        # We will dynamically map them from your Property Finder columns
        ads_headers = ["ID", "Item title", "Final URL", "Image URL", "Item description", "Price"]
        
        # Find structural layout replacements (handling variations)
        id_idx = headers.index('id') if 'id' in headers else 0
        title_idx = headers.index('title') if 'title' in headers else 1
        link_idx = headers.index('link') if 'link' in headers else 2
        
        img_idx = next((i for i, h in enumerate(headers) if 'image' in h), 3)
        desc_idx = next((i for i, h in enumerate(headers) if 'desc' in h), 4)
        price_idx = next((i for i, h in enumerate(headers) if 'price' in h), 5)

        matched_count = 0
        total_count = 0

        # Open our output file to write clean rows on the fly (saves RAM)
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(ads_headers) # Write custom feed layout headers
            
            for row in reader:
                if not row or len(row) <= max(segment_idx, depth_idx):
                    continue
                total_count += 1
                
                segment = row[segment_idx].strip().lower()
                depth = row[depth_idx].strip().lower()
                
                # ========================================================
                #   YOUR CUSTOM FILTERS (Diamond + Premium or Featured)
                # ========================================================
                if segment == 'diamond' and (depth == 'premium' or depth == 'featured'):
                    matched_count += 1
                    
                    # Pull values and protect against short data index row mismatches
                    p_id = row[id_idx] if id_idx < len(row) else ""
                    title = row[title_idx] if title_idx < len(row) else ""
                    link = row[link_idx] if link_idx < len(row) else ""
                    img = row[img_idx] if img_idx < len(row) else ""
                    desc = row[desc_idx][:150] if desc_idx < len(row) else "" # Trim descriptions for ad space
                    price = row[price_idx] if price_idx < len(row) else ""
                    
                    writer.writerow([p_id, title, link, img, desc, price])

        print(f"Process complete. Scanned {total_count} rows. Saved {matched_count} Diamond matches directly to CSV.")

if __name__ == "__main__":
    main()
