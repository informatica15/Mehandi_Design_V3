import os
import glob
from PIL import Image
import imagehash

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

def clean_category(category_path):
    print(f"\nCleaning directory: {category_path}")
    
    # Get all files in category path
    image_paths = glob.glob(os.path.join(category_path, '*'))
    
    unique_hashes = set()
    deleted_corrupt = 0
    deleted_small = 0
    deleted_duplicates = 0
    valid_count = 0
    
    for img_path in image_paths:
        # Skip if directory
        if os.path.isdir(img_path):
            continue
            
        try:
            # Try to open image and verify it
            with Image.open(img_path) as img:
                img.verify()
        except Exception:
            try:
                os.remove(img_path)
            except OSError:
                pass
            deleted_corrupt += 1
            continue
            
        # Re-open for size check and hashing since verify() closes the file pointer or limits access
        try:
            with Image.open(img_path) as img:
                # Check resolution
                width, height = img.size
                if width < 224 or height < 224:
                    os.remove(img_path)
                    deleted_small += 1
                    continue
                
                # Check duplicate using perceptual average hashing
                img_hash = imagehash.average_hash(img)
                if img_hash in unique_hashes:
                    os.remove(img_path)
                    deleted_duplicates += 1
                    continue
                
                unique_hashes.add(img_hash)
                valid_count += 1
                
        except Exception as e:
            try:
                os.remove(img_path)
            except OSError:
                pass
            deleted_corrupt += 1
            
    print(f"Results for {os.path.basename(category_path)}:")
    print(f"  Valid kept: {valid_count}")
    print(f"  Deleted corrupt/unreadable: {deleted_corrupt}")
    print(f"  Deleted small (<224x224): {deleted_small}")
    print(f"  Deleted duplicates: {deleted_duplicates}")
    return valid_count

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    total_valid = 0
    
    for category in categories:
        cat_path = os.path.join(base_dir, category)
        if os.path.exists(cat_path):
            count = clean_category(cat_path)
            total_valid += count
        else:
            print(f"Directory not found: {cat_path}")
            
    print(f"\nCleanup complete. Total valid images remaining: {total_valid}")

if __name__ == '__main__':
    main()
