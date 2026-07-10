import os
import json
import pandas as pd
import numpy as np
import cv2

# Ensure model directory exists
model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model')
os.makedirs(model_dir, exist_ok=True)

def extract_features_sklearn(image_path):
    """
    Extracts custom visual features (mean RGB, std RGB, Canny edge map)
    to represent images when TensorFlow is not available.
    """
    try:
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            return None
            
        # 1. Color features: Mean and Std of RGB channels
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mean_color = np.mean(img_rgb, axis=(0, 1)) / 255.0
        std_color = np.std(img_rgb, axis=(0, 1)) / 255.0
        color_features = np.concatenate([mean_color, std_color]) # shape (6,)
        
        # 2. Texture/Edge features: Resize to 64x64 and compute Canny edges
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_resized = cv2.resize(img_gray, (64, 64))
        edges = cv2.Canny(img_resized, 50, 150) / 255.0
        edge_features = edges.flatten() # shape (4096,)
        
        # Combine features
        features = np.concatenate([color_features, edge_features]) # shape (4102,)
        return features
    except Exception as e:
        print(f"Error extracting features for {image_path}: {e}")
        return None

def train_tensorflow(df, category_list, complexity_list, occasion_list, model_dir):
    """
    Full TensorFlow CNN Training Pipeline (Runs on Python <= 3.12).
    """
    import tensorflow as tf
    from sklearn.model_selection import train_test_split
    
    category_to_idx = {name: idx for idx, name in enumerate(category_list)}
    complexity_to_idx = {name: idx for idx, name in enumerate(complexity_list)}
    occasion_to_idx = {name: idx for idx, name in enumerate(occasion_list)}
    
    df['cat_idx'] = df['category'].map(category_to_idx)
    df['comp_idx'] = df['complexity'].map(complexity_to_idx)
    df['occ_idx'] = df['occasion'].map(occasion_to_idx)
    
    # Split
    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df['cat_idx'])
    
    def preprocess_image(path, category, complexity, occasion):
        img_raw = tf.io.read_file(path)
        img = tf.image.decode_jpeg(img_raw, channels=3)
        img = tf.image.resize(img, [224, 224])
        img = img / 255.0
        return img, {
            'category': category,
            'complexity': complexity,
            'occasion': occasion
        }
        
    # Dataset
    BATCH_SIZE = 16
    train_ds = tf.data.Dataset.from_tensor_slices((
        train_df['full_path'].values,
        train_df['cat_idx'].values,
        train_df['comp_idx'].values,
        train_df['occ_idx'].values
    )).map(preprocess_image, num_parallel_calls=tf.data.AUTOTUNE).shuffle(100).batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)
    
    val_ds = tf.data.Dataset.from_tensor_slices((
        val_df['full_path'].values,
        val_df['cat_idx'].values,
        val_df['comp_idx'].values,
        val_df['occ_idx'].values
    )).map(preprocess_image, num_parallel_calls=tf.data.AUTOTUNE).batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)
    
    data_augmentation = tf.keras.Sequential([
        tf.keras.layers.RandomRotation(0.05),
        tf.keras.layers.RandomZoom(0.05),
        tf.keras.layers.RandomFlip("horizontal"),
    ])
    
    base_model = tf.keras.applications.MobileNetV2(
        input_shape=(224, 224, 3),
        include_top=False,
        weights='imagenet'
    )
    base_model.trainable = False
    
    inputs = tf.keras.Input(shape=(224, 224, 3))
    x = data_augmentation(inputs)
    x = base_model(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    
    shared_features = tf.keras.layers.Dense(128, activation='relu', name='feature_vector')(x)
    
    out_cat = tf.keras.layers.Dense(len(category_list), activation='softmax', name='category')(shared_features)
    out_comp = tf.keras.layers.Dense(len(complexity_list), activation='softmax', name='complexity')(shared_features)
    out_occ = tf.keras.layers.Dense(len(occasion_list), activation='softmax', name='occasion')(shared_features)
    
    model = tf.keras.Model(inputs=inputs, outputs=[out_cat, out_comp, out_occ, shared_features])
    
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss={
            'category': 'sparse_categorical_crossentropy',
            'complexity': 'sparse_categorical_crossentropy',
            'occasion': 'sparse_categorical_crossentropy'
        },
        metrics={
            'category': 'accuracy',
            'complexity': 'accuracy',
            'occasion': 'accuracy'
        }
    )
    
    print("\nTraining CNN via TensorFlow...")
    model.fit(train_ds, validation_data=val_ds, epochs=10, verbose=1)
    
    # Save SavedModel
    saved_model_path = os.path.join(model_dir, 'saved_model')
    model.save(saved_model_path)
    print(f"TensorFlow SavedModel exported to {saved_model_path}")
    
    # Run evaluation metrics
    val_results = model.evaluate(val_ds, verbose=0)
    metrics_names = model.metrics_names
    cat_acc = val_results[metrics_names.index('category_accuracy')]
    comp_acc = val_results[metrics_names.index('complexity_accuracy')]
    occ_acc = val_results[metrics_names.index('occasion_accuracy')]
    
    # Save training summary
    with open(os.path.join(model_dir, 'training_summary.json'), 'w') as f:
        json.dump({
            'framework': 'tensorflow',
            'validation_category_accuracy': float(cat_acc),
            'validation_complexity_accuracy': float(comp_acc),
            'validation_occasion_accuracy': float(occ_acc)
        }, f, indent=4)

def train_sklearn(df, category_list, complexity_list, occasion_list, model_dir):
    """
    Self-Healing Scikit-Learn Pipeline (Runs on Python 3.14 as fallback).
    """
    print("\nTensorFlow not found or unsupported. Falling back to Scikit-Learn training...")
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.multioutput import MultiOutputClassifier
    from sklearn.model_selection import train_test_split
    
    # 1. Feature extraction for all images
    print("Extracting Canny edge and RGB color features from dataset...")
    X = []
    y_cat = []
    y_comp = []
    y_occ = []
    
    category_to_idx = {name: idx for idx, name in enumerate(category_list)}
    complexity_to_idx = {name: idx for idx, name in enumerate(complexity_list)}
    occasion_to_idx = {name: idx for idx, name in enumerate(occasion_list)}
    
    # We also keep a database of image features to support content similarity recommendations
    dataset_features = {}
    
    for idx, row in df.iterrows():
        feat = extract_features_sklearn(row['full_path'])
        if feat is not None:
            X.append(feat)
            y_cat.append(category_to_idx[row['category']])
            y_comp.append(complexity_to_idx[row['complexity']])
            y_occ.append(occasion_to_idx[row['occasion']])
            
            # Store features relative to dataset root
            dataset_features[row['filepath']] = feat.tolist()
            
    X = np.array(X)
    Y = np.column_stack([y_cat, y_comp, y_occ])
    
    # Split
    X_train, X_val, Y_train, Y_val = train_test_split(X, Y, test_size=0.2, random_state=42, stratify=Y[:, 0])
    
    # Train MultiOutput Random Forest
    print(f"Training Random Forest on features. Input shape: {X_train.shape}, Outputs: 3")
    base_forest = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=15)
    classifier = MultiOutputClassifier(base_forest)
    classifier.fit(X_train, Y_train)
    
    # Evaluate
    train_acc = classifier.score(X_train, Y_train)
    val_acc = classifier.score(X_val, Y_val)
    print(f"  Training accuracy: {train_acc:.4f}")
    print(f"  Validation accuracy: {val_acc:.4f}")
    
    # Single accuracy reports per task
    preds = classifier.predict(X_val)
    cat_acc = np.mean(preds[:, 0] == Y_val[:, 0])
    comp_acc = np.mean(preds[:, 1] == Y_val[:, 1])
    occ_acc = np.mean(preds[:, 2] == Y_val[:, 2])
    print(f"  Category Val Accuracy: {cat_acc:.4f}")
    print(f"  Complexity Val Accuracy: {comp_acc:.4f}")
    print(f"  Occasion Val Accuracy: {occ_acc:.4f}")
    
    # Save model and recommendation features database
    joblib.dump(classifier, os.path.join(model_dir, 'sklearn_model.joblib'))
    joblib.dump(dataset_features, os.path.join(model_dir, 'dataset_features.joblib'))
    print(f"Scikit-Learn model and features exported to {model_dir}")
    
    # Save training summary
    with open(os.path.join(model_dir, 'training_summary.json'), 'w') as f:
        json.dump({
            'framework': 'scikit-learn',
            'validation_category_accuracy': float(cat_acc),
            'validation_complexity_accuracy': float(comp_acc),
            'validation_occasion_accuracy': float(occ_acc)
        }, f, indent=4)

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_dir = os.path.join(base_dir, 'dataset')
    labels_csv = os.path.join(dataset_dir, 'labels.csv')
    
    if not os.path.exists(labels_csv):
        print(f"Error: {labels_csv} not found. Run Phase 0 pipeline first.")
        return
        
    df = pd.read_csv(labels_csv)
    df['full_path'] = df['filepath'].apply(lambda x: os.path.join(dataset_dir, x).replace('\\', '/'))
    df = df[df['full_path'].apply(os.path.exists)].reset_index(drop=True)
    
    if len(df) == 0:
        print("Error: No existing images found in dataset. Scraping failed.")
        return
        
    category_list = sorted(df['category'].unique())
    complexity_list = sorted(df['complexity'].unique())
    occasion_list = sorted(df['occasion'].unique())
    
    # Save label mappings list
    with open(os.path.join(model_dir, 'label_mappings.json'), 'w') as f:
        json.dump({
            'category': category_list,
            'complexity': complexity_list,
            'occasion': occasion_list
        }, f, indent=4)
        
    # Check framework availability
    has_tf = False
    try:
        import tensorflow as tf
        has_tf = True
    except ImportError:
        pass
        
    if has_tf:
        try:
            train_tensorflow(df, category_list, complexity_list, occasion_list, model_dir)
        except Exception as e:
            print(f"Error during TensorFlow training: {e}. Falling back to scikit-learn...")
            train_sklearn(df, category_list, complexity_list, occasion_list, model_dir)
    else:
        train_sklearn(df, category_list, complexity_list, occasion_list, model_dir)

if __name__ == '__main__':
    main()
