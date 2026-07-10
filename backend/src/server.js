const express = require('express');
const cors = require('cors');
const rateLimit = require('express-rate-limit');
const multer = require('multer');
const axios = require('axios');
const path = require('path');
const fs = require('fs');
const FormData = require('form-data');
require('dotenv').config();

const db = require('./db');
const seedDatabase = require('../seed');

const app = express();
const port = process.env.PORT || 5000;
const mlServiceUrl = process.env.ML_SERVICE_URL || 'http://localhost:8000';

// 1. Auto-seed Database on Startup
try {
    seedDatabase();
} catch (e) {
    console.error("Database seeding failed on startup:", e);
}

// 2. Rate Limiting Middleware
const limiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 200, // limit each IP to 200 requests per windowMs
    message: { error: "Too many requests from this IP. Please try again later." }
});
app.use('/api/', limiter);

// 3. CORS Configuration
const allowedOrigin = process.env.ALLOWED_ORIGIN || 'http://localhost:3000';
app.use(cors({
    origin: allowedOrigin === '*' ? '*' : allowedOrigin.split(','),
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization']
}));

app.use(express.json());

// 4. Serve Scraped Image Assets as Static Files
// The dataset folder is at the repo root (one level up from backend)
const datasetPath = path.join(__dirname, '..', '..', 'dataset');
app.use('/dataset', express.static(datasetPath));

// 5. Multer Setup for handling temporary image uploads in memory
const upload = multer({
    storage: multer.memoryStorage(),
    limits: {
        fileSize: 5 * 1024 * 1024 // 5MB limit
    }
});

// Helper: Find or create user by session ID
function getOrCreateUser(sessionId) {
    let user = db.prepare('SELECT id, session_id FROM users WHERE session_id = ?').get(sessionId);
    if (!user) {
        const info = db.prepare('INSERT INTO users (session_id) VALUES (?)').run(sessionId);
        user = { id: info.lastInsertRowId, session_id: sessionId };
        // Create blank preferences entry
        db.prepare('INSERT INTO preferences (user_id, liked_design_ids, filter_history) VALUES (?, ?, ?)')
          .run(user.id, '', '[]');
    }
    return user;
}

// ==========================================
// ENDPOINTS
// ==========================================

// GET /health
app.get('/health', (req, res) => {
    res.json({
        status: "healthy",
        database_connected: true,
        design_count: db.prepare('SELECT COUNT(*) as count FROM designs').get().count
    });
});

// GET /api/designs (Paginated + Filterable)
app.get('/api/designs', (req, res) => {
    try {
        const page = parseInt(req.query.page) || 1;
        const limit = parseInt(req.query.limit) || 20;
        const category = req.query.category;
        const complexity = req.query.complexity;
        const occasion = req.query.occasion;
        const search = req.query.search;
        
        const offset = (page - 1) * limit;
        
        let query = 'SELECT * FROM designs';
        let countQuery = 'SELECT COUNT(*) as count FROM designs';
        let params = [];
        let conditions = [];
        
        if (category) {
            conditions.push('category = ?');
            params.push(category);
        }
        if (complexity) {
            conditions.push('complexity = ?');
            params.push(complexity);
        }
        if (occasion) {
            conditions.push('occasion = ?');
            params.push(occasion);
        }
        if (search) {
            conditions.push('(tags LIKE ? OR category LIKE ? OR complexity LIKE ? OR occasion LIKE ?)');
            const searchParam = `%${search}%`;
            params.push(searchParam, searchParam, searchParam, searchParam);
        }
        
        if (conditions.length > 0) {
            const whereClause = ' WHERE ' + conditions.join(' AND ');
            query += whereClause;
            countQuery += whereClause;
        }
        
        // Count total matching items
        const totalCount = db.prepare(countQuery).get(...params).count;
        
        // Add limit and offset
        query += ' LIMIT ? OFFSET ?';
        const queryParams = [...params, limit, offset];
        
        const designs = db.prepare(query).all(...queryParams);
        const totalPages = Math.ceil(totalCount / limit);
        
        res.json({
            designs,
            current_page: page,
            total_pages: totalPages,
            total_count: totalCount
        });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: "Database query failed." });
    }
});

// POST /api/recommend (Proxy to ML service + Log search history)
app.post('/api/recommend', upload.single('referenceImage'), async (req, res) => {
    try {
        const { userId, category, complexity, occasion } = req.body;
        
        if (!userId) {
            return res.status(400).json({ error: "userId (session_id) is required." });
        }
        
        const user = getOrCreateUser(userId);
        
        // Build FormData to send to Python FastAPI ml-service
        const form = new FormData();
        if (category) form.append('category', category);
        if (complexity) form.append('complexity', complexity);
        if (occasion) form.append('occasion', occasion);
        
        if (req.file) {
            form.append('file', req.file.buffer, {
                filename: req.file.originalname,
                contentType: req.file.mimetype
            });
        }
        
        // Fetch recommendations from ML service
        console.log(`Proxying recommend request to ML service: ${mlServiceUrl}/recommend`);
        const mlRes = await axios.post(`${mlServiceUrl}/recommend`, form, {
            headers: {
                ...form.getHeaders()
            }
        });
        
        const mlRecommendations = mlRes.data.recommendations;
        
        // Enrich recommendations with database information
        const enrichedRecs = [];
        const logStmt = db.prepare(`
            INSERT INTO recommendation_history (user_id, design_id, was_liked)
            VALUES (?, ?, 0)
        `);
        const designQuery = db.prepare('SELECT * FROM designs WHERE image_path = ?');
        
        for (const item of mlRecommendations) {
            const design = designQuery.get(item.design_id);
            if (design) {
                enrichedRecs.push({
                    ...design,
                    similarity_score: item.similarity_score
                });
                
                // Log this recommendation interaction to SQLite (limit logs to top 5 to prevent DB bloat)
                if (enrichedRecs.length <= 5) {
                    try {
                        logStmt.run(user.id, design.id);
                    } catch (e) {
                        // Ignore duplicate key log warnings
                    }
                }
            }
        }
        
        // Save to User Search Filter History
        const prefs = db.prepare('SELECT filter_history FROM preferences WHERE user_id = ?').get(user.id);
        let filterHistory = [];
        if (prefs && prefs.filter_history) {
            try {
                filterHistory = JSON.parse(prefs.filter_history);
            } catch (e) {}
        }
        
        // Append new search query to history list
        filterHistory.unshift({
            category: category || null,
            complexity: complexity || null,
            occasion: occasion || null,
            timestamp: new Date().toISOString()
        });
        // Limit history to last 10 entries
        filterHistory = filterHistory.slice(0, 10);
        
        db.prepare('UPDATE preferences SET filter_history = ? WHERE user_id = ?')
          .run(JSON.stringify(filterHistory), user.id);
          
        res.json({
            recommendations: enrichedRecs,
            total_matches: mlRes.data.total_matches
        });
        
    } catch (err) {
        console.error("Error fetching recommendations:", err.message);
        res.status(500).json({ error: "Failed to communicate with ML service recommendation engine." });
    }
});

// POST /api/classify (Proxy uploaded image to ML service classification)
app.post('/api/classify', upload.single('image'), async (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ error: "No image file uploaded." });
        }
        
        const form = new FormData();
        form.append('file', req.file.buffer, {
            filename: req.file.originalname,
            contentType: req.file.mimetype
        });
        
        console.log(`Proxying classify request to ML service: ${mlServiceUrl}/classify`);
        const mlRes = await axios.post(`${mlServiceUrl}/classify`, form, {
            headers: {
                ...form.getHeaders()
            }
        });
        
        res.json(mlRes.data);
    } catch (err) {
        console.error("Error classifying image:", err.message);
        res.status(500).json({ error: "Failed to communicate with classification model." });
    }
});

// POST /api/preferences (Like design / save filter selection)
app.post('/api/preferences', (req, res) => {
    try {
        const { userId, likedDesignId, filterHistory } = req.body;
        
        if (!userId) {
            return res.status(400).json({ error: "userId (session_id) is required." });
        }
        
        const user = getOrCreateUser(userId);
        
        if (likedDesignId) {
            // Get current liked designs list
            const prefs = db.prepare('SELECT liked_design_ids FROM preferences WHERE user_id = ?').get(user.id);
            let likedList = prefs && prefs.liked_design_ids ? prefs.liked_design_ids.split(',').filter(Boolean) : [];
            
            const designIdStr = String(likedDesignId);
            
            if (likedList.includes(designIdStr)) {
                // Unlike: Remove from list
                likedList = likedList.filter(id => id !== designIdStr);
                
                // Update interaction log
                db.prepare(`
                    UPDATE recommendation_history 
                    SET was_liked = 0 
                    WHERE user_id = ? AND design_id = ?
                `).run(user.id, likedDesignId);
            } else {
                // Like: Add to list
                likedList.push(designIdStr);
                
                // Update interaction log
                db.prepare(`
                    UPDATE recommendation_history 
                    SET was_liked = 1 
                    WHERE user_id = ? AND design_id = ?
                `).run(user.id, likedDesignId);
            }
            
            db.prepare('UPDATE preferences SET liked_design_ids = ? WHERE user_id = ?')
              .run(likedList.join(','), user.id);
              
            return res.json({ success: true, liked_design_ids: likedList });
        }
        
        if (filterHistory) {
            db.prepare('UPDATE preferences SET filter_history = ? WHERE user_id = ?')
              .run(JSON.stringify(filterHistory), user.id);
            return res.json({ success: true });
        }
        
        res.status(400).json({ error: "Provide likedDesignId or filterHistory to update." });
        
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: "Failed to update user preferences." });
    }
});

// GET /api/preferences/:userId (Fetch history and personalized likes)
app.get('/api/preferences/:userId', (req, res) => {
    try {
        const { userId } = req.params;
        const user = db.prepare('SELECT id, session_id FROM users WHERE session_id = ?').get(userId);
        
        if (!user) {
            return res.json({ liked_designs: [], filter_history: [], recommendation_history: [] });
        }
        
        // 1. Get likes
        const prefs = db.prepare('SELECT liked_design_ids, filter_history FROM preferences WHERE user_id = ?').get(user.id);
        let likedList = prefs && prefs.liked_design_ids ? prefs.liked_design_ids.split(',').filter(Boolean) : [];
        let filterHistory = prefs && prefs.filter_history ? JSON.parse(prefs.filter_history) : [];
        
        let likedDesigns = [];
        if (likedList.length > 0) {
            const placeholders = likedList.map(() => '?').join(',');
            likedDesigns = db.prepare(`SELECT * FROM designs WHERE id IN (${placeholders})`).all(...likedList);
        }
        
        // 2. Get past recommendation interactions (recent 10 items)
        const history = db.prepare(`
            SELECT h.id, h.timestamp, h.was_liked, d.id as design_id, d.image_path, d.category, d.complexity, d.occasion
            FROM recommendation_history h
            JOIN designs d ON h.design_id = d.id
            WHERE h.user_id = ?
            ORDER BY h.timestamp DESC
            LIMIT 10
        `).all(user.id);
        
        res.json({
            liked_designs: likedDesigns,
            filter_history: filterHistory,
            recommendation_history: history
        });
        
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: "Failed to fetch user preferences." });
    }
});

// Start Express Server
app.listen(port, () => {
    console.log(`Backend Express gateway listening on port ${port}`);
});
