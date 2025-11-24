# prog : Progetti universitari rinati (con auto‑testing)

[![Monorepo](https://img.shields.io/badge/repo-monorepo-blue.svg?style=flat-square)]() [![Linux-first](https://img.shields.io/badge/target-Linux%20first-black?logo=linux&style=flat-square)]() [![Auto‑testing](https://img.shields.io/badge/auto--testing-enabled-brightgreen?style=flat-square)]() [![Heavy%20data](https://img.shields.io/badge/heavy%20data-external%20%2F%20ignored-orange?style=flat-square)]() [![Status](https://img.shields.io/badge/status-active%20%2F%20wip-yellow?style=flat-square)]()

Questa repo raccoglie progetti che tenevo su un backup sviluppati durante l'università per allenare competenze di sistemi, reti, AI e grafica, riattivati e aggiornati con l'ausilio di Codex per introdurre auto‑testing, stress test riproducibili e pipeline dati per i casi pesanti. L'obiettivo è documentare, consolidare e rendere eseguibili i prototipi, senza caricare materiale ingombrante.

> Nota: la cartella `data_hardcore/` contiene asset voluminosi per benchmark/stress (video 4K, dataset finanziari, modelli 3D, rootfs, ecc.). Non verrà pubblicata su GitHub. In README spieghiamo come usarla in locale senza versionarla.

---

## Struttura del repository

- `prog1/` — PROJECT TITAN (Go): runtime container e orchestrazione low‑level (namespaces, cgroups, overlayfs, veth). Prototipo educativo “from scratch”.
- `prog2/` — PROJECT HYDRA (Go + Rust): key‑value store distribuito AP con LSM‑Tree, gossip, quorums e hinted‑handoff.
- `prog3/` — PROJECT AIGIS (Python): protocollo di voto E2E‑verifiable con ZK‑proofs, nullifier deterministici e somma omomorfica.
- `prog4/` — PROJECT CORTEX (Python): “neural extension OS” offline‑first (RAG ibrido, GraphRAG, reranking, privacy locale).
- `prog5/` — PROJECT FLUX (Rust): edge proxy ad alte prestazioni (thread‑per‑core, HTTP/2, QUIC, Wasm, TLS hot‑reload).
- `prog6/` — PROJECT PANOPTICON (Python): sentinella antifrode real‑time (P99 < 200ms) con TimescaleDB/PostGIS/Redis + ONNX.
- `prog7/` — PROJECT GHOSTFS (C/FUSE + Rust): filesystem a deniability plausibile tramite steganografia LSB su PNG.
- `prog8/` — PROJECT AETHER (Rust): data mesh P2P (libp2p/QUIC, chunking content‑defined, vector clocks, Noise protocol).
- `progetti_idee/` — Quaderni di progetto: specifiche visionarie e roadmap (vedi sommario più sotto).
- `data_hardcore/` — Asset locali ingombranti per stress test e demo (ignorati dal VCS; vedi sezione dedicata).
- `.gitignore` — Regole estese per escludere binari, artefatti ML e tutti gli asset pesanti.

---

## Tabella riassuntiva (stato/stack)

| Progetto   | Cartella  | Stack                     | Stato | Scopo sintetico |
|------------|-----------|---------------------------|-------|-----------------|
| TITAN      | `prog1/`  | Go + Linux syscalls       | α     | Runtime container + orchestrazione low‑level |
| HYDRA      | `prog2/`  | Go (cluster) + Rust (LSM) | α     | KV distribuito AP con quorums e gossip |
| AIGIS      | `prog3/`  | Python (crypto/ZK)        | α     | Voto E2E‑verifiable, ZK‑proofs + tally omomorfico |
| CORTEX     | `prog4/`  | Python (RAG/GraphRAG)     | α     | Secondo cervello offline‑first, hybrid search |
| FLUX       | `prog5/`  | Rust (net/QUIC/Wasm)      | α     | Edge proxy thread‑per‑core con estensioni Wasm |
| PANOPTICON | `prog6/`  | Python + Timescale/PostGIS/Redis + ONNX | α | Antifrode real‑time (P99 < 200ms) |
| GHOSTFS    | `prog7/`  | C/FUSE + OpenSSL + libpng | MVP   | FS steganografico con deniability plausibile |
| AETHER     | `prog8/`  | Rust (libp2p/QUIC/tokio)  | WIP   | Data mesh P2P offline‑first |

Legenda: α = Alpha, MVP = prototipo utilizzabile, WIP = work‑in‑progress.

---

## Come si usano i progetti (quick start)

Requisiti consigliati per ambienti di sviluppo locali:
- Go ≥ 1.20, Rust ≥ 1.76, Python ≥ 3.11
- Linux per i progetti di sistema (TITAN/ghostfs richiedono privilegi e kernel features)
- Docker/Docker Compose dove indicato

Esempi rapidi per progetto (build/run/test):

### prog1 — TITAN
```bash
# Build
cd prog1 && go build -o titan ./cmd
# Run (rootfs richiesto)
chmod +x setup_rootfs.sh && sudo ./setup_rootfs.sh
sudo ./titan run --memory 52428800 --pids 20 /bin/sh
```

### prog2 — HYDRA
```bash
# Build
cd prog2/libhydra && cargo build --release && cd ..
export CGO_LDFLAGS="-L$(pwd)/libhydra/target/release -lhydra_engine"
export LD_LIBRARY_PATH="$(pwd)/libhydra/target/release:$LD_LIBRARY_PATH"
go build -o hydra ./cmd/hydra
# Run cluster
./run_node.sh seed 9001
./run_node.sh node2 9002 127.0.0.1:9001
# Test (esempi)
python3 tests/cluster_test.py
```

### prog3 — AIGIS
```bash
cd prog3 && python -m venv venv && . venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn server:app --reload
```

### prog4 — CORTEX
```bash
cd prog4 && pip install -r requirements.txt
python ingest.py   # indicizzazione locale multimodale
python main.py     # query offline
```

### prog5 — FLUX
```bash
cd prog5 && cargo build --release
./target/release/flux --config ./flux.yaml
cargo test -q
```

### prog6 — PANOPTICON
```bash
cd prog6 && cp .env.example .env
docker-compose up -d
python scripts/init_db.py
pytest -q
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### prog7 — GHOSTFS
```bash
cd prog7 && make
mkdir -p /tmp/ghost_mount
./bin/ghostfs /path/alle/png /tmp/ghost_mount -o password=mypassword
# test/validazione
make test || true
```

### prog8 — AETHER
```bash
cd prog8 && cargo test -q
cargo run
```

---

## Auto‑testing e “casi pesanti” (con Codex)

Aggiornamenti trasversali introdotti per rendere i prototipi robusti:
- Test automatizzati per linguaggio/stack (Go: `go test`; Python: `pytest`; Rust: `cargo test`).
- Stress test riproducibili e benchmark scriptati; dove opportuno, harness per caos di rete/processo.
- Dataset/asset pesanti spostati in `data_hardcore/` e marcati in `.gitignore`; i test li montano on‑demand se presenti in locale.
- Per progetti I/O‑bound (FLUX/STREAMFORGE) introdotte pipeline zero‑copy e fixture realistiche.

Suggerimenti:
- Eseguire i test progetto per progetto (evita di saturare la macchina con tutti i carichi insieme).
- Valutare Git LFS solo per sample minimi: gli asset reali restano fuori repo.

---

## `data_hardcore/` (non versionata)

Contiene materiale per stress test e demo realistiche. Esempi (non esaustivo):
- Video 4K (es. `tearsofsteel_4k.mov`) per STREAMFORGE/VORTEX; modelli 3D (`DamagedHelmet.glb`, scene `.blend`) per SENTINELLA/visualizzazioni.
- Dataset finanziari (`btcusd_1-min_data.csv`, `kaggle_stock_data.csv`) e frodi (`creditcard.csv`) per AEQUITAS/PANOPTICON.
- Rootfs (`alpine-minirootfs-*.tar.gz`) per TITAN; benchmark/asset grafici (Unigine Heaven).


---

## Sommario da `progetti_idee/`

Le seguenti idee guidano i repository esistenti e le future evoluzioni.

- PROJECT TITAN — Distributed Container Fabric & Orchestration Kernel
  - Perché: comprendere a basso livello container, isolamento, cgroups e rete; orchestrazione “self‑healing”.
  - Cosa fa: runtime con namespaces + overlayfs + cgroups v2; bridge veth; primi mattoni di scheduler/consenso.
- PROJECT HYDRA — Distributed Persistent KV Store (AP)
  - Perché: storage scritto per durabilità e disponibilità sotto partizioni.
  - Cosa fa: LSM‑Tree, WAL, compaction; consistent hashing con VNodes; gossip; quorum R/W; hinted‑handoff.
- PROJECT AIGIS — Zero‑Trust Cryptographic Democracy Protocol
  - Perché: risultati verificabili senza fiducia nell'infrastruttura.
  - Cosa fa: ZK‑SNARK membership, nullifier anti‑double‑vote, somma omomorfica, bulletin board immutabile.
- PROJECT CORTEX — Neural Extension OS (Offline‑First)
  - Perché: secondo cervello locale, privato e performante.
  - Cosa fa: ingestion multimodale (OCR/Whisper/Code), Hybrid Search (BM25+embeddings) + GraphRAG, reranking, cifratura a riposo.
- PROJECT FLUX — Hyper‑Scale Traffic Engine
  - Perché: proxy/edge moderno, programmabile e resiliente.
  - Cosa fa: thread‑per‑core, io_uring/epoll, HTTP/2 e QUIC, estensioni Wasm, circuit breaking e rate limiting, TLS hot‑reload.
- PROJECT PANOPTICON — High‑Frequency Financial Sentinel
  - Perché: antifrode deterministica con latenza stretta.
  - Cosa fa: FastAPI async, TimescaleDB/PostGIS, Redis probabilistico, rule engine AST, locking/idempotenza, ML ONNX in‑process.
- PROJECT GHOSTFS — Plausible Deniability Filesystem
  - Perché: archiviazione “invisibile” con steganografia + cifratura.
  - Cosa fa: FUSE, LSB su PNG, AES‑XTS+Argon2id, metadati nascosti, journaling pianificato.
- PROJECT AETHER — Sovereign Data Mesh (P2P)
  - Perché: sincronizzazione device‑to‑device, offline‑first, senza cloud.
  - Cosa fa: libp2p/QUIC, hole punching, DHT Kademlia, chunking content‑defined, vector clocks, Noise.
- PROJECT CHRONOS — Distributed Temporal Orchestrator (backlog)
  - Perché: cron distribuito affidabile con virtual threads (Java 21).
  - Cosa fa: timing wheel, sharding logico, lease/heartbeat, DLQ, gRPC/webhooks.
- PROJECT STREAMFORGE — Elastic Media Pipeline (backlog)
  - Perché: ABR a più profili qualità con pipeline ibrida Python/C++.
  - Cosa fa: binding FFmpeg via FFI, transcodifica multi‑codec, HLS/DASH, X‑Sendfile, DRM light.
- SPECIAL — AEQUITAS (backtesting HPC), VORTEX (telepresence a bassa latenza), SENTINELLA (digital twin industriale)
  - Motori ibridi C++/Python/Web con zero‑copy, GPU e protocolli industriali.

Progetti implementati nel repo: `prog1..prog8`. Idee in backlog: CHRONOS e STREAMFORGE.

---

## Mappa rapida progetto → cartella → stack

- TITAN → `prog1/` → Go + Linux syscalls
- HYDRA → `prog2/` → Go (cluster) + Rust (engine)
- AIGIS → `prog3/` → Python (crypto/ZK, FastAPI, pytest)
- CORTEX → `prog4/` → Python (RAG, BM25, graph, reranker)
- FLUX → `prog5/` → Rust (network, QUIC, Wasm)
- PANOPTICON → `prog6/` → Python (FastAPI, TimescaleDB/PostGIS, Redis, ONNX)
- GHOSTFS → `prog7/` → C/FUSE + Rust utils
- AETHER → `prog8/` → Rust (libp2p/QUIC, tokio)

---

## Convenzioni di test e qualità

- Ogni progetto espone comandi standard di test:
  - Go: `go test ./...`
  - Python: `pytest -q` (+ coverage dove presente)
  - Rust: `cargo test`
  - C/FUSE: `make test` e `valgrind` per leak
- Stress test: cartelle `tests/`, `stress_test/` o `scripts/benchmark.sh` quando presenti.
- Lint/format (facoltativo): `ruff/black` per Python, `gofmt`/`golangci-lint` per Go, `cargo fmt/clippy` per Rust.

---

## Contributi e roadmap

- Focus: robustire i prototipi senza introdurre dipendenze superflue; prediligere semplicità e riproducibilità.
- Issue/PR benvenuti per: copertura test, documentazione, compatibilità piattaforme, rimozione footgun.
- Backlog prioritario: CHRONOS, STREAMFORGE, rafforzare journaling di GHOSTFS, overlay networking multi‑node in TITAN, Wasm ABI stabile in FLUX.


---

Sono aperto a sviluppare nuove idee /progetti,sulla base delle issue aperte