import os
import json
import numpy as np
import pandas as pd
import cv2
import joblib
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel

app = FastAPI(
    title="Mehndi Design Recommendation ML Service",
    description="Inference service for multi-axis classification and content-based recommendation",
    version="1.0.0"
)

# CORS configurations
allowed_origins = os.getenv("ALLOWED_ORIGIN", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables to store models and labels
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model')
dataset_dir = os.path.join(base_dir, 'dataset')

label_mappings = {}
framework = "scikit-learn"  # Default fallback
model_sklearn = None
dataset_features_cache = {}  # In-memory feature vectors cache for recommendations
labels_df = None

# TFLite Interpreter globals
tflite_interpreter = None
tflite_input_details = None
tflite_output_details = None

def extract_features_sklearn(img_bytes):
    """
    Extracts custom visual features (mean RGB, std RGB, Canny edge map) from image bytes.
    """
    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None
            
        # 1. Color features: Mean and Std of RGB channels
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mean_color = np.mean(img_rgb, axis=(0, 1)) / 255.0
        std_color = np.std(img_rgb, axis=(0, 1)) / 255.0
        color_features = np.concatenate([mean_color, std_color])
        
        # 2. Texture/Edge features: Resize to 64x64 and compute Canny edges
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_resized = cv2.resize(img_gray, (64, 64))
        edges = cv2.Canny(img_resized, 50, 150) / 255.0
        edge_features = edges.flatten()
        
        features = np.concatenate([color_features, edge_features])
        return features
    except Exception as e:
        print(f"Error extracting sklearn features: {e}")
        return None

def preprocess_image_tflite(img_bytes):
    """
    Loads, resizes, and normalizes image for TFLite MobileNetV2 input.
    """
    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (224, 224))
        img_normalized = img_resized.astype(np.float32) / 255.0
        # Add batch dimension: (1, 224, 224, 3)
        return np.expand_dims(img_normalized, axis=0)
    except Exception as e:
        print(f"Error preprocessing image for TFLite: {e}")
        return None

@app.on_event("startup")
def startup_event():
    global label_mappings, framework, model_sklearn, dataset_features_cache, labels_df
    global tflite_interpreter, tflite_input_details, tflite_output_details
    
    # 1. Load label mappings
    mapping_path = os.path.join(model_dir, 'label_mappings.json')
    if os.path.exists(mapping_path):
        with open(mapping_path, 'r') as f:
            label_mappings = json.load(f)
    else:
        # Fallback default lists
        label_mappings = {
            'category': ['arabic', 'bridal', 'finger', 'floral', 'geometric', 'indo_arabic', 'minimalist', 'rajasthani'],
            'complexity': ['intricate', 'medium', 'simple'],
            'occasion': ['everyday', 'festival', 'party', 'wedding']
        }
        
    # 2. Load dataset labels CSV if available
    labels_csv = os.path.join(dataset_dir, 'labels.csv')
    if os.path.exists(labels_csv):
        labels_df = pd.read_csv(labels_csv)
        print(f"Loaded {len(labels_df)} entries from labels.csv")
    else:
        print("Warning: labels.csv not found. Recommendation database will be empty on startup.")
        labels_df = pd.DataFrame(columns=['filepath', 'category', 'complexity', 'occasion'])
        
    # 3. Detect framework and load model
    tflite_path = os.path.join(model_dir, 'model.tflite')
    sklearn_model_path = os.path.join(model_dir, 'sklearn_model.joblib')
    
    # Check if we can import tensorflow
    has_tf = False
    try:
        import tensorflow as tf
        has_tf = True
    except ImportError:
        pass
        
    # We verify if the TFLite file is a real compiled TFLite model or our fallback string
    is_real_tflite = False
    if os.path.exists(tflite_path):
        with open(tflite_path, 'rb') as f:
            head = f.read(20)
            # TFLite models start with standard schema headers (typically contains 'TFL3' in offset 4)
            if b"scikit-learn-fallback" not in head:
                is_real_tflite = True
                
    if has_tf and is_real_tflite:
        print("TensorFlow and TFLite model found. Initializing TFLite Interpreter...")
        try:
            tflite_interpreter = tf.lite.Interpreter(model_path=tflite_path)
            tflite_interpreter.allocate_tensors()
            tflite_input_details = tflite_interpreter.get_input_details()
            tflite_output_details = tflite_interpreter.get_output_details()
            framework = "tensorflow"
            print("TFLite Interpreter initialized successfully.")
        except Exception as e:
            print(f"Error allocating TFLite interpreter: {e}. Trying Scikit-Learn fallback...")
            
    if framework == "scikit-learn":
        if os.path.exists(sklearn_model_path):
            print("Loading Scikit-Learn RandomForest classifier...")
            model_sklearn = joblib.load(sklearn_model_path)
            print("Scikit-Learn model loaded successfully.")
        else:
            print("Warning: No trained model found. Inference will return mock predictions.")
            
    # 4. Build in-memory recommendation features cache
    # This prevents reloading/re-extracting features from disk during recommend queries
    print("Building recommendation feature cache in memory...")
    if framework == "scikit-learn":
        # Check if features are already saved to disk during training
        features_path = os.path.join(model_dir, 'dataset_features.joblib')
        if os.path.exists(features_path):
            dataset_features_cache = joblib.load(features_path)
            print(f"Loaded {len(dataset_features_cache)} cached feature vectors from disk.")
        else:
            # Re-extract
            for idx, row in labels_df.iterrows():
                full_img_path = os.path.join(dataset_dir, row['filepath'])
                if os.path.exists(full_img_path):
                    with open(full_img_path, 'rb') as f:
                        feat = extract_features_sklearn(f.read())
                        if feat is not None:
                            dataset_features_cache[row['filepath']] = feat.tolist()
    else:
        # TensorFlow path: Compute model embeddings for all images
        for idx, row in labels_df.iterrows():
            full_img_path = os.path.join(dataset_dir, row['filepath'])
            if os.path.exists(full_img_path):
                try:
                    with open(full_img_path, 'rb') as f:
                        img_input = preprocess_image_tflite(f.read())
                        if img_input is not None:
                            # Run TFLite inference to extract feature vector
                            tflite_interpreter.set_tensor(tflite_input_details[0]['index'], img_input)
                            tflite_interpreter.invoke()
                            
                            # Retrieve the 128-dimensional bottleneck layer output
                            # The model has 4 outputs. We identify the correct index by checking output shapes.
                            feature_vector = None
                            for detail in tflite_output_details:
                                if detail['shape'][-1] == 128:
                                    feature_vector = tflite_interpreter.get_tensor(detail['index'])[0]
                                    break
                            if feature_vector is not None:
                                dataset_features_cache[row['filepath']] = feature_vector.tolist()
                except Exception as e:
                    print(f"Error caching features for {row['filepath']}: {e}")
                    
    print(f"Feature cache built. Ready to serve recommendations for {len(dataset_features_cache)} images.")

# Response structures
class ClassificationResponse(BaseModel):
    category: str
    category_confidence: float
    complexity: str
    complexity_confidence: float
    occasion: str
    occasion_confidence: float
    framework_used: str

class RecommendationItem(BaseModel):
    design_id: str  # Matches relative image path
    category: str
    complexity: str
    occasion: str
    similarity_score: float

class RecommendationResponse(BaseModel):
    recommendations: List[RecommendationItem]
    total_matches: int

@app.get("/health")
def health_check():
    tflite_model_exists = os.path.exists(os.path.join(model_dir, 'model.tflite'))
    sklearn_model_exists = os.path.exists(os.path.join(model_dir, 'sklearn_model.joblib'))
    
    return {
        "status": "healthy",
        "active_framework": framework,
        "label_mappings_loaded": len(label_mappings.get('category', [])) > 0,
        "database_entries_count": len(labels_df) if labels_df is not None else 0,
        "model_files": {
            "tflite": tflite_model_exists,
            "sklearn": sklearn_model_exists
        }
    }

@app.post("/classify", response_model=ClassificationResponse)
async def classify_image(file: UploadFile = File(...)):
    img_bytes = await file.read()
    
    # Validation
    if not img_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
        
    category_pred, category_conf = "unknown", 0.0
    complexity_pred, complexity_conf = "unknown", 0.0
    occasion_pred, occasion_conf = "unknown", 0.0
    
    if framework == "tensorflow" and tflite_interpreter is not None:
        # Preprocess
        img_input = preprocess_image_tflite(img_bytes)
        if img_input is None:
            raise HTTPException(status_code=400, detail="Invalid image encoding.")
            
        try:
            # Set input tensor
            tflite_interpreter.set_tensor(tflite_input_details[0]['index'], img_input)
            tflite_interpreter.invoke()
            
            # Map outputs based on shapes
            # Output details contain:
            # - category (size matches category count)
            # - complexity (size matches complexity count)
            # - occasion (size matches occasion count)
            cat_probs, comp_probs, occ_probs = None, None, None
            
            for detail in tflite_output_details:
                shape_last = detail['shape'][-1]
                tensor_val = tflite_interpreter.get_tensor(detail['index'])[0]
                
                if shape_last == len(label_mappings['category']):
                    cat_probs = tensor_val
                elif shape_last == len(label_mappings['complexity']):
                    comp_probs = tensor_val
                elif shape_last == len(label_mappings['occasion']):
                    occ_probs = tensor_val
            
            if cat_probs is not None:
                cat_idx = np.argmax(cat_probs)
                category_pred = label_mappings['category'][cat_idx]
                category_conf = float(cat_probs[cat_idx])
                
            if comp_probs is not None:
                comp_idx = np.argmax(comp_probs)
                complexity_pred = label_mappings['complexity'][comp_idx]
                complexity_conf = float(comp_probs[comp_idx])
                
            if occ_probs is not None:
                occ_idx = np.argmax(occ_probs)
                occasion_pred = label_mappings['occasion'][occ_idx]
                occasion_conf = float(occ_probs[occ_idx])
                
        except Exception as e:
            print(f"Error during TFLite execution: {e}")
            raise HTTPException(status_code=500, detail="Error running model inference.")
            
    elif framework == "scikit-learn" and model_sklearn is not None:
        # Extract Canny/Color features
        feat = extract_features_sklearn(img_bytes)
        if feat is None:
            raise HTTPException(status_code=400, detail="Invalid image encoding.")
            
        try:
            X = np.expand_dims(feat, axis=0)
            
            # predict_proba returns a list of arrays
            probs_list = model_sklearn.predict_proba(X)
            
            # probs_list[0] -> category, probs_list[1] -> complexity, probs_list[2] -> occasion
            cat_probs = probs_list[0][0]
            comp_probs = probs_list[1][0]
            occ_probs = probs_list[2][0]
            
            cat_idx = np.argmax(cat_probs)
            category_pred = label_mappings['category'][cat_idx]
            category_conf = float(cat_probs[cat_idx])
            
            comp_idx = np.argmax(comp_probs)
            complexity_pred = label_mappings['complexity'][comp_idx]
            complexity_conf = float(comp_probs[comp_idx])
            
            occ_idx = np.argmax(occ_probs)
            occasion_pred = label_mappings['occasion'][occ_idx]
            occasion_conf = float(occ_probs[occ_idx])
            
        except Exception as e:
            print(f"Error during Scikit-Learn execution: {e}")
            raise HTTPException(status_code=500, detail="Error running model inference.")
    else:
        # Mock predictions if no model is loaded
        category_pred, category_conf = label_mappings['category'][0], 0.85
        complexity_pred, complexity_conf = label_mappings['complexity'][0], 0.90
        occasion_pred, occasion_conf = label_mappings['occasion'][0], 0.80
        
    return ClassificationResponse(
        category=category_pred,
        category_confidence=category_conf,
        complexity=complexity_pred,
        complexity_confidence=complexity_conf,
        occasion=occasion_pred,
        occasion_confidence=occasion_conf,
        framework_used=framework
    )

@app.post("/recommend", response_model=RecommendationResponse)
async def recommend_designs(
    category: Optional[str] = Form(None),
    complexity: Optional[str] = Form(None),
    occasion: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    if labels_df is None or len(labels_df) == 0:
        return RecommendationResponse(recommendations=[], total_matches=0)
        
    ref_embedding = None
    
    # 1. Compute reference image embedding if uploaded
    if file is not None:
        img_bytes = await file.read()
        if img_bytes:
            if framework == "tensorflow" and tflite_interpreter is not None:
                img_input = preprocess_image_tflite(img_bytes)
                if img_input is not None:
                    try:
                        tflite_interpreter.set_tensor(tflite_input_details[0]['index'], img_input)
                        tflite_interpreter.invoke()
                        for detail in tflite_output_details:
                            if detail['shape'][-1] == 128:
                                ref_embedding = tflite_interpreter.get_tensor(detail['index'])[0]
                                break
                    except Exception as e:
                        print(f"Error computing ref embedding in TFLite: {e}")
            elif framework == "scikit-learn":
                ref_embedding = extract_features_sklearn(img_bytes)

    # 2. Filter dataset based on preferences
    filtered_df = labels_df.copy()
    if category:
        filtered_df = filtered_df[filtered_df['category'] == category]
    if complexity:
        filtered_df = filtered_df[filtered_df['complexity'] == complexity]
    if occasion:
        filtered_df = filtered_df[filtered_df['occasion'] == occasion]
        
    matches = []
    
    # 3. Calculate similarity score for each matching design
    for idx, row in filtered_df.iterrows():
        design_id = row['filepath']
        sim_score = 1.0  # Default similarity if no reference image is uploaded
        
        # If similarity matching is requested and we have cached features
        if ref_embedding is not None and design_id in dataset_features_cache:
            design_embedding = np.array(dataset_features_cache[design_id])
            ref_vector = np.array(ref_embedding)
            
            # Compute cosine similarity
            dot_product = np.dot(ref_vector, design_embedding)
            norm_ref = np.linalg.norm(ref_vector)
            norm_design = np.linalg.norm(design_embedding)
            
            if norm_ref > 0 and norm_design > 0:
                sim_score = float(dot_product / (norm_ref * norm_design))
            else:
                sim_score = 0.0
                
        matches.append(RecommendationItem(
            design_id=design_id,
            category=row['category'],
            complexity=row['complexity'],
            occasion=row['occasion'],
            similarity_score=sim_score
        ))
        
    # Sort matches by similarity score descending
    matches.sort(key=lambda x: x.similarity_score, reverse=True)
    
    return RecommendationResponse(
        recommendations=matches,
        total_matches=len(matches)
    )

if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
