name: Sync and Filter Property Finder Feed

on:
  schedule:
    - cron: '0 2 * * *' # Runs automatically every day at 2:00 AM
  workflow_dispatch: # Allows you to run it manually anytime

# Grant explicit administrative permissions to update your public GitHub website link
permissions:
  contents: write
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Install Dependencies
        run: pip install requests

      - name: Run Filter Script
        run: python filter_feed.py

      - name: Save Clean CSV to Repository Bank
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          file_pattern: 'clean_display_feed.csv'
          commit_message: 'Automated Feed Sync: Populated Custom Catalog Layout'

      - name: Setup Web Server Environment
        uses: actions/configure-pages@v5

      - name: Package CSV for Live Web Deployment
        uses: actions/upload-pages-artifact@v3
        with:
          path: '.' # Packages the folder containing your clean file

      - name: Force Web Link Update
        uses: actions/deploy-pages@v4
