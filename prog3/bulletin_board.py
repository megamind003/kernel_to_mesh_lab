import sqlite3
from typing import List, Set, Optional
from dataclasses import dataclass
import json
import time
import hashlib
from ballot import Ballot
from zk_circuit import VotingCircuit


@dataclass
class BulletinBoardEntry:
    entry_id: int
    ballot_json: str
    nullifier_hex: str
    timestamp: float
    verified: bool


class BulletinBoard:
    def __init__(self, db_path: str, merkle_root: bytes):
        self.db_path = db_path
        self.merkle_root = merkle_root
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._initialize_database()
        self.seen_nullifiers: Set[bytes] = self._load_nullifiers()
    
    def _initialize_database(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ballots (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ballot_json TEXT NOT NULL,
                nullifier_hex TEXT UNIQUE NOT NULL,
                timestamp REAL NOT NULL,
                verified INTEGER NOT NULL,
                previous_hash TEXT NOT NULL,
                current_hash TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_nullifier 
            ON ballots(nullifier_hex)
        ''')
        
        self.conn.commit()
    
    def _load_nullifiers(self) -> Set[bytes]:
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT nullifier_hex FROM ballots')
            return {bytes.fromhex(row[0]) for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            return set()
    
    def _get_last_hash(self) -> str:
        cursor = self.conn.cursor()
        cursor.execute('SELECT current_hash FROM ballots ORDER BY entry_id DESC LIMIT 1')
        row = cursor.fetchone()
        return row[0] if row else "0" * 64  # Genesis hash
    
    def _compute_entry_hash(self, ballot_json: str, nullifier_hex: str, 
                           timestamp: float, previous_hash: str) -> str:
        data = f"{previous_hash}|{ballot_json}|{nullifier_hex}|{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def check_nullifier_used(self, nullifier: bytes) -> bool:
        return nullifier in self.seen_nullifiers
    
    def append_ballot(self, ballot: Ballot) -> bool:
        nullifier = ballot.get_nullifier()
        
        if self.check_nullifier_used(nullifier):
            return False
        
        from ballot import BallotValidator
        validator = BallotValidator(self.merkle_root)
        
        if not validator.validate_ballot(ballot):
            return False
        
        previous_hash = self._get_last_hash()
        current_hash = self._compute_entry_hash(
            ballot.to_json(),
            nullifier.hex(),
            ballot.timestamp,
            previous_hash
        )
        
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO ballots (
                    ballot_json, nullifier_hex, timestamp, verified, 
                    previous_hash, current_hash
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                ballot.to_json(),
                nullifier.hex(),
                ballot.timestamp,
                1,
                previous_hash,
                current_hash
            ))
            
            self.conn.commit()
            self.seen_nullifiers.add(nullifier)
            return True
        
        except sqlite3.IntegrityError:
            return False
    
    def get_all_ballots(self) -> List[Ballot]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT ballot_json FROM ballots WHERE verified = 1 ORDER BY entry_id')
        
        ballots = []
        for row in cursor.fetchall():
            ballots.append(Ballot.from_json(row[0]))
        
        return ballots
    
    def get_ballot_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM ballots WHERE verified = 1')
        return cursor.fetchone()[0]
    
    def get_audit_log(self) -> List[BulletinBoardEntry]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT entry_id, ballot_json, nullifier_hex, timestamp, verified
            FROM ballots
            ORDER BY entry_id
        ''')
        
        entries = []
        for row in cursor.fetchall():
            entries.append(BulletinBoardEntry(
                entry_id=row[0],
                ballot_json=row[1],
                nullifier_hex=row[2],
                timestamp=row[3],
                verified=bool(row[4])
            ))
        
        return entries
    
    def verify_chain_integrity(self) -> bool:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ballot_json, nullifier_hex, timestamp, previous_hash, current_hash
            FROM ballots ORDER BY entry_id
        ''')
        
        expected_prev_hash = "0" * 64
        
        for row in cursor.fetchall():
            ballot_json, nullifier_hex, timestamp, prev_hash, curr_hash = row
            
            if prev_hash != expected_prev_hash:
                print(f"Chain broken! Expected prev {expected_prev_hash}, got {prev_hash}")
                return False
            
            recalculated_hash = self._compute_entry_hash(
                ballot_json, nullifier_hex, timestamp, prev_hash
            )
            
            if recalculated_hash != curr_hash:
                print(f"Hash mismatch! Expected {recalculated_hash}, got {curr_hash}")
                return False
            
            expected_prev_hash = curr_hash
            
        return True

    def verify_all_ballots(self) -> bool:
        if not self.verify_chain_integrity():
            return False

        from ballot import BallotValidator
        validator = BallotValidator(self.merkle_root)
        
        ballots = self.get_all_ballots()
        
        for ballot in ballots:
            if not validator.validate_ballot(ballot):
                return False
        
        return True
    
    def close(self):
        self.conn.close()
