# Catalogo delle metriche per l'analisi DSpace

Questo documento organizza le metriche attualmente estratte dai tre notebook:

- `01_db_metrics.ipynb`
- `02_solr_metrics.ipynb`
- `03_matomo_metrics.ipynb`

L'obiettivo non è soltanto censire i CSV prodotti, ma costruire una tassonomia comune utile per:

1. progettare i futuri report;
2. progettare una dashboard storica;
3. distinguere le metriche descrittive da quelle realmente utili per l'analisi;
4. individuare i punti di contatto tra PostgreSQL, Solr e Matomo.

## 1. Convenzioni generali

Le metriche sono oggi divise in due famiglie operative:

| Tipo | Significato |
| --- | --- |
| `monthly` | Metriche riferite a uno specifico `reference_month`; sono la base naturale per trend, confronti e report periodici. |
| `always` | Metriche di stato o cumulative calcolate al momento dell'esecuzione; sono utili come fotografia corrente, audit e contesto. |

Per la reportistica futura conviene trattarle in modo diverso:

- le metriche `monthly` alimentano grafici temporali e confronti mese su mese;
- le metriche `always` alimentano snapshot, controlli di qualità, inventari e indicatori di sistema.

## 2. Macro-aree comuni di indagine

Le metriche dei tre notebook possono essere ricondotte a otto grandi domande analitiche.

| Macro-area | Domanda principale | Fonti coinvolte |
| --- | --- | --- |
| Dimensione del repository | Quanto è grande e come sta crescendo il repository? | DB, in parte Solr |
| Produzione editoriale | Cosa viene caricato, da chi e dove? | DB |
| Qualità e integrità | Il repository è coerente, completo e tecnicamente sano? | DB, in parte Solr/OAI |
| Uso dei contenuti | Quali contenuti vengono consultati o scaricati? | Solr |
| Traffico web | Quante persone visitano il sito e come interagiscono? | Matomo |
| Acquisizione e provenienza | Da dove arrivano utenti e accessi? | Solr, Matomo |
| Pubblico e tecnologia | Chi visita il sito e con quali dispositivi? | Matomo |
| Attività interna e governance | Come lavorano utenti, gruppi e workflow? | DB |

Queste macro-aree sono il candidato naturale per le future sezioni di report e dashboard.

## 3. Mappa sintetica delle metriche

### 3.1 Dimensione e struttura del repository

| Metrica | Fonte | Frequenza | Uso analitico |
| --- | --- | --- | --- |
| Totale item | DB | `always` | Dimensione complessiva del repository |
| Totale community | DB | `always` | Struttura organizzativa |
| Totale collection | DB | `always` | Struttura organizzativa |
| Bitstream per collection | DB | `always` | Distribuzione del patrimonio digitale |
| Numero totale di record per core | Solr | `always` | Stato degli indici |
| Dimensione degli indici per core | Solr | `always` | Peso tecnico degli indici |
| Record OAI totali | Solr | `always` | Copertura dell'esposizione OAI |
| Record OAI nel mese | Solr | `monthly` | Variazione mensile del patrimonio esposto |

**Punti di indagine comuni**

- crescita quantitativa del repository;
- coerenza tra patrimonio in DB, indici Solr e record OAI;
- eventuali divergenze tra dimensione del repository e visibilità esterna.

### 3.2 Produzione editoriale e crescita mensile

| Metrica | Fonte | Frequenza | Uso analitico |
| --- | --- | --- | --- |
| Item caricati nel mese con bitstream e MIME type | DB | `monthly` | Volume e natura dei nuovi contenuti |
| Item caricati nel mese per submitter | DB | `monthly` | Attività dei depositanti |
| Item caricati nel mese per collection | DB | `monthly` | Collezioni più attive |
| Item caricati nel mese per lingua | DB | `monthly` | Profilo linguistico dei nuovi contenuti |
| Item modificati/caricati nel mese con timeline di workflow | DB | `monthly` | Tempi e processi editoriali |
| Dimensione media file nel mese | DB | `monthly` | Peso medio dei contenuti caricati |
| Item caricati nel mese per tipo e autore | DB | `monthly` | Profilo dei nuovi oggetti |
| Collection più attive nel mese | DB | `monthly` | Ranking di produzione |

**Punti di indagine comuni**

- quali collection crescono di più;
- quali tipi di contenuto trainano la crescita;
- se la crescita editoriale trova poi riscontro nell'uso dei contenuti.

### 3.3 Qualità, completezza e integrità del repository

| Metrica | Fonte | Frequenza | Uso analitico |
| --- | --- | --- | --- |
| Item senza handle | DB | `always` | Integrità identificativa |
| Item senza collection | DB | `always` | Completezza strutturale |
| Item con metadata mancanti | DB | `always` | Qualità descrittiva |
| Item con metadata vuoti | DB | `always` | Qualità descrittiva |
| Media metadata per item | DB | `always` | Ricchezza descrittiva |
| Item senza bitstream | DB | `always` | Completezza degli oggetti |
| Bitstream senza checksum | DB | `always` | Integrità tecnica |
| Item senza bundle `ORIGINAL` | DB | `always` | Integrità tecnica |
| Orphan metadatavalue | DB | `always` | Integrità referenziale |
| Orphan handle | DB | `always` | Integrità referenziale |
| Item con licenza non valida | DB | `always` | Conformità |
| Item con licenze multiple | DB | `always` | Ambiguità descrittiva |
| Record OAI con informazioni mancanti | Solr | `always` | Qualità dell'esposizione |
| Record OAI di item eliminati | Solr | `always` | Audit dell'indice OAI |

**Punti di indagine comuni**

- salute tecnica del repository;
- qualità minima per rendere i contenuti trovabili, riusabili e correttamente esposti;
- metriche adatte a una sezione “alert” o “to-do”.

### 3.4 Accessibilità, visibilità e licenze

| Metrica | Fonte | Frequenza | Uso analitico |
| --- | --- | --- | --- |
| Item non pubblicamente visibili | DB | `always` | Accessibilità |
| Bitstream non pubblicamente visibili | DB | `always` | Accessibilità |
| Item pubblici con bitstream non pubblici | DB | `always` | Coerenza dei permessi |
| Item sotto embargo | DB | `always` | Restrizioni temporanee |
| Distribuzione item per licenza | DB | `always` | Profilo giuridico dei contenuti |
| Licenze per collection | DB | `always` | Differenze tra collezioni |
| Licenze per resource type | DB | `always` | Differenze per tipologia |
| Download per licenza | Solr | `always` / `monthly` | Uso dei contenuti per regime di licenza |

**Punti di indagine comuni**

- quanto del patrimonio è realmente accessibile;
- se certi regimi di licenza sono associati a maggior uso;
- se esistono incoerenze tra pubblicazione dell'item e accessibilità dei file.

### 3.5 Utenti, gruppi e processi interni

| Metrica | Fonte | Frequenza | Uso analitico |
| --- | --- | --- | --- |
| Totale utenti | DB | `always` | Base utenti |
| Utenti per collection | DB | `always` | Distribuzione della responsabilità |
| Utenti attivi nel mese | DB | `monthly` | Attività recente |
| Utenti mai loggati | DB | `always` | Account inutilizzati |
| Utenti inattivi da oltre 12 mesi | DB | `monthly` | Dormienza |
| Utenti attivi negli ultimi 12 mesi | DB | `monthly` | Base utenti realmente viva |
| Totale gruppi | DB | `always` | Struttura autorizzativa |
| Gruppi vuoti | DB | `always` | Qualità della governance |
| Utenti per gruppo | DB | `always` | Distribuzione delle responsabilità |
| Gruppi submitter/workflow/admin per collection | DB | `always` | Copertura dei ruoli |
| Item in workspace | DB | `always` | Coda editoriale |
| Item in review | DB | `always` | Coda editoriale |
| Workspace item per utente | DB | `always` | Carico di lavoro |
| Workspace item per collection | DB | `always` | Carico di lavoro |
| Submission pendenti oltre 30 giorni | DB | `always` | Collo di bottiglia operativo |

**Punti di indagine comuni**

- vitalità della comunità interna;
- carichi e colli di bottiglia editoriali;
- bisogno di pulizia account o governance.

### 3.6 Uso dei contenuti e comportamento di ricerca

| Metrica | Fonte | Frequenza | Uso analitico |
| --- | --- | --- | --- |
| Totale item views | Solr | `always` | Uso complessivo dei contenuti |
| Totale bitstream downloads | Solr | `always` | Consumo complessivo |
| Totale eventi | Solr | `always` | Volume generale di attività |
| Eventi non bot | Solr | `always` | Uso umano stimato |
| Item più visti | Solr | `always` / `monthly` | Interesse sui contenuti |
| Bitstream più scaricati | Solr | `always` | Interesse sui file |
| Item più scaricati nel mese | Solr | `monthly` | Ranking mensile |
| Views per collection | Solr | `always` / `monthly` | Interesse per area |
| Downloads per collection | Solr | `always` / `monthly` | Consumo per area |
| Views per community | Solr | `always` / `monthly` | Interesse per comunità |
| Downloads per community | Solr | `always` / `monthly` | Consumo per comunità |
| Downloads per resource type | Solr | `always` / `monthly` | Uso per tipologia |
| Downloads per MIME type | Solr | `always` / `monthly` | Uso per formato |
| Rapporto views/downloads per item | Solr | `always` / `monthly` | Conversione dall'interesse al consumo |
| Totale ricerche | Solr | `always` / `monthly` | Attività di discovery |
| Dettaglio ricerche | Solr | `always` / `monthly` | Comportamento di ricerca |
| Termini più cercati | Solr | `always` / `monthly` | Domanda informativa |

**Punti di indagine comuni**

- cosa viene scoperto;
- cosa viene effettivamente consumato;
- quali collezioni o tipi di risorsa performano meglio;
- dove l'interesse non si traduce in download.

### 3.7 Traffico web, acquisizione e pubblico

| Metrica | Fonte | Frequenza | Uso analitico |
| --- | --- | --- | --- |
| Visite totali | Matomo | `always` |
| Visitatori unici per mese | Matomo | `always` |
| Azioni totali | Matomo | `always` |
| Durata media visita | Matomo | `always` / `monthly` |
| Bounce count | Matomo | `always` |
| Bounce rate | Matomo | `always` / `monthly` |
| Azioni per visita | Matomo | `always` / `monthly` |
| Massimo numero di azioni in una visita | Matomo | `always` |
| Visite nel mese | Matomo | `monthly` |
| Pageviews nel mese | Matomo | `monthly` |
| Visite dirette | Matomo | `always` / `monthly` |
| Visite da motori di ricerca | Matomo | `always` / `monthly` |
| Visite da siti web | Matomo | `always` / `monthly` |
| Visite da social network | Matomo | `always` / `monthly` |
| Visite da campagne | Matomo | `always` / `monthly` |
| Top referrer websites | Matomo | `always` / `monthly` |
| Top visited pages | Matomo | `always` / `monthly` |
| Tipologia delle page view | Matomo | `always` / `monthly` |
| Visite per paese | Matomo | `always` / `monthly` |
| Visite per città | Matomo | `always` / `monthly` |
| Visite per continente | Matomo | `always` / `monthly` |
| Visite per device type | Matomo | `always` / `monthly` |
| Visite per browser | Matomo | `always` / `monthly` |
| Visite per sistema operativo | Matomo | `always` / `monthly` |

**Punti di indagine comuni**

- quanto pubblico raggiunge il sito;
- da dove arriva;
- con quale qualità di sessione;
- quali sezioni del sito attirano maggiormente attenzione;
- come cambia nel tempo il profilo geografico e tecnologico del pubblico.

### 3.8 Qualità del traffico e rumore tecnico

| Metrica | Fonte | Frequenza | Uso analitico |
| --- | --- | --- | --- |
| Bot events | Solr | `always` / `monthly` | Rumore automatizzato |
| Bot user agents più frequenti | Solr | `always` / `monthly` | Profilo dei crawler |
| Eventi interni | Solr | `always` / `monthly` | Traffico non utente |
| Rapporto eventi interni/esterni | Solr | `always` / `monthly` | Pulizia dell'analisi |
| User agents più frequenti | Solr | `always` / `monthly` | Diagnostica accessi |
| IP/DNS più frequenti | Solr | `always` / `monthly` | Diagnostica accessi |
| Accessi da motori di ricerca | Solr | `always` / `monthly` | Provenienza discovery |

**Punti di indagine comuni**

- distinguere il comportamento umano da quello automatico;
- interpretare correttamente i trend d'uso;
- identificare traffico interno o ripetitivo che può falsare la lettura.

## 4. Le sezioni consigliate per i futuri report

Una struttura di report o dashboard coerente con le metriche disponibili potrebbe essere:

1. **Executive overview**
   - dimensione del repository;
   - nuovi item del mese;
   - visite;
   - download;
   - utenti attivi;
   - principali alert.

2. **Repository growth**
   - crescita del patrimonio;
   - nuove acquisizioni;
   - collezioni più attive;
   - distribuzioni per lingua, tipo, licenza.

3. **Content usage**
   - views;
   - downloads;
   - top item;
   - top collection/community;
   - rapporto views/downloads.

4. **Audience and acquisition**
   - visite;
   - pageviews;
   - referrer;
   - motori di ricerca;
   - provenienza geografica;
   - device e browser.

5. **Quality and compliance**
   - handle mancanti;
   - metadata mancanti o vuoti;
   - bitstream senza checksum;
   - licenze non valide;
   - record OAI problematici.

6. **Internal operations**
   - utenti attivi;
   - utenti inattivi;
   - submission pendenti;
   - gruppi e copertura autorizzativa.

7. **Traffic hygiene**
   - bot;
   - traffico interno;
   - accessi anomali;
   - quota di eventi realmente interpretabili come uso esterno.

## 5. Incroci analitici particolarmente promettenti

Questi non sono ancora singole metriche, ma domande che diventano molto forti quando si combinano più fonti:

| Incrocio | Domanda |
| --- | --- |
| DB upload per collection + Solr downloads/views per collection | Le collection che crescono di più sono anche quelle più usate? |
| DB distribuzione per licenza + Solr downloads per licenza | Alcuni regimi di licenza favoriscono maggiore uso? |
| DB nuovi item per tipo + Solr downloads per resource type | I tipi di contenuto caricati sono anche quelli più richiesti? |
| Matomo visite/pageviews + Solr views/downloads | Il traffico web si traduce in consultazione reale dei contenuti? |
| Matomo top pages + Solr top items | Le pagine più visitate corrispondono ai contenuti più consultati? |
| Solr search terms + DB/collection structure | Le ricerche degli utenti sono ben coperte dall'offerta del repository? |
| DB qualità metadata + Solr uso | I contenuti meglio descritti ottengono maggiore visibilità o uso? |
| DB upload mensili + Matomo/ Solr trend mensili | La crescita del repository produce crescita del pubblico o dell'uso? |

## 6. Metriche centrali da privilegiare

Per evitare report troppo affollati, conviene distinguere tra:

### Metriche core

Sono quelle che dovrebbero comparire quasi sempre in dashboard e report:

- nuovi item del mese;
- totale item;
- visite del mese;
- pageviews del mese;
- download del mese;
- views del mese;
- utenti attivi nel mese;
- top collection per upload;
- top collection per downloads/views;
- bounce rate;
- principali canali di acquisizione;
- principali alert di qualità.

### Metriche diagnostiche

Sono molto utili, ma non necessariamente da mostrare sempre in apertura:

- item senza handle;
- metadata mancanti;
- bitstream senza checksum;
- gruppi vuoti;
- submission ferme oltre 30 giorni;
- bot events;
- traffico interno;
- record OAI problematici;
- user agent/IP anomali.

### Metriche di dettaglio

Sono ottime per drill-down o appendici:

- ranking completi di item, referrer, paesi, browser;
- liste nominative di utenti;
- liste complete di oggetti problematici;
- primi/ultimi datestamp OAI;
- prime 30 righe di eventi Solr.

## 7. Osservazioni tecniche da verificare

1. Nel notebook Solr la sezione **“Downloads by collection in the reference month”** sembra avere una cella marcata `always` invece di `monthly`. Prima di usare quella metrica nei trend storici conviene verificarla.
2. Alcune metriche `always` sono cumulative e non andrebbero lette come trend temporali se rieseguite ogni mese senza una chiara semantica di snapshot.
3. Per la futura dashboard conviene creare un layer unico di caricamento dati, così i grafici non leggono direttamente decine di CSV sparsi ma funzioni stabili e documentate.

## 8. Principio guida per la fase successiva

La reportistica futura dovrebbe evitare di riprodurre semplicemente la struttura dei tre notebook. La struttura migliore non è:

- PostgreSQL
- Solr
- Matomo

ma piuttosto:

- crescita;
- uso;
- pubblico;
- qualità;
- operatività;
- anomalie.

In questo modo il report racconta il repository come sistema unico, invece di riflettere soltanto l'origine tecnica dei dati.
