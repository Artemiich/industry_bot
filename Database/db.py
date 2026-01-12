import aiosqlite

DB_NAME = 'factory.db'

async def create_tables():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                phone TEXT
            )
        """)
        # Поля sub_category делаем TEXT (можно NULL)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product TEXT,
                shift TEXT,
                stage TEXT,
                category TEXT,
                sub_category TEXT, 
                quantity INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

# ... add_user и get_user оставляем те же ...
async def add_user(user_id: int, username: str, phone: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, username, phone) VALUES (?, ?, ?)", (user_id, username, phone))
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def add_order(user_id: int, data: dict, quantity: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO orders (user_id, product, shift, stage, category, sub_category, quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data['product'],
            data['shift'],
            data['stage'],
            data['category'],
            data['sub_category'], # Сюда придет None или строка
            quantity
        ))
        await db.commit()