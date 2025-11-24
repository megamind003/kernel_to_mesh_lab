import time
import random
import threading
from enum import Enum
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass

class NodeState(Enum):
    FOLLOWER = 0
    CANDIDATE = 1
    LEADER = 2

@dataclass
class LogEntry:
    term: int
    command: Any

@dataclass
class RequestVoteArgs:
    term: int
    candidate_id: int
    last_log_index: int
    last_log_term: int

@dataclass
class RequestVoteReply:
    term: int
    vote_granted: bool

@dataclass
class AppendEntriesArgs:
    term: int
    leader_id: int
    prev_log_index: int
    prev_log_term: int
    entries: List[LogEntry]
    leader_commit: int

@dataclass
class AppendEntriesReply:
    term: int
    success: bool

class RaftNode:
    """
    Raft Consensus Algorithm Implementation.
    Manages leader election and log replication.
    """
    def __init__(self, node_id: int, peers: List['RaftNode']):
        self.node_id = node_id
        self.peers = peers
        self.state = NodeState.FOLLOWER
        
        # Persistent state
        self.current_term = 0
        self.voted_for = None
        self.log: List[LogEntry] = []
        
        # Volatile state
        self.commit_index = -1
        self.last_applied = -1
        
        # Leader state
        self.next_index: Dict[int, int] = {}
        self.match_index: Dict[int, int] = {}
        
        # Timers
        self.election_timeout = random.uniform(0.15, 0.3)
        self.last_heartbeat = time.time()
        self.running = True
        
        # State machine callback
        self.apply_callback: Optional[Callable[[Any], None]] = None
        
        self.lock = threading.Lock()
        
    def start(self):
        threading.Thread(target=self._run_loop, daemon=True).start()
        
    def stop(self):
        self.running = False
        
    def set_apply_callback(self, callback: Callable[[Any], None]):
        self.apply_callback = callback
        
    def _run_loop(self):
        while self.running:
            with self.lock:
                if self.state == NodeState.LEADER:
                    self._send_heartbeats()
                elif time.time() - self.last_heartbeat > self.election_timeout:
                    self._start_election()
            time.sleep(0.05)
            
    def _start_election(self):
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.last_heartbeat = time.time()
        votes_received = 1
        
        print(f"Node {self.node_id} starting election for term {self.current_term}")
        
        args = RequestVoteArgs(
            term=self.current_term,
            candidate_id=self.node_id,
            last_log_index=len(self.log) - 1,
            last_log_term=self.log[-1].term if self.log else 0
        )
        
        for peer in self.peers:
            if peer.node_id == self.node_id:
                continue
            
            # Simulate RPC
            reply = peer.request_vote(args)
            
            if reply.term > self.current_term:
                self.current_term = reply.term
                self.state = NodeState.FOLLOWER
                self.voted_for = None
                return
            
            if reply.vote_granted:
                votes_received += 1
                
        if self.state == NodeState.CANDIDATE and votes_received > len(self.peers) // 2:
            self._become_leader()
            
    def _become_leader(self):
        print(f"Node {self.node_id} became LEADER for term {self.current_term}")
        self.state = NodeState.LEADER
        for peer in self.peers:
            self.next_index[peer.node_id] = len(self.log)
            self.match_index[peer.node_id] = -1
        self._send_heartbeats()
        
    def _send_heartbeats(self):
        for peer in self.peers:
            if peer.node_id == self.node_id:
                continue
                
            prev_log_index = self.next_index[peer.node_id] - 1
            prev_log_term = self.log[prev_log_index].term if prev_log_index >= 0 else 0
            entries = self.log[self.next_index[peer.node_id]:]
            
            args = AppendEntriesArgs(
                term=self.current_term,
                leader_id=self.node_id,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                entries=entries,
                leader_commit=self.commit_index
            )
            
            reply = peer.append_entries(args)
            
            if reply.term > self.current_term:
                self.current_term = reply.term
                self.state = NodeState.FOLLOWER
                self.voted_for = None
                return
            
            if reply.success:
                self.next_index[peer.node_id] = prev_log_index + len(entries) + 1
                self.match_index[peer.node_id] = prev_log_index + len(entries)
            else:
                self.next_index[peer.node_id] = max(0, self.next_index[peer.node_id] - 1)
                
        self._update_commit_index()
        
    def _update_commit_index(self):
        for i in range(len(self.log) - 1, self.commit_index, -1):
            if self.log[i].term != self.current_term:
                continue
                
            count = 1
            for peer in self.peers:
                if peer.node_id == self.node_id:
                    continue
                if self.match_index.get(peer.node_id, -1) >= i:
                    count += 1
            
            if count > len(self.peers) // 2:
                self.commit_index = i
                self._apply_logs()
                break
                
    def _apply_logs(self):
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log[self.last_applied]
            if self.apply_callback:
                self.apply_callback(entry.command)
                
    def request_vote(self, args: RequestVoteArgs) -> RequestVoteReply:
        with self.lock:
            if args.term > self.current_term:
                self.current_term = args.term
                self.state = NodeState.FOLLOWER
                self.voted_for = None
                
            if args.term < self.current_term:
                return RequestVoteReply(self.current_term, False)
            
            if (self.voted_for is None or self.voted_for == args.candidate_id):
                # Check log up-to-dateness
                last_idx = len(self.log) - 1
                last_term = self.log[-1].term if self.log else 0
                
                if (args.last_log_term > last_term) or \
                   (args.last_log_term == last_term and args.last_log_index >= last_idx):
                    self.voted_for = args.candidate_id
                    self.last_heartbeat = time.time()
                    return RequestVoteReply(self.current_term, True)
                    
            return RequestVoteReply(self.current_term, False)
            
    def append_entries(self, args: AppendEntriesArgs) -> AppendEntriesReply:
        with self.lock:
            if args.term > self.current_term:
                self.current_term = args.term
                self.state = NodeState.FOLLOWER
                self.voted_for = None
                
            self.last_heartbeat = time.time()
            
            if args.term < self.current_term:
                return AppendEntriesReply(self.current_term, False)
                
            # Check log consistency
            if args.prev_log_index >= 0:
                if len(self.log) <= args.prev_log_index:
                    return AppendEntriesReply(self.current_term, False)
                if self.log[args.prev_log_index].term != args.prev_log_term:
                    # Conflict: delete everything from here
                    self.log = self.log[:args.prev_log_index]
                    return AppendEntriesReply(self.current_term, False)
            
            # Append new entries
            for i, entry in enumerate(args.entries):
                idx = args.prev_log_index + 1 + i
                if idx < len(self.log):
                    if self.log[idx].term != entry.term:
                        self.log = self.log[:idx]
                        self.log.append(entry)
                else:
                    self.log.append(entry)
            
            if args.leader_commit > self.commit_index:
                self.commit_index = min(args.leader_commit, len(self.log) - 1)
                self._apply_logs()
                
            return AppendEntriesReply(self.current_term, True)
            
    def replicate(self, command: Any) -> bool:
        if self.state != NodeState.LEADER:
            return False
            
        with self.lock:
            self.log.append(LogEntry(self.current_term, command))
            self.match_index[self.node_id] = len(self.log) - 1
            return True
