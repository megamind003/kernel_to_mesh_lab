TODO : REVISE


PROJECT AETHER: Sovereign Data Mesh (P2P Synchronization)
Visione: Il Cloud è il computer di qualcun altro. Aether riporta i dati a casa. È un protocollo di sincronizzazione bidirezionale, Device-to-Device, che bypassa completamente i datacenter centralizzati. Deve essere più veloce di Dropbox (perché trasferisce via LAN quando possibile) e più sicuro di Signal (perché i file sono tuoi). La filosofia è "Offline First": i dispositivi si sincronizzano quando si vedono, e risolvono i conflitti quando si riconnettono.

1. The Connectivity Mesh (Libp2p & NAT Traversal)
Il problema numero uno del P2P è: "Come ti parlo se non hai un IP pubblico?".

ICE & Hole Punching:

Implementazione aggressiva di UDP Hole Punching per bucare i NAT domestici.

Integrazione di server STUN (pubblici) e TURN (relay privati di fallback) solo se la connessione diretta fallisce.

Multi-Layer Discovery:

Local (L2): Uso di mDNS (Multicast DNS) per scoprire peer sulla stessa rete Wi-Fi istantaneamente.

Global (L3): Partecipazione a una DHT Kademlia (Distributed Hash Table) globale. Ogni nodo annuncia: "Io possiedo il device ID xyz". Quando il tuo laptop cerca il tuo desktop, chiede alla DHT: "Chi ha l'IP corrente di xyz?".

Circuit Relays v2: Se due nodi sono dietro NAT simmetrici "cattivi", Aether deve negoziare un tunnel cifrato attraverso un nodo terzo volontario, mantenendo la crittografia End-to-End.

2. The Sync Engine (Merkle DAGs & Rolling Hashes)
Non trasferire mai lo stesso byte due volte.

Content Addressing (Like Git):

I file non sono identificati dal percorso (/docs/file.txt), ma dall'hash del loro contenuto (QmHash...).

Costruzione di un Merkle DAG (Directed Acyclic Graph). Una cartella è un nodo che punta agli hash dei file. Se modifichi un file profondo, l'hash della radice cambia. Questo permette di confrontare intere directory di Terabyte scambiando solo l'hash della radice (pochi byte).

Rolling Hashes (Rabin Fingerprinting):

Per i file grandi, non usare chunk fissi (4MB). Se inserisco un byte all'inizio del file, tutti i chunk successivi cambierebbero hash (Disaster!).

Uso di Content-Defined Chunking. L'algoritmo taglia il file in punti basati sul contenuto. Se aggiungo un byte, cambia solo UN chunk. Il resto del file rimane identico e non viene ritrasmesso.

Delta Transfer: Quando viene rilevata una modifica, il protocollo scambia solo i chunk mancanti ("Block Exchange Protocol", simile a BitTorrent).

3. The Async Runtime (Tokio & Multiplexing)
Rust deve brillare qui.

Stream Multiplexing (Yamux/QUIC):

Non aprire 100 connessioni TCP per 100 file. Usa una singola connessione fisica (meglio se su QUIC/UDP) e apri migliaia di "stream leggeri" logici al suo interno.

Evitare l'Head-of-Line Blocking: Se un pacchetto di un file viene perso, gli altri file continuano a scaricare senza aspettare la ritrasmissione.

Backpressure Management: Se il disco è lento a scrivere ma la rete è veloce, il sistema non deve esplodere in RAM. Implementare meccanismi di backpressure reattiva attraverso i canali asincroni di Tokio (mpsc::channel).

4. Conflict Resolution (Vector Clocks)
Cosa succede se modifico "Note.txt" sul Laptop e sul Desktop mentre sono offline?

Version Vectors:

Ogni file porta con sé un metadato logico: [Laptop: 5, Desktop: 3].

Quando i nodi si incontrano, confrontano i vettori.

Se V1 > V2 -> Aggiornamento automatico.

Se V1 e V2 sono divergenti (Concurrent Edit) -> Conflict Branch. Il sistema non sovrascrive nulla. Rinomina i file in Note (Laptop).txt e Note (Desktop).txt e notifica l'utente ("Human Intervention Required"). Niente perdita di dati silenziosa.

5. Security & Identity (The Noise Protocol)
Crypto Handshake:

Uso del framework Noise Protocol (lo stesso di WireGuard) per stabilire la sessione. È più leggero e moderno di TLS.

Mutual Authentication: Non esistono server e client. Entrambi i nodi si autenticano crittograficamente usando le loro chiavi pubbliche Ed25519.

Untrusted Relays: Anche se il traffico passa attraverso un server Relay, il Relay vede solo rumore cifrato. Non può sapere chi sta parlando con chi né cosa si dicono (metadati minimi).

Livello di Difficoltà:

Networking: Estremo. Scrivere un'implementazione QUIC o gestire il NAT Traversal manuale in Rust richiede una comprensione profonda dello stack TCP/IP.

Concorrenza: Alta. Gestire lock su file system, channel asincroni e state machine distribuite senza causare Panic o Deadlock.

Algoritmica: Alta. Implementare Rabin Fingerprinting efficiente e gestione dei Merkle Tree.

Obiettivo Finale: Avviare aether su un server a New York e su un Raspberry Pi a Roma (dietro NAT casalingo). Modificare un file ISO da 4GB a New York. Vedere il Raspberry Pi iniziare a ricevere i dati istantaneamente perforando il firewall, saturando la banda disponibile, e verificando crittograficamente ogni singolo blocco ricevuto. Staccare la spina a metà, riattaccarla e vederlo riprendere esattamente dall'ultimo byte.