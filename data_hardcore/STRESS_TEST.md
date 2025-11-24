
 TABLE 1: DATA-INTENSIVE PROJECTS
File Progetto,Nome Progetto,Materiale (Percorso Relativo),Protocollo di Test (The Gauntlet)
prog2.md,HYDRA (Distributed KV Store),btcusd_1-min_data.csv (366MB),"Test ""Write Storm"": Ingerire il CSV riga per riga simulando un feed di borsa. La chiave è il Timestamp, il Valore è il JSON della riga.  Pass Criteria: Il DB deve scrivere su disco usando LSM-Trees senza bloccare le letture quando la MemTable viene flushata."
prog3.md,AIGIS (ZK Voting),emails.csv (1.4GB),"Test ""Merkle Scale"": Estrarre tutti i mittenti univoci (colonna From). Costruire un Merkle Tree gigante. Generare una ZK-Proof di appartenenza per l'email vincent.kaminski@enron.com.  Pass Criteria: Tempo di generazione prova < 3s."
prog4.md,CORTEX (Local RAG),emails.csv (1.4GB),"Test ""Needle in Haystack"": Indicizzare il corpo delle email. Chiedere all'LLM locale: ""Cosa discutevano riguardo il progetto Raptor nel 2001?"".  Pass Criteria: Il sistema deve recuperare le email corrette semanticamente in < 200ms."
prog6.md,PANOPTICON (Fraud Detection),creditcard.csv (144MB),"Test ""Latency Spike"": Leggere il CSV e sparare le transazioni all'API.  Pass Criteria: Latenza P99 < 50ms anche durante i picchi di traffico. Nessun False Negative sulle righe con Class=1."
prog7.md,GHOSTFS (Steganography),archive/all_images/images/*.png (Cellule) + alpine-minirootfs... (Payload),"Test ""Invisible Ink"": Iniettare il file Alpine (3.5MB) distribuendolo nei bit meno significativi delle immagini PNG delle cellule (che hanno alto rumore visivo).  Pass Criteria: Hash MD5 del file estratto identico all'originale. Immagini visibilmente inalterate."
prog9.md,CHRONOS (Job Scheduler),creditcard.csv (144MB),"Test ""Time Bomb"": Usare la colonna Time come delay relativo (secondi da ora). Inserire 284k job nella Timing Wheel.  Pass Criteria: I job vengono eseguiti nell'ordine esatto senza uccidere il DB con query di polling."
prog10.md,STREAMFORGE (Video Streaming),tearsofsteel_4k.mov (6.3GB),"Test ""Transcoding Furnace"": Avviare la transcodifica ABR (1080p, 720p, 480p) in parallelo.  Pass Criteria: CPU Usage al 100%, ma nessun frame droppato. Generazione corretta dei segmenti .ts e playlist .m3u8."
| SPECIAL_1.MD | **AEQUITAS** (HFT Engine) | `btcusd_1-min_data.csv` (366MB) | **Test "Quantum Speed":** Caricare il CSV in RAM (mmap) e calcolare una Simple Moving Average (SMA) su 1 milione di candele. <br> **Pass Criteria:** Tempo di esecuzione < 50ms in C++ puro (con SIMD AVX2). |


 TABLE 2: NETWORK & INFRASTRUCTURE PROJECTS
 File Progetto,Nome Progetto,Materiale (Percorso Relativo),Protocollo di Test (The Gauntlet)
prog5.md,FLUX (Load Balancer),archive/all_images/images/*.png,"Test ""Zero-Copy"": Servire i file PNG statici attraverso FLUX. Monitorare la RAM con htop.  Pass Criteria: RAM piatta (pochi MB) indipendentemente dalla dimensione del file servito (uso corretto di sendfile syscall)."
prog8.md,AETHER (P2P Sync),1. alpine-minirootfs... (Small)2. tearsofsteel_4k.mov (Huge),Test 1 (Ping): File piccolo trasferito in < 100ms.Test 2 (Resume): Iniziare trasferimento del video 6GB. Staccare cavo/killare processo al 40%. Riavviare.  Pass Criteria: Il download riprende dal 40% verificando solo i chunk hash.
| prog1.md | **TITAN** (Container Orch.) | `alpine-minirootfs...tar.gz` | **Test "Jailbreak":** Scompattare il rootfs in una cartella temporanea. Lanciare un processo `sh` isolato (namespaces). <br> **Pass Criteria:** Eseguendo `ps aux` dentro il container, devo vedere solo il processo `sh` e non i processi dell'host. |
SPECIAL_2.md,VORTEX (Pixel Streaming),Unigine_Heaven-4.0/bin/heaven,"Test ""GPU Capture"": Lanciare l'eseguibile Heaven. Il server deve agganciare la finestra X11/Win32.  Pass Criteria: Streaming video a 60fps nel browser con latenza input < 30ms."
SPECIAL_3.md,SENTINELLA (Digital Twin),Drill_01_4k.blend/textures/ + DamagedHelmet.glb,"Test ""Asset Loading"": Caricare il modello e le texture 4K nel visualizzatore WebGL.  Pass Criteria: Rendering fluido, sincronizzazione rotazione via WebSocket a 60Hz."


TABLE 3: AI & OLLAMA CONFIGURATION (The Brain)
API Endpoint: http://localhost:11434

Ruolo,Modello (Tag),VRAM Stimata,Configurazione Test
Inference (Chat/Reasoning),llama3.2:3b,~2.2 GB,"Context Window: 8192  Temperature: 0.1 (Vogliamo determinismo, non creatività)"
Embedding (Vector Search),nomic-embed-text,~0.3 GB,Batch Size: 512 (Per ingestione veloce di emails.csv)



NOTE TECNICHE PER LO SVILUPPO
Percorsi Assoluti: Quando configuri i progetti, usa sempre il path assoluto per evitare errori: /home/boss/Documents/prog/data_hardcore/...

Video:
tearsofsteel_4k.mov è un file pesante. Non provare a caricarlo tutto in RAM. Va streamato dal disco.

Immagini:
Le immagini in archive/all_images/images/ sono file PNG pesanti (~5MB l'uno) di microscopia. Sono perfetti per testare il carico di memoria e la steganografia perché hanno un'altissima entropia (molto rumore/dettaglio), rendendo difficile notare le modifiche ai bit.


AI STRESS PROTOCOLS
1. PROJECT CORTEX (Local RAG) - prog4.md

Materiale: emails.csv (1.4GB).

Setup:

Assicurarsi che Ollama stia girando: curl http://localhost:11434/api/tags.

Ingerire le prime 10.000 righe del CSV.

Chunking: 512 token con overlap 50.

Vettorizzare con nomic-embed-text.

Test "The Needle":

Query: "Chi ha inviato l'email riguardante il 'Raptor Project' e in che data?" (Nota: cerca un dettaglio specifico nascosto nel dataset Enron).

Check: La risposta deve contenere il nome corretto (es. Vincent Kaminski o simili) e la data.

Test "VRAM Pressure":

Mentre risponde, apri un'altra finestra di terminale e lancia watch -n 0.5 nvidia-smi.

Pass Criteria: La memoria GPU non deve mai superare i 9.5 GB (lasciare 500MB per il display). Se va in swap sulla RAM di sistema, il test è fallito (bisogna ridurre la context window o il batch size).

2. PROJECT PANOPTICON (ML Inference) - prog6.md

Nota: Questo progetto usa Python nativo (scikit-learn/XGBoost) e non Ollama, per mantenere la latenza < 10ms.

Test: Allenare IsolationForest su creditcard.csv.

Check: L'inferenza (predizione 0/1) su una singola riga deve impiegare < 5 millisecondi. Non usare LLM per questo task!


LA PASSWORD PER ESEGUIRE SUDO CON UTENTE boss, e' :
boss


