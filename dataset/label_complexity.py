import os
import glob
import csv
import numpy as np
import cv2

# Define categories
categories = [
    'bridal',
    'arabic',
    'indo_arabic',
    'minimalist',
    'floral',
    'geometric',
    'rajasthani',
    'finger',
]

# Direct category to occasion lookup mapping
occasion_mapping = {
    'bridal': 'wedding',
    'rajasthani': 'wedding',
    'minimalist': 'everyday',
    'finger': 'everyday',
    'arabic': 'party',
    'indo_arabic': 'party',
    'floral': 'festival',
    'geometric': 'festival',
}

def calculate_edge_density(image_path):
    """
    Computes the edge density of an image using Canny Edge Detection.
    """
    try:
        # Load image in grayscale
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        
        # Apply Gaussian Blur to reduce noise
        blurred = cv2.GaussianBlur(img, (5, 5), 0)
        
        # Apply Canny Edge Detection
        edges = cv2.Canny(blurred, 50, 150)
        
        # Calculate ratio of edge pixels to total pixels
        edge_pixels = np.sum(edges > 0)
        total_pixels = edges.size
        
        ratio = edge_pixels / total_pixels
        return ratio
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return None

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    records = []
    
    print("Analyzing image edge densities for complexity classification...")
    
    for category in categories:
        cat_path = os.path.join(base_dir, category)
        if not os.path.exists(cat_path):
            continue
            
        # Get all files
        image_paths = glob.glob(os.path.join(cat_path, '*'))
        for img_path in image_paths:
            if os.path.isdir(img_path):
                continue
                
            # Compute edge density
            density = calculate_edge_density(img_path)
            if density is not None:
                # We store relative path to base_dir
                rel_path = os.path.relpath(img_path, base_dir)
                records.append({
                    'filepath': rel_path.replace('\\', '/'),
                    'category': category,
                    'density': density,
                    'occasion': occasion_mapping.get(category, 'general')
                })
                
    if not records:
        print("No valid images found to label.")
        return
        
    # Classify complexity based on quantiles of edge density
    densities = [r['density'] for r in records]
    q33 = np.percentile(densities, 33.3)
    q66 = np.percentile(densities, 66.6)
    
    print(f"\nComplexity Thresholds based on edge density quantiles:")
    print(f"  Simple (density < {q33:.4f})")
    print(f"  Medium ({q33:.4f} <= density < {q66:.4f})")
    print(f"  Intricate (density >= {q66:.4f})")
    
    # Assign complexity labels
    for r in records:
        d = r['density']
        if d < q33:
            r['complexity'] = 'simple'
        elif d < q66:
            r['complexity'] = 'medium'
        else:
            r['complexity'] = 'intricate'
            
    # Write to labels.csv
    csv_path = os.path.join(base_dir, 'labels.csv')
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['filepath', 'category', 'complexity', 'occasion'])
        for r in records:
            writer.writerow([r['filepath'], r['category'], r['complexity'], r['occasion']])
            
    print(f"\nSaved complexity and occasion mappings for {len(records)} images in: {csv_path}")

if __name__ == '__main__':
    main()
