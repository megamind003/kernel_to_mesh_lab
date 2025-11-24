PROJECT VORTEX: low-Latency Telepresence Engine
Visione: I computer locali stanno morendo. Il futuro è il "Cloud PC". Vortex è un motore di Pixel Streaming ad alte prestazioni. A differenza di RDP o VNC (che inviano comandi di disegno o bitmap lente), Vortex cattura il framebuffer della GPU server, lo codifica in hardware e lo spara via UDP al browser. L'obiettivo è permettere a un Chromebook da 200€ di far girare Cyberpunk 2077 o AutoCAD in 4K a 60fps.

1. The Application Host (C# & Win32 API Hooks)
Il cervello dell'operazione. C# (.NET 8) gestisce il sistema operativo.

DirectX/DXGI Capture:

Non usare GDI (Graphics.CopyFromScreen), è troppo lento.

Usa le API Desktop Duplication di Windows (DXGI). Questo ti permette di ottenere la texture dello schermo direttamente dalla memoria video (VRAM) prima che venga mostrata sul monitor.

Input Injection (Low Level):

Ricevi pacchetti input dal browser via rete.

Usa SendInput (Win32 API) o scrivi un Virtual HID Driver (livello kernel) per simulare mouse e tastiera. Se il gioco usa DirectX per leggere il mouse (Raw Input), i metodi standard di iniezione falliranno. Il driver virtuale è l'unico modo per essere "indistinguibili" da un mouse fisico.

Audio Loopback: Catturare l'output audio del sistema (WASAPI Loopback), codificarlo in Opus e inviarlo sincronizzato col video.

2. The Encoder Core (C++ & NVENC Interop)
Il muscolo. Qui ogni microsecondo conta. Dobbiamo evitare il "Round Trip" della memoria (GPU -> CPU -> GPU).

Zero-Copy Pipeline (CUDA Interop):

Il frame catturato da C# (DXGI) è una texture DirectX.

Passiamo il puntatore di questa texture direttamente alla libreria C++ (NVENC/AMF).

Il chip encoder della GPU legge quella texture e produce pacchetti H.264/HEVC senza che i dati grezzi tocchino mai la RAM di sistema (CPU).

Solo i pacchetti compressi (pochi KB) vengono copiati in RAM per l'invio di rete.

Dynamic Bitrate Adjustment:

L'encoder non è statico. Se il client segnala perdita di pacchetti, il codice C++ deve riconfigurare l'encoder al volo (senza riavviare) per abbassare il bitrate o cambiare la quantizzazione (QP) per il frame successivo.

3. The Transport Layer (WebRTC & Python Signaling)
TCP è vietato. Se perdi un pacchetto video, non lo ritrasmetti (sarebbe già vecchio). Lo salti.

FastAPI Signaling:

Prima di iniziare lo stream, Client e Server si scambiano le informazioni SDP (Session Description Protocol) e i candidati ICE via WebSocket gestiti da Python.

WebRTC Data Channels (SCTP):

Video e Audio viaggiano su RTP (UDP).

Gli input (Mouse, Tastiera) viaggiano su Data Channels ad alta priorità.

Configurare il canale input come ordered: true ma maxRetransmits: 0. Vogliamo che i click arrivino in ordine, ma se un pacchetto di movimento mouse si perde, non vogliamo che blocchi i successivi.
4. The Client Illusion (JavaScript & Prediction)
Il browser è l'interfaccia. Ma la rete ha sempre latenza. Come nasconderla?

Client-Side Prediction (Ghost Cursor):

Se aspetti che il video torni indietro per vedere il mouse muoversi, la sensazione è di "guidare sul ghiaccio" (Input Lag).

Soluzione: Disegni il cursore del mouse locale sopra il tag <video> usando CSS/Canvas.

Nascondi il cursore reale del sistema remoto nel flusso video.

In questo modo, l'utente vede la sua mano muoversi istantaneamente (latenza zero), mentre il video sotto "insegue" il cursore con quei 20-30ms di ritardo. Il cervello accetta questo compromesso molto meglio del cursore in ritardo.

Jitter Buffer Management:

WebRTC ha un buffer automatico. Per il gaming, vogliamo buffer quasi zero.

Hackerare le statistiche di riproduzione (chrome://webrtc-internals) per forzare il browser a riprodurre i frame appena arrivano ("Low Latency Mode"), rischiando qualche glitch visivo pur di mantenere la reattività.

Livello di Difficoltà:

Gestione Memoria GPU: Estrema. Far parlare DirectX (C# capture) con CUDA (C++ encoding) condividendo le risorse senza crashare il driver video richiede competenze grafiche avanzate.

Sincronizzazione A/V: Alta. Se l'audio arriva 100ms prima del video (perché il video ci mette di più a essere codificato), l'esperienza è rovinata. Devi implementare timestamp precisi e buffer di compensazione.

Networking: Alta. Implementare un algoritmo di "Congestion Control" personalizzato (come Google Stadia) che capisce la differenza tra "la rete è intasata" e "la CPU del client è lenta a decodificare".

Obiettivo Finale: Aprire il browser su un iPad in 4G. Connettersi al server Vortex. Lanciare uno shooter frenetico (es. Doom Eternal). Mirare e sparare. La sensazione deve essere indistinguibile dal gioco che gira localmente sull'iPad, con una qualità visiva Blu-Ray e nessun ritardo percettibile tra il tocco e lo sparo.