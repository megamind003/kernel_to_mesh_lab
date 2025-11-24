# **PROJECT TITAN: Distributed Container Fabric & Orchestration Kernel**

**"Treat servers like cattle, not pets."**

## **1\. Visione & Obiettivo**

**Titan** è un'implementazione educativa e sperimentale di un **Container Runtime** e di un **Orchestrator**, scritto da zero in Go. L'obiettivo non è competere con Docker o Kubernetes, ma demistificare la "magia" dei container interagendo direttamente con le primitive del kernel Linux senza intermediari (nessuna dipendenza da runc o containerd).

Titan astrae l'hardware sottostante creando "Celle" (container) isolate, governate rigidamente e connesse tramite una rete definita dal software.

## **2\. Architettura del Sistema (Code Analysis)**

Il progetto è modulare e ogni package in pkg/ gestisce una responsabilità specifica del ciclo di vita del container.

### **I. The Core Runtime (pkg/container)**

Il cuore pulsante di Titan. Non usa librerie esterne per la creazione dei container, ma invoca direttamente le syscall.

* **Isolamento (Namespaces)**: Utilizza syscall.SysProcAttr con flag CLONE\_NEWPID (processi), CLONE\_NEWNS (mount), CLONE\_NEWUTS (hostname) e CLONE\_NEWNET (rete) per creare uno spazio utente isolato.  
* **Jail (Pivot Root)**: In container.go, la funzione RunParent prepara l'ambiente e poi esegue una pivot\_root syscall per intrappolare il processo all'interno del rootfs, rendendo il file system dell'host inaccessibile.  
* **Storage (OverlayFS)**: Il modulo overlay.go implementa un filesystem Copy-On-Write.  
  * **LowerDir**: L'immagine base read-only (es. busybox).  
  * **UpperDir**: Il layer scrivibile effimero del container.  
  * **WorkDir**: Directory tecnica necessaria per l'atomicità di OverlayFS.  
  * **MergedDir**: Il punto di mount finale visto dal container.

### **II. Resource Governance (pkg/cgroups)**

Titan protegge l'host dal "Noisy Neighbor effect" utilizzando **Cgroups v2** (/sys/fs/cgroup).

* **Memory Controller**: Scrive limiti rigidi in memory.max per prevenire OOM dell'host.  
* **PIDs Controller**: Limita il numero di processi tramite pids.max per prevenire fork bombs.  
* **Procs Management**: I processi vengono migrati nel cgroup scrivendo il loro PID in cgroup.procs.

### **III. The Nervous System (pkg/network)**

Gestisce la connettività locale del container.

* **Bridge (Titan0)**: Crea un bridge virtuale Linux (titan0) che funge da switch software.  
* **Veth Pairs**: Crea coppie di interfacce virtuali. Un'estremità resta all'host collegata al bridge, l'altra viene spostata nel namespace del container e rinominata eth0.  
* **IP Management**: Assegna staticamente IP dalla subnet 172.18.0.0/16 basandosi su un calcolo deterministico.  
* **NAT/Masquerade**: Configura regole iptables (POSTROUTING) per permettere ai container di uscire su internet tramite l'interfaccia dell'host.

### **IV. The Brain (pkg/cluster & pkg/scheduler)**

*Attualmente in stadio di prototipo.*

* **Raft Consensus**: raft.go contiene le strutture dati per un log distribuito (LogEntry, RaftNode), ma l'implementazione attuale agisce in "Single Node Mode", committando le entry immediatamente in memoria.  
* **Scheduler**: scheduler.go implementa un algoritmo **First Fit** con controllo di affinità. Verifica se un nodo ha abbastanza RAM/PID liberi prima di assegnare un Job.  
* **Telemetry**: telemetry.go implementa un Event Bus interno (Pub/Sub) per trasmettere eventi come ContainerStarted o NodeJoined.

## **3\. Struttura del Progetto**

.  
├── cmd  
│   └── main.go              \# Entry point CLI (parsing flags, init subsystems)  
├── pkg  
│   ├── cgroups  
│   │   └── cgroups.go       \# Gestione gerarchia Cgroups v2  
│   ├── cluster  
│   │   └── raft.go          \# Strutture dati per il consenso distribuito  
│   ├── container  
│   │   ├── container.go     \# Logica Syscalls (Clone, Namespaces, PivotRoot)  
│   │   └── overlay.go       \# Gestione mount OverlayFS  
│   ├── network  
│   │   └── network.go       \# Configurazione Bridge, Veth e IP routing  
│   ├── scheduler  
│   │   └── scheduler.go     \# Logica di piazzamento dei carichi  
│   └── telemetry  
│       └── telemetry.go     \# Bus eventi interno  
├── setup\_rootfs.sh          \# Script per generare l'immagine base (Busybox)  
└── go.mod

## **4\. Guida all'Uso**

Poiché Titan interagisce a basso livello con il kernel, richiede privilegi di **root** e un sistema Linux moderno.

### **Prerequisiti**

1. Linux Kernel 5.4+ (per Cgroups v2).  
2. iptables installato (per il NAT).  
3. Go 1.18+ installato.

### **1\. Preparazione RootFS**

Prima di eseguire qualsiasi container, è necessario creare un filesystem di base (rootfs). Titan include uno script per scaricare e configurare busybox.

chmod \+x setup\_rootfs.sh  
sudo ./setup\_rootfs.sh  
\# Output: Base Image created at /tmp/titan/images/busybox

### **2\. Compilazione**

Compila il binario statico.

go build \-o titan cmd/main.go

### **3\. Esecuzione (Run)**

Lancia un container isolato. Titan creerà i namespace, limiterà le risorse e configurerà la rete.

Sintassi:  
sudo ./titan run \--memory \<bytes\> \--pids \<max\_procs\> \<comando\>  
Esempio:  
Avvia una shell (sh) isolata con massimo 50MB di RAM e 20 processi:  
sudo ./titan run \--memory 52428800 \--pids 20 /bin/sh

All'interno del container, puoi verificare l'isolamento:

/ \# ps aux        \# Vedrai solo PID 1 (sh) e ps  
/ \# ip addr       \# Vedrai l'interfaccia eth0 con IP 172.18.x.x  
/ \# hostname      \# Vedrai un hostname isolato

## **5\. Dettagli Interni: Cosa succede al run?**

Quando esegui il comando run, il flusso (cmd/main.go) è il seguente:

1. **Init**: Generazione ID container e inizializzazione Bus Telemetria.  
2. **Storage**: OverlayManager monta busybox (Read-Only) \+ upper (Read-Write) in /merged.  
3. **Network Prep**: SetupBridge assicura che titan0 esista e configura il NAT.  
4. **Process Creation**: RunParent chiama /proc/self/exe con argomento child.  
5. **Kernel Magic (Il processo figlio)**:  
   * Viene clonato con nuovi Namespace.  
   * **Cgroups**: Il processo si auto-aggiunge ai gruppi di limitazione risorse.  
   * **Network Setup**: Configura l'IP e la rotta di default dentro il nuovo namespace.  
   * **Pivot Root**: Scambia / con la directory /merged di OverlayFS.  
   * **Exec**: Sostituisce il binario di Titan con il comando utente (es. /bin/sh).  
6. **Cleanup**: Alla chiusura della shell, il defer in main smonta OverlayFS e pulisce le risorse.

## **6\. Limitazioni Attuali & Roadmap**

* **Networking**: Il networking Multi-Node (Overlay VXLAN) non è ancora implementato. Attualmente i container possono parlare solo con l'host e internet.  
* **Rootless**: Richiede obbligatoriamente sudo per manipolare namespaces e cgroups.  
* **Consensus**: Il modulo Raft è una struttura logica (mock) e non replica ancora i dati via rete tra nodi multipli.

