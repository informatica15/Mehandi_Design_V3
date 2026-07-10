const path = require('path');
const fs = require('fs');

const dbDir = path.join(__dirname, '..', 'database');
if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
}

const dbPath = path.join(dbDir, 'mehndi_db.json');

// Initialize data state
let data = {
    designs: [],
    users: [],
    preferences: [],
    recommendation_history: []
};

// Load existing state from disk
if (fs.existsSync(dbPath)) {
    try {
        data = JSON.parse(fs.readFileSync(dbPath, 'utf8'));
        // Check for integrity
        if (!data.designs) data.designs = [];
        if (!data.users) data.users = [];
        if (!data.preferences) data.preferences = [];
        if (!data.recommendation_history) data.recommendation_history = [];
    } catch (e) {
        console.error("Failed to parse mehndi_db.json, starting fresh:", e);
    }
}

// Persist data helper
function saveData() {
    try {
        fs.writeFileSync(dbPath, JSON.stringify(data, null, 2), 'utf8');
    } catch (e) {
        console.error("Failed to save mehndi_db.json:", e);
    }
}

// Mimic better-sqlite3 API
const db = {
    pragma(str) {
        // No-op
    },
    exec(sql) {
        // No-op
    },
    transaction(fn) {
        return function(...args) {
            // In-memory transactions execute directly
            const result = fn(...args);
            saveData();
            return result;
        };
    },
    prepare(sql) {
        const sqlClean = sql.replace(/\s+/g, ' ').trim();
        
        // 1. seed.js: SELECT id FROM designs WHERE image_path = ?
        if (sqlClean.includes('SELECT id FROM designs WHERE image_path = ?')) {
            return {
                get(image_path) {
                    const design = data.designs.find(d => d.image_path === image_path);
                    return design ? { id: design.id } : undefined;
                }
            };
        }
        
        // 1b. server.js: SELECT * FROM designs WHERE image_path = ?
        if (sqlClean.includes('SELECT * FROM designs WHERE image_path = ?')) {
            return {
                get(image_path) {
                    return data.designs.find(d => d.image_path === image_path);
                }
            };
        }
        
        // 2. seed.js: INSERT INTO designs (image_path, category, complexity, occasion, tags)
        if (sqlClean.includes('INSERT INTO designs')) {
            return {
                run(image_path, category, complexity, occasion, tags) {
                    const id = data.designs.length + 1;
                    data.designs.push({ id, image_path, category, complexity, occasion, tags });
                    saveData();
                    return { lastInsertRowId: id };
                }
            };
        }
        
        // 3. server.js: SELECT COUNT(*) as count FROM designs
        if (sqlClean.includes('SELECT COUNT(*) as count FROM designs')) {
            return {
                get(...params) {
                    let filtered = data.designs;
                    let pIdx = 0;
                    if (sqlClean.includes('category = ?')) {
                        const val = params[pIdx++];
                        filtered = filtered.filter(d => d.category === val);
                    }
                    if (sqlClean.includes('complexity = ?')) {
                        const val = params[pIdx++];
                        filtered = filtered.filter(d => d.complexity === val);
                    }
                    if (sqlClean.includes('occasion = ?')) {
                        const val = params[pIdx++];
                        filtered = filtered.filter(d => d.occasion === val);
                    }
                    if (sqlClean.includes('tags LIKE ?')) {
                        const searchVal = params[pIdx++].replace(/%/g, '').toLowerCase();
                        filtered = filtered.filter(d => 
                            (d.tags && d.tags.toLowerCase().includes(searchVal)) ||
                            (d.category && d.category.toLowerCase().includes(searchVal)) ||
                            (d.complexity && d.complexity.toLowerCase().includes(searchVal)) ||
                            (d.occasion && d.occasion.toLowerCase().includes(searchVal))
                        );
                    }
                    return { count: filtered.length };
                }
            };
        }
        
        // 4. server.js: SELECT * FROM designs WHERE id IN (...)
        if (sqlClean.includes('SELECT * FROM designs WHERE id IN')) {
            return {
                all(...ids) {
                    const numericIds = ids.map(Number);
                    return data.designs.filter(d => numericIds.includes(Number(d.id)));
                }
            };
        }
        
        // 5. server.js: SELECT * FROM designs (with optional WHERE and LIMIT/OFFSET)
        if (sqlClean.includes('SELECT * FROM designs')) {
            return {
                all(...params) {
                    let filtered = [...data.designs];
                    let pIdx = 0;
                    if (sqlClean.includes('category = ?')) {
                        const val = params[pIdx++];
                        filtered = filtered.filter(d => d.category === val);
                    }
                    if (sqlClean.includes('complexity = ?')) {
                        const val = params[pIdx++];
                        filtered = filtered.filter(d => d.complexity === val);
                    }
                    if (sqlClean.includes('occasion = ?')) {
                        const val = params[pIdx++];
                        filtered = filtered.filter(d => d.occasion === val);
                    }
                    if (sqlClean.includes('tags LIKE ?')) {
                        const searchVal = params[pIdx++].replace(/%/g, '').toLowerCase();
                        filtered = filtered.filter(d => 
                            (d.tags && d.tags.toLowerCase().includes(searchVal)) ||
                            (d.category && d.category.toLowerCase().includes(searchVal)) ||
                            (d.complexity && d.complexity.toLowerCase().includes(searchVal)) ||
                            (d.occasion && d.occasion.toLowerCase().includes(searchVal))
                        );
                    }
                    
                    // The last two parameters of queryParams in server.js are [limit, offset]
                    const limit = params[params.length - 2];
                    const offset = params[params.length - 1];
                    
                    if (typeof limit === 'number' && typeof offset === 'number') {
                        return filtered.slice(offset, offset + limit);
                    }
                    return filtered;
                }
            };
        }
        
        // 6. server.js: SELECT id, session_id FROM users WHERE session_id = ?
        if (sqlClean.includes('SELECT id, session_id FROM users WHERE session_id = ?')) {
            return {
                get(session_id) {
                    return data.users.find(u => u.session_id === session_id);
                }
            };
        }
        
        // 7. server.js: INSERT INTO users (session_id) VALUES (?)
        if (sqlClean.includes('INSERT INTO users')) {
            return {
                run(session_id) {
                    const id = data.users.length + 1;
                    data.users.push({ id, session_id });
                    saveData();
                    return { lastInsertRowId: id };
                }
            };
        }
        
        // 8. server.js: INSERT INTO preferences (user_id, liked_design_ids, filter_history)
        if (sqlClean.includes('INSERT INTO preferences')) {
            return {
                run(user_id, liked_design_ids, filter_history) {
                    data.preferences.push({ user_id, liked_design_ids, filter_history });
                    saveData();
                    return { changes: 1 };
                }
            };
        }
        
        // 9. server.js: SELECT liked_design_ids, filter_history FROM preferences WHERE user_id = ?
        if (sqlClean.includes('SELECT liked_design_ids, filter_history FROM preferences WHERE user_id = ?')) {
            return {
                get(user_id) {
                    return data.preferences.find(p => Number(p.user_id) === Number(user_id));
                }
            };
        }
        
        // 10. server.js: UPDATE preferences SET filter_history = ? WHERE user_id = ?
        if (sqlClean.includes('UPDATE preferences SET filter_history = ?')) {
            return {
                run(filter_history, user_id) {
                    const pref = data.preferences.find(p => Number(p.user_id) === Number(user_id));
                    if (pref) {
                        pref.filter_history = filter_history;
                        saveData();
                    }
                    return { changes: 1 };
                }
            };
        }
        
        // 11. server.js: UPDATE preferences SET liked_design_ids = ? WHERE user_id = ?
        if (sqlClean.includes('UPDATE preferences SET liked_design_ids = ?')) {
            return {
                run(liked_design_ids, user_id) {
                    const pref = data.preferences.find(p => Number(p.user_id) === Number(user_id));
                    if (pref) {
                        pref.liked_design_ids = liked_design_ids;
                        saveData();
                    }
                    return { changes: 1 };
                }
            };
        }
        
        // 12. server.js: INSERT INTO recommendation_history (user_id, design_id, was_liked)
        if (sqlClean.includes('INSERT INTO recommendation_history')) {
            return {
                run(user_id, design_id) {
                    const id = data.recommendation_history.length + 1;
                    data.recommendation_history.push({
                        id,
                        user_id: Number(user_id),
                        design_id: Number(design_id),
                        timestamp: new Date().toISOString(),
                        was_liked: 0
                    });
                    saveData();
                    return { lastInsertRowId: id };
                }
            };
        }
        
        // 13. server.js: UPDATE recommendation_history SET was_liked = ? WHERE user_id = ? AND design_id = ?
        if (sqlClean.includes('UPDATE recommendation_history SET was_liked = ?')) {
            return {
                run(was_liked, user_id, design_id) {
                    const logs = data.recommendation_history.filter(h => 
                        Number(h.user_id) === Number(user_id) && 
                        Number(h.design_id) === Number(design_id)
                    );
                    for (const l of logs) {
                        l.was_liked = Number(was_liked);
                    }
                    saveData();
                    return { changes: logs.length };
                }
            };
        }
        
        // 14. server.js: SELECT h.id, h.timestamp, h.was_liked, d.id as design_id...
        if (sqlClean.includes('FROM recommendation_history h JOIN designs d')) {
            return {
                all(user_id) {
                    const logs = data.recommendation_history.filter(h => Number(h.user_id) === Number(user_id));
                    // Sort descending by timestamp
                    logs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                    const recent = logs.slice(0, 10);
                    
                    return recent.map(h => {
                        const design = data.designs.find(d => Number(d.id) === Number(h.design_id));
                        return {
                            id: h.id,
                            timestamp: h.timestamp,
                            was_liked: h.was_liked,
                            design_id: h.design_id,
                            image_path: design ? design.image_path : '',
                            category: design ? design.category : '',
                            complexity: design ? design.complexity : '',
                            occasion: design ? design.occasion : ''
                        };
                    });
                }
            };
        }
        
        console.warn("Warning: Unrecognized SQL statement requested in mock DB:", sqlClean);
        return {
            get() { return undefined; },
            all() { return []; },
            run() { return { lastInsertRowId: 1, changes: 0 }; }
        };
    }
};

module.exports = db;
