const fs = require('fs');
const path = require('path');
const db = require('./src/db');

function seedDatabase() {
    const csvPath = path.join(__dirname, '..', 'dataset', 'labels.csv');
    if (!fs.existsSync(csvPath)) {
        console.log(`Warning: Seed labels.csv not found at ${csvPath}. Skipping seeding.`);
        return;
    }
    
    console.log("Starting database seeding from labels.csv...");
    
    const content = fs.readFileSync(csvPath, 'utf8');
    const lines = content.split('\n').map(line => line.trim()).filter(line => line.length > 0);
    
    if (lines.length <= 1) {
        console.log("No data found in labels.csv. Skipping seeding.");
        return;
    }
    
    // Parse CSV headers (filepath,category,complexity,occasion)
    const headers = lines[0].split(',');
    
    const checkStmt = db.prepare('SELECT id FROM designs WHERE image_path = ?');
    const insertStmt = db.prepare(`
        INSERT INTO designs (image_path, category, complexity, occasion, tags)
        VALUES (?, ?, ?, ?, ?)
    `);
    
    let insertedCount = 0;
    let skippedCount = 0;
    
    // Start transaction for speed
    const transaction = db.transaction((rows) => {
        for (const rowStr of rows) {
            const row = rowStr.split(',');
            if (row.length < 4) continue;
            
            const filepath = row[0];
            const category = row[1];
            const complexity = row[2];
            const occasion = row[3];
            
            // Generate tags automatically
            const tags = `${category}, ${complexity}, ${occasion}, design, henna`;
            
            // Check if exists (idempotency check)
            const exists = checkStmt.get(filepath);
            if (!exists) {
                insertStmt.run(filepath, category, complexity, occasion, tags);
                insertedCount++;
            } else {
                skippedCount++;
            }
        }
    });
    
    // Run transaction on lines excluding headers
    transaction(lines.slice(1));
    
    console.log(`Seeding complete: ${insertedCount} new designs inserted, ${skippedCount} skipped.`);
}

module.exports = seedDatabase;

// Allow direct execution
if (require.main === module) {
    seedDatabase();
}
