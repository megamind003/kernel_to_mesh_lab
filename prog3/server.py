from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uvicorn
import time
from ballot import Ballot
from bulletin_board import BulletinBoard
from homomorphic import PaillierPrivateKey, PaillierPublicKey
from voter_registry import FastVoterRegistry
import json


app = FastAPI(title="AIGIS Voting Server")

bulletin_board: BulletinBoard = None
private_key: PaillierPrivateKey = None
public_key: PaillierPublicKey = None
num_options: int = 0
election_id: str = ""


class BallotSubmission(BaseModel):
    ballot_json: str


class TallyResponse(BaseModel):
    encrypted_tally: List[int]
    decrypted_tally: List[int]
    total_votes: int


class AuditResponse(BaseModel):
    total_ballots: int
    all_verified: bool
    audit_log: List[Dict[str, Any]]


@app.post("/submit_ballot")
async def submit_ballot(submission: BallotSubmission):
    try:
        ballot = Ballot.from_json(submission.ballot_json)
        
        if ballot.election_id != election_id:
            raise HTTPException(status_code=400, detail="Invalid election ID")
        
        success = bulletin_board.append_ballot(ballot)
        
        if not success:
            raise HTTPException(status_code=400, detail="Ballot rejected (duplicate vote or invalid proof)")
        
        return {"status": "accepted", "timestamp": ballot.timestamp}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid ballot: {str(e)}")


@app.get("/tally", response_model=TallyResponse)
async def get_tally():
    ballots = bulletin_board.get_all_ballots()
    
    if not ballots:
        return TallyResponse(
            encrypted_tally=[],
            decrypted_tally=[],
            total_votes=0
        )
    
    encrypted_tallies = [0] * num_options
    
    for ballot in ballots:
        for i in range(num_options):
            if encrypted_tallies[i] == 0:
                encrypted_tallies[i] = ballot.encrypted_votes[i]
            else:
                encrypted_tallies[i] = public_key.add_encrypted(
                    encrypted_tallies[i],
                    ballot.encrypted_votes[i]
                )
    
    decrypted_tallies = [private_key.decrypt(ct) for ct in encrypted_tallies]
    
    return TallyResponse(
        encrypted_tally=encrypted_tallies,
        decrypted_tally=decrypted_tallies,
        total_votes=len(ballots)
    )


@app.get("/audit", response_model=AuditResponse)
async def get_audit():
    entries = bulletin_board.get_audit_log()
    
    audit_log = []
    for entry in entries:
        audit_log.append({
            'entry_id': entry.entry_id,
            'nullifier': entry.nullifier_hex,
            'timestamp': entry.timestamp,
            'verified': entry.verified
        })
    
    all_verified = bulletin_board.verify_all_ballots()
    
    return AuditResponse(
        total_ballots=len(entries),
        all_verified=all_verified,
        audit_log=audit_log
    )


@app.get("/info")
async def get_info():
    return {
        'election_id': election_id,
        'num_options': num_options,
        'merkle_root': bulletin_board.merkle_root.hex(),
        'public_key_n': public_key.n,
        'public_key_g': public_key.g,
        'total_ballots': bulletin_board.get_ballot_count()
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}


def initialize_server(bb: BulletinBoard, priv_key: PaillierPrivateKey, 
                      pub_key: PaillierPublicKey, options: int, elec_id: str):
    global bulletin_board, private_key, public_key, num_options, election_id
    
    bulletin_board = bb
    private_key = priv_key
    public_key = pub_key
    num_options = options
    election_id = elec_id


def run_server(host: str = "0.0.0.0", port: int = 8000):
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    print("AIGIS Voting Server")
    print("Initialize server before running")
