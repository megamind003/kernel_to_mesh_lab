ROJECT FLUX: The Hyper-Scale Traffic Engine
Visione: NGINX è vecchio. HAProxy è complesso. Noi stiamo costruendo FLUX, un Edge Proxy di nuova generazione progettato per l'era del Cloud Native. Non è solo un passacarte per pacchetti TCP. FLUX è un sistema operativo di rete programmabile. Deve poter gestire 100.000 richieste al secondo (RPS) su un singolo core, terminare SSL in modo trasparente e permettere all'utente di iniettare logica di routing complessa (via WebAssembly) senza mai riavviare il processo.

1. The Reactor Core (Async I/O & Threading Model)
Il modello "un thread per connessione" (Apache style) è morto. FLUX deve essere totalmente non-bloccante.

Thread-per-Core Architecture (Shared-Nothing):

Se la CPU ha 8 core, lanciamo 8 worker thread inchiodati (pinned) ai core fisici.

Nessun lock (mutex) condiviso tra i thread. Ogni thread ha il suo Event Loop, la sua memoria e le sue code. Questo elimina il Context Switching e la Cache Thrashing.

Modern Kernel Polling:

Uso diretto di io_uring (su Linux moderno) per sottomettere operazioni di I/O in batch al kernel senza overhead di syscall multiple. Fallback su epoll (Linux) o kqueue (BSD/macOS).

Zero-Copy Data Path: Spostare i dati dalla scheda di rete (NIC) al socket di backend senza mai copiarli nello spazio utente (User Space) se non strettamente necessario per l'ispezione.

2. The Protocol Polyglot (HTTP/2, gRPC & QUIC)
Gestire HTTP/1.1 è facile. La vera sfida è il multiplexing.

Binary Framing Layer (HTTP/2):

Implementare una macchina a stati finiti per decodificare i frame binari.

Gestire centinaia di "stream" virtuali su una singola connessione TCP.

Flow Control: Gestire le finestre di ricezione per evitare che un client veloce inondi un backend lento.

QUIC & HTTP/3 (The UDP Challenge):

Implementare il trasporto su UDP. Qui non c'è il Kernel che ti aiuta con l'handshake TCP e la congestione. Devi implementare algoritmi di Congestion Control (es. CUBIC o BBR) nello spazio utente.

gRPC Transcoding: Capacità di ricevere una chiamata gRPC (binaria) e tradurla al volo in JSON per un backend legacy (e viceversa).

3. The Brain (Wasm Extension System)
I file di configurazione statici (flux.yaml) non bastano. Vogliamo logica dinamica.

WebAssembly (Wasm) Runtime:

Integrare un runtime leggero (es. Wasmtime o V8).

Permettere agli utenti di scrivere filtri in Rust, Go o C++, compilarli in .wasm e caricarli a caldo su FLUX.

Esempio di plugin: "Se l'header User-Agent è iPhone E l'orario è > 18:00, manda la richiesta al server beta-cluster e aggiungi un header di tracciamento".

Sandboxing: Se il codice Wasm dell'utente crasha o va in loop infinito, FLUX deve uccidere solo quella richiesta, non l'intero processo server.

4. Resilience Engineering (Circuit Breaking & Shedding)
Proteggere i backend è importante quanto servire i client.

Adaptive Load Shedding:

Se la latenza media dei backend sale sopra i 500ms, FLUX inizia a scartare preventivamente le richieste meno prioritarie (es. quelle dei bot) per dare ossigeno ai server.

Outlier Detection:

FLUX monitora statisticamente tutti i nodi di backend. Se un nodo restituisce errori 5xx più spesso della media (deviazione standard), viene espulso temporaneamente dal pool (Passive Health Checking), anche se risponde ai Ping.

Global Rate Limiting: Implementare un algoritmo Token Bucket o Leaky Bucket distribuito (usando Redis o crdt in memoria) per limitare gli abusi API.

5. The TLS Fortress
Hot-Reloading dei Certificati: Cambiare i certificati SSL scaduti senza chiudere le connessioni attive (socket migration).

SNI (Server Name Indication) Parsing: Leggere il primo pacchetto dell'handshake TLS per capire quale dominio il client vuole, prima di decifrare il traffico, per scegliere il certificato giusto.

Obiettivo Finale: Creare un binario singolo di 20MB che puoi piazzare davanti a un cluster morente e vederlo stabilizzare il traffico, proteggere dagli attacchi e instradare milioni di pacchetti con un utilizzo CPU ridicolo. Capirai perché aziende come Cloudflare e Amazon AWS dominano il mondo.