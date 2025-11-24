PROJECT TITAN: Distributed Container Fabric & Orchestration Kernel
Visione: Non stiamo costruendo un semplice "lanciatore di script" o un clone di Docker. Stiamo costruendo un Sistema Operativo per Data Center. L'obiettivo è astrarre completamente l'hardware sottostante (CPU, RAM, Network) e presentarlo all'utente come un'unica, gigantesca macchina virtuale programmabile. Il sistema deve trattare i server fisici come bestiame sacrificabile (cattle), non come animali domestici (pets). Se un server muore, Titan se ne accorge e sposta il carico altrove in millisecondi.

1. The Core Runtime (The "Cell")
Il cuore del sistema è un motore di isolamento puro che dialoga direttamente con il Kernel Linux tramite Syscalls.

Isolamento Totale (Namespaces):

Implementazione manuale di clone(2) con flag specifici: CLONE_NEWPID (processi isolati), CLONE_NEWNS (mount points privati), CLONE_NEWNET (stack di rete isolato), CLONE_NEWUTS (hostname separato).

Pivot Root: Utilizzo di pivot_root per "ingabbiare" il processo dentro il file system Alpine Linux (o altro rootfs), impedendogli di vedere il file system dell'host.

Resource Governance (Cgroups v2):

Utilizzo rigoroso di Control Groups v2 via sysfs.

Il sistema deve poter imporre limiti hard: "Questo container non userà più di 512MB di RAM e il 20% di un Core CPU".

OOM Handling: Se un processo sfora, Titan deve intercettare l'evento e decidere se ucciderlo o riavviarlo, senza destabilizzare l'host.

Storage a Strati (OverlayFS):

Supporto nativo per OverlayFS. Il container parte da un'immagine base read-only (es. Alpine) e scrive su un layer effimero superiore read-write.

Al termine del container, il layer effimero viene distrutto (o committato se richiesto).

2. The Nervous System (Software Defined Networking)
Qui abbandoniamo la semplicità. Il networking deve essere virtuale e distribuito.

Virtual Ethernet Pairs (veth):

Creazione dinamica di coppie veth. Un capo (eth0) viene spostato nel namespace del container, l'altro (vethXXXX) viene agganciato a un bridge virtuale (cni0) sull'host.

IP Address Management (IPAM):

Un modulo interno che assegna IP univoci da una subnet privata (es. 10.244.0.0/16) a ogni container, garantendo che non ci siano collisioni nel cluster.

Overlay Network (Multi-Node):

Se due container sono su server fisici diversi, devono parlarsi. Implementare un tunnel VXLAN o incapsulamento WireGuard automatico tra i nodi per creare una rete "piatta" sopra la rete fisica.

3. The Brain (Cluster Orchestration & Consensus)
Il sistema deve tollerare il fallimento.

Distributed State Machine:

Lo stato del cluster (chi sta eseguendo cosa) non può stare in memoria. Serve un Distributed Key-Value Store implementato internamente (basato su Raft Consensus Algorithm).

Tutti i nodi "Manager" devono concordare sulla "verità" (Consenso).

Scheduler Intelligente (The Planner):

Quando l'utente lancia un job, lo scheduler analizza il carico di tutti i nodi e applica algoritmi di Bin Packing: "Il nodo A ha poca RAM libera, il nodo B ha poca CPU. Metto il container sul nodo C".

Self-Healing Loop:

Un ciclo di controllo infinito che confronta lo stato desiderato (es. "voglio 3 copie di Nginx") con lo stato attuale. Se ne trova 2, ne avvia una nuova. Se ne trova 4, ne uccide una.

4. Sicurezza & Hardening (Paranoia Mode)
Seccomp Filtering:

Bloccare le chiamate di sistema (syscalls) pericolose tramite profili BPF. Un container web non dovrebbe mai poter fare una chiamata reboot, swapon o caricare moduli kernel.

Capability Dropping:

Rimuovere i privilegi di root granulari (es. CAP_NET_ADMIN, CAP_SYS_BOOT) prima di eseguire il payload utente, anche se l'utente "pensa" di essere root (uid 0).

5. Interfaccia & Telemetria
API Server: Tutto il sistema è pilotabile via API RESTful o gRPC. La CLI (titan-cli) è solo un client stupido.

Log Streaming: Un sistema che permette di vedere "live" l'output stdout/stderr di un processo isolato, leggendo i file pipe dal filesystem virtuale /proc dell'host.

La Complessità (The Hard Part)
Interazione a basso livello con il kernel Linux (non puoi usare librerie che lo fanno per te).

Gestione della concorrenza e race conditions nel networking (creare e distruggere interfacce di rete mentre i pacchetti fluiscono).

Debuggare processi che "non esistono" nel tuo namespace.

Stack Consigliato
Linguaggio: Go (Golang) o Rust.

Librerie: Solo la standard library per le syscall (syscall package in Go, nix in Rust). Niente libcontainer o runc.

Target: Linux Kernel 5.x+.

Obiettivo Finale (The Test)
Lanciare un comando titan run --replicas=5 --memory=64MB nginx:alpine. Staccare brutalmente il cavo di rete a due server fisici. Vedere il traffico HTTP continuare a fluire senza interruzioni mentre Titan rileva i nodi morti e riprogramma istantaneamente i container persi sui nodi sopravvissuti.