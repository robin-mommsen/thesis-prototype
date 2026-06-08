CREATE TABLE IF NOT EXISTS upcycling_factsheets (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    input_materials TEXT NOT NULL,
    target_object VARCHAR(255) NOT NULL,
    difficulty VARCHAR(50),
    tools_required TEXT,
    description TEXT,
    steps TEXT,
    practical_notes TEXT,
    source VARCHAR(255),
    retrieval_text TEXT NOT NULL,
    embedding vector(768)
);