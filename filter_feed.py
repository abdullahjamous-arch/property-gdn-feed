import io
import os
import zipfile
import csv
import requests

FEED_URL = "https://marketingfeeds.propertyfinder.net/eg/en/export/google/full/b5543c8e7a4bfc2ff66636569c135c73473535d37788cf024e2987035b3df4267c3a1f7330ea7d1dcb90f677be73e50de26776e7039b21db4715c1a0d03e8aef"
OUTPUT_FILE = "clean_display_feed.csv"

def main():
    print("Downloading compressed data package...")
    response = requests.get(FEED_URL, stream=True)
    if response.status_code != 200:
        raise Exception(f"Failed to download feed. Status: {response.status_code}")
        
    zip_file = zipfile.ZipFile(io.BytesIO(response.content))
    internal_filename = zip_file.namelist()[0]
    
    with zip_file.open(internal_filename, 'r') as f:
        text_stream = io.TextIOWrapper(f, encoding='utf-8')
        sample = text_stream.readline()
        delimiter = '\t' if '\t' in sample else ','
        text_stream.seek(0) 
        
        reader = csv.reader(text_stream, delimiter=delimiter)
        headers = [h.strip().lower() for h in next(reader)]
        
        try:
            segment_idx = headers.index('client_segment')
            depth_idx = headers.index('listings_depth')
            type_idx = headers.index('listing_type') # <-- Added for targeting Buy listings
        except ValueError:
            print(f"Columns not found. Headers: {headers}")
            return

        ads_headers = ["ID", "Item title", "Final URL", "Image URL", "Item description", "Price"]
        id_idx = headers.index('id') if 'id' in headers else 0
        title_idx = headers.index('title') if 'title' in headers else 1
        link_idx = headers.index('link') if 'link' in headers else 2
        img_idx = next((i for i, h in enumerate(headers) if 'image' in h), 3)
        desc_idx = next((i for i, h in enumerate(headers) if 'desc' in h), 4)
        price_idx = next((i for i, h in enumerate(headers) if 'price' in h), 5)

        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(ads_headers)
            
            for row in reader:
                if not row or len(row) <= max(segment_idx, depth_idx, type_idx):
                    continue
                segment = row[segment_idx].strip().lower()
                depth = row[depth_idx].strip().lower()
                l_type = row[type_idx].strip().lower() # <-- Pulling listing type string
                
                # =========================================================================================
                #   UPDATED CUSTOM FILTERS (Diamond + Premium/Featured + For Sale By Agent)
                # =========================================================================================
                if segment == 'diamond' and (depth == 'premium' or depth == 'featured') and l_type == 'for_sale_by_agent':
                    p_id = row[id_idx] if id_idx < len(row) else ""
                    title = row[title_idx] if title_idx < len(row) else ""
                    link = row[link_idx] if link_idx < len(row) else ""
                    img = row[img_idx] if img_idx < len(row) else ""
                    desc = row[desc_idx][:150] if desc_idx < len(row) else ""
                    price = row[price_idx] if price_idx < len(row) else ""
                    writer.writerow([p_id, title, link, img, desc, price])
    print("Complete!")

if __name__ == "__main__":
    main()
