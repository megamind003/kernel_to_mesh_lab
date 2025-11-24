#!/usr/bin/env python3

import asyncio
import asyncpg
import os
from dotenv import load_dotenv


async def init_database():
    load_dotenv()
    
    database_url = os.getenv("DATABASE_URL", "postgresql://panopticon:panopticon@localhost/panopticon")
    
    print("Connecting to database...")
    conn = await asyncpg.connect(database_url)
    
    try:
        print("Checking TimescaleDB extension...")
        result = await conn.fetchval("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'")
        
        if result:
            print("TimescaleDB extension is installed")
        else:
            print("Warning: TimescaleDB extension not found")
        
        print("\nChecking PostGIS extension...")
        result = await conn.fetchval("SELECT extname FROM pg_extension WHERE extname = 'postgis'")
        
        if result:
            print("PostGIS extension is installed")
        else:
            print("Warning: PostGIS extension not found")
        
        print("\nCreating sample users...")
        for i in range(1, 101):
            await conn.execute(
                "INSERT INTO users (user_id, email, risk_score) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                i,
                f"user{i}@example.com",
                (i % 100)
            )
        
        user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        print(f"Users in database: {user_count}")
        
        print("\nVerifying fraud rules...")
        rule_count = await conn.fetchval("SELECT COUNT(*) FROM fraud_rules WHERE enabled = true")
        print(f"Active fraud rules: {rule_count}")
        
        print("\nVerifying continuous aggregates...")
        aggregates = await conn.fetch(
            """
            SELECT view_name 
            FROM timescaledb_information.continuous_aggregates
            """
        )
        
        for agg in aggregates:
            print(f"  - {agg['view_name']}")
        
        print("\nDatabase initialization complete!")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(init_database())
