# Mehndi Design Dataset

This directory contains the pipeline to build, clean, and auto-label the Mehndi design dataset for training the multi-axis classifier.

## Dataset Sourcing
Because there are no publicly available multi-axis classification datasets for Mehndi designs, this dataset is built from scratch:
1. **Scraping**: `scrape.py` pulls images from Bing Images via `icrawler` across 8 categories:
   - `bridal` (Wedding / intricate bridal designs)
   - `arabic` (Flowing, thick-line patterns)
   - `indo_arabic` (Fusion patterns)
   - `minimalist` (Simple, modern accents)
   - `floral` (Flower-based structures)
   - `geometric` (Line art / grids)
   - `rajasthani` (Traditional full-hand wedding designs)
   - `finger` (Accents centered on fingers)
2. **Quality Filters & Deduplication**: `clean.py` verifies image integrity, filters out images with dimensions smaller than `224x224` pixels, and uses perceptual hashing (`imagehash`'s `average_hash`) to remove duplicate or near-duplicate results.
3. **Complexity Auto-Labeling**: `label_complexity.py` applies Canny edge detection to grayscale images, computes the edge density (edge pixels / total pixels), and splits the results into three balanced quantiles:
   - `simple` (low edge density)
   - `medium` (moderate edge density)
   - `intricate` (high edge density)
4. **Occasion Mapping**: Map categories directly to occasions using a predefined mapping (e.g. `bridal`/`rajasthani` -> `wedding`, `minimalist`/`finger` -> `everyday`, etc.).

## Setup & Regeneration

To regenerate the dataset locally:
1. Make sure you install the required Python dependencies:
   ```bash
   pip install icrawler Pillow imagehash opencv-python numpy
   ```
2. Run the scraping script:
   ```bash
   python scrape.py
   ```
3. Run the cleaning script:
   ```bash
   python clean.py
   ```
4. Run the auto-labeling script to generate `labels.csv`:
   ```bash
   python label_complexity.py
   ```

## Note on Usage
This dataset is constructed for personal, educational, and portfolio demonstration purposes. The raw image assets are ignored in `.gitignore` and are not checked into the repository to respect original creators and copyright holders. The schema and labeling are fully reproducible using the scripts in this folder.
