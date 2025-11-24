TODO : REVISE

PROJECT GHOSTFS: The Plausible Deniability Filesystem
Visione: La crittografia standard (come VeraCrypt o LUKS) ha un problema: se qualcuno vede un file crittografato di 10GB, sa che nascondi qualcosa. Ti possono costringere a dare la password. GhostFS offre la "Plausible Deniability". Il tuo hard disk contiene solo una cartella piena di foto delle vacanze (/home/user/photos). Nient'altro. Ma se monti quella cartella con GhostFS e la chiave corretta, appare un drive virtuale (/mnt/ghost) con documenti segreti. I dati sono frammentati e nascosti nei bit di rumore delle immagini. Agli occhi di un'analisi forense standard, quelle sono solo normali JPEG.

1. The Carrier Allocator (Bitmap over Bitmaps)
Un Filesystem normale scrive su blocchi del disco (settori). GhostFS scrive su pixel.

Carrier Discovery: All'avvio, il sistema scansiona ricorsivamente una directory "Host" (es. la tua cartella Immagini). Analizza ogni file (JPEG, PNG, WAV) e calcola la sua "Capacity" (quanti bit possiamo nascondere senza degradare visibilmente l'immagine).

Virtual Block Device: Devi astrarre i file immagine.

Il Block 0 del filesystem virtuale potrebbe essere i primi 512 byte nascosti dentro IMG_001.jpg.

Il Block 1 potrebbe essere dentro IMG_002.png.

Il Block 2 potrebbe essere diviso a metà tra IMG_002.png e audio_01.wav.

Fragment Manager: Devi mantenere una "Mappa di Allocazione" in RAM che dice: "I byte dal 0 al 4096 del file segreto passwords.txt si trovano sparsi nei pixel [100-5000] dell'immagine A e nei pixel [0-200] dell'immagine B".

2. The FUSE Bridge (User-Space Kernel Interface)
Devi implementare l'interfaccia struct fuse_operations di libfuse.

Intercepting Syscalls:

Quando l'utente fa cat /mnt/ghost/segreto.pdf, il kernel chiama la tua funzione ghost_read().

La tua funzione deve:

Calcolare in quali immagini "reali" si trovano i pezzi del file.

Aprire le immagini reali con fopen.

Estrarre i bit (decodifica LSB).

Riassemblare il buffer.

Decifrarlo (AES).

Restituirlo al kernel.

Tutto questo deve avvenire in microsecondi per non bloccare il sistema.

3. The Stealth Crypto Layer (AES-XTS & Argon2)
Non basta nascondere i bit. I bit nascosti devono sembrare rumore casuale.

Encryption First: I dati vengono prima cifrati con AES-256 in modalità XTS (standard per la disk encryption).

Key Derivation: La password dell'utente viene passata attraverso Argon2id (memory-hard function) per rendere impossibile il brute-force.

Whitening: Se scrivi dati cifrati (che hanno alta entropia) in un'immagine che ha bassa entropia (es. un cielo blu uniforme), la modifica si vede statisticamente ("Steganalysis").

Advanced: Implementare algoritmi che scrivono solo nelle zone "rumorose" dell'immagine (bordi, texture complesse) saltando le zone uniformi. Questo richiede di implementare un allocatore non-lineare.

4. The Metadata Problem (The Inode Table)
Dove salviamo i nomi dei file, i permessi e le date? Non possiamo creare un file index.db visibile.

Hidden Superblock: Le strutture dati del filesystem (Inode Table, Directory Entries) devono essere serializzate e nascoste anch'esse distribuite tra le prime N immagini della cartella.

B-Tree Serialization: Devi scrivere un motore che serializza un B-Tree (che mappa i nomi file ai blocchi logici) in un flusso di bit, lo cifra e lo inietta nelle immagini. Se perdi l'immagine che contiene la radice del B-Tree, perdi tutto il filesystem.

Atomicità: Cosa succede se crasha il PC mentre stai aggiornando l'albero delle directory? Rischi di corrompere il filesystem nascosto rendendolo irrecuperabile. Serve un meccanismo di Journaling (anch'esso nascosto).

5. The Hardest Part: Memory & Reliability
Stiamo lavorando in C puro.

Pointer Arithmetic Hell: Gestire buffer che rappresentano pixel RGB (unsigned char *), buffer che rappresentano blocchi cifrati, e buffer che rappresentano file in chiaro. Un errore di +1 nell'aritmetica dei puntatori e scrivi spazzatura nell'immagine, corrompendola visibilmente.

Host File Modification: Se l'utente apre la cartella reale e ruota una foto o la ridimensiona con Photoshop, i dati nascosti dentro vengono distrutti.

Il sistema deve implementare Checksum (CRC32 o SHA256) per ogni blocco dati.

Durante la lettura, se il checksum fallisce, GhostFS deve restituire un errore di I/O (o tentare di recuperare i dati da codici di correzione errore Reed-Solomon, se sei abbastanza folle da implementarli).

Livello di Difficoltà:

System Programming: Estremo. FUSE richiede una gestione perfetta della concorrenza (il kernel può lanciare più richieste read in parallelo).

Algoritmica: Alta. Mappare un filesystem logico continuo su un supporto fisico frammentato e rumoroso (immagini di dimensioni diverse) è un incubo di bookkeeping.

Debugging: Incubo. Non puoi "vedere" i dati. Se qualcosa non va, ottieni solo "Segfault" o file corrotti. GDB e Valgrind saranno i tuoi unici amici.

Obiettivo Finale: Montare GhostFS. Copiare un video di 500MB dentro /mnt/ghost. Vedere il sistema "spalmare" invisibilmente quei 500MB modificando impercettibilmente 2000 foto nella tua cartella immagini reale. Smontare. Aprire le foto: sembrano identiche. Rimonatare: il video è lì e si riproduce.