# DSpace Reporting

Questo progetto produce reportistiche DSpace a partire da notebook Jupyter e da una configurazione YAML.

Il flusso attuale consente di eseguire i notebook delle metriche DB, Solr e Matomo su un singolo mese oppure su una sequenza di mesi completi. Il mese corrente viene escluso automaticamente, per evitare metriche troncate.

## Struttura

```text
config/
  settings.example.yaml   # configurazione di esempio
  settings.local.yaml     # configurazione locale reale
notebooks/
  01_db_metrics.ipynb     # metriche PostgreSQL
  02_solr_metrics.ipynb   # metriche Solr
  03_matomo_metrics.ipynb # metriche Matomo
src/
  dspace_reporting/
    config.py             # caricamento e normalizzazione config
    periods.py            # risoluzione mesi/intervalli
    export.py             # helper directory export
    runners/
      run_notebook_periods.py
exports/
  db/
    monthly/             # metriche relative al reference_month
    always/              # metriche sullo stato complessivo
  solr/
  matomo/
reports/
  metrics_catalog.md        # tassonomia delle metriche e aree di analisi
  index.html                # archivio navigabile dei report mensili generati
  assets/                   # asset statici pubblicati insieme al sito dei report
  monthly/                  # report statici generati per mese
  always/                   # report di stato complessivo per snapshot always
assets/
  branding/                 # logo del centro usato nei report e nella futura dashboard
data/
tests/
```

## Setup

Crea il virtualenv nella root del progetto:

```powershell
python -m venv virtual_env
```

Attivalo:

```powershell
.\virtual_env\Scripts\Activate.ps1
```

Installa le dipendenze nell'ambiente Python/Jupyter con cui vuoi eseguire i notebook:

```bash
pip install -r requirements.txt
```

Installa poi il progetto in modalita editable, cosi Python trova il package `dspace_reporting` senza impostare `PYTHONPATH`:

```powershell
python -m pip install --no-use-pep517 -e .
```

## Configurazione

La configurazione principale e in:

```text
config/settings.local.yaml
```

La sezione piu importante e `run`:

```yaml
run:
  mode: "monthly"
  reference_month: "current"
  always_reference_month: null
  start: "2026"
  end: null
  create_month_subfolders: true
  export_outputs: true
  overwrite_exports: false
  overwrite_reports: false
  include_snapshot_metrics: true
  future_start_policy: "current_year"
```

### Campi principali

`mode`

- `single`: esegue solo `reference_month`.
- `monthly`: calcola tutti i mesi completi da `start` a `end`.

`reference_month`

Mese singolo nel formato `YYYY-MM`, oppure `"current"`/`"today"` per usare il mese della data di lancio. Serve per compatibilita con il notebook e per `mode: single`.

`always_reference_month`

Etichetta opzionale per gli export `always`. Se vale `"current"`, il runner usa il mese corrente del giorno di avvio. Se e `null` o assente, il runner usa `reference_month`; se manca anche `reference_month`, usa comunque il mese corrente.

`start`

Periodo iniziale. Accetta:

```yaml
start: "2026"
```

che significa gennaio 2026, oppure:

```yaml
start: "2026-03"
```

che significa marzo 2026.

`end`

Periodo finale. Accetta `YYYY-MM` oppure `null`.

Con:

```yaml
end: null
```

il programma usa automaticamente il mese precedente al mese corrente.

Esempio: se lo script viene lanciato l'11 maggio 2026, l'ultimo mese incluso e `2026-04`.

`overwrite_exports`

Se `false`, il runner controlla gli export attesi prima di eseguire ogni
periodo. In modalita `monthly`, salta i periodi che hanno gia tutti i CSV,
esegue quelli mancanti e si ferma solo se trova un periodo esportato
parzialmente.

`overwrite_reports`

Segue la stessa logica operativa di `overwrite_exports`, ma per i report HTML:

- se `false`, il runner dei report salta i report mensili o `always` gia presenti;
- se `true`, rigenera i report anche quando `report.html` esiste gia.

`export_outputs`

Se `false`, il notebook esegue le analisi e mostra i risultati a video, ma non scrive CSV. Lo stesso comportamento si puo attivare da comando con `--display-only`, senza modificare il file YAML.

`future_start_policy`

Se `start` e nel futuro:

- `current_year`: riparte da gennaio dell'anno corrente.
- `error`: interrompe l'esecuzione con errore.

### Matomo

La sezione `matomo` contiene endpoint, site id, token e filtro dominio usato dalle metriche sulle URL delle pagine:

```yaml
matomo:
  base_url: "https://stats.ilc.cnr.it/"
  site_id: 12
  token_auth: "CHANGE_ME"
  token_description: "jupyter-notebook-analytics"
  domain_filter: "dspace-clarin-it.ilc.cnr.it"
  verify_ssl: true
```

`domain_filter` viene letto dal notebook `03_matomo_metrics.ipynb` e limita le classificazioni delle page view alle URL del dominio DSpace configurato.

## Esempi Di Periodo

Da gennaio 2026 fino all'ultimo mese completo:

```yaml
run:
  mode: "monthly"
  start: "2026"
  end: null
```

Se oggi e l'11 maggio 2026, vengono processati:

```text
2026-01
2026-02
2026-03
2026-04
```

Intervallo esplicito:

```yaml
run:
  mode: "monthly"
  start: "2025-09"
  end: "2026-03"
```

Vengono processati:

```text
2025-09
2025-10
2025-11
2025-12
2026-01
2026-02
2026-03
```

Singolo mese:

```yaml
run:
  mode: "single"
  reference_month: "current"
```

## Verificare Cosa Verra Eseguito

Prima di lanciare davvero le analisi, usa il dry-run:

```powershell
python -m dspace_reporting.runners.run_notebook_periods --dry-run
```

Output atteso:

```text
Months to process: 2026-01, 2026-02, 2026-03, 2026-04
```

Il dry-run non apre connessioni al database e non esegue il notebook.

Per verificare l'esecuzione su un solo mese senza modificare il file YAML:

```powershell
python -m dspace_reporting.runners.run_notebook_periods --month 2026-05 --dry-run
```

## Eseguire Le Reportistiche

Per lanciare tutti i notebook di reportistica disponibili su tutti i mesi risolti dalla configurazione:

> [!WARNING]
> Se i servizi configurati (PostgreSQL, Solr, Matomo o il bastion SSH) si trovano
> in una rete privata, assicuratevi di essere connessi alla VPN prima di eseguire
> le reportistiche, altrimenti il runner potrebbe non riuscire a raggiungerli.

```powershell
python -m dspace_reporting.runners.run_notebook_periods
```

Per limitare l'esecuzione a uno o piu mesi specifici dalla riga di comando:

```powershell
python -m dspace_reporting.runners.run_notebook_periods --month 2026-05
```

oppure:

```powershell
python -m dspace_reporting.runners.run_notebook_periods --month 2026-04 2026-05
```

L'opzione `--month` prevale sulla risoluzione dei mesi definita nella sezione
`run` del file YAML. Se i notebook contengono celle taggate `always`, quelle
vengono comunque eseguite una sola volta secondo la logica descritta piu sotto
per `always_reference_month`.

Il runner controlla gli export attesi per sorgente. Se gli export DB sono gia
presenti ma quelli Solr o Matomo mancano, salta il DB e genera solo gli export
mancanti.

Per eseguire le stesse analisi senza scrivere CSV:

```powershell
python -m dspace_reporting.runners.run_notebook_periods --display-only
```

In questa modalita il runner stampa a console i titoli delle sezioni, gli output testuali delle celle e le rappresentazioni testuali delle tabelle prodotte con `display(...)`.

Il runner:

1. legge `config/settings.local.yaml`;
2. calcola i mesi da processare;
3. crea una configurazione temporanea per ciascun mese;
4. passa quella configurazione al notebook tramite la variabile `DSPACE_REPORTING_CONFIG`;
5. esegue le celle marcate `monthly` una volta per mese;
6. esegue le celle marcate `always` una sola volta.

La configurazione locale non viene modificata a ogni giro.

## Usare Un File Di Configurazione Diverso

Puoi passare un file YAML diverso:

```powershell
python -m dspace_reporting.runners.run_notebook_periods --config config/settings.local.yaml
```

## Eseguire Un Solo Notebook

Il runner accetta anche un notebook specifico:

```powershell
python -m dspace_reporting.runners.run_notebook_periods --notebook notebooks/02_solr_metrics.ipynb --dry-run
```

Per eseguirlo davvero:

```powershell
python -m dspace_reporting.runners.run_notebook_periods --notebook notebooks/02_solr_metrics.ipynb
```

Nota: per funzionare correttamente, il notebook deve leggere la configurazione da `DSPACE_REPORTING_CONFIG`, come fanno i notebook inclusi nel progetto.

## Export

Gli export sono separati prima per sorgente e poi per tipo di metrica:

```text
exports/db/monthly/2026-04/
exports/db/always/2026-04/
exports/solr/monthly/2026-04/
exports/solr/always/2026-04/
exports/matomo/monthly/2026-04/
exports/matomo/always/2026-04/
```

`monthly` contiene analisi relative al mese o a finestre temporali calcolate dal `reference_month`, per esempio caricamenti nel mese o utenti attivi negli ultimi 12 mesi.

`always` contiene analisi sullo stato complessivo della sorgente al momento dell'esecuzione, per esempio totale item, community, collection, gruppi, licenze o anomalie strutturali.

Se `overwrite_exports: false`, il runner salta i periodi gia completi, esegue quelli senza CSV e si ferma se trova un periodo con export parziali. Per rieseguire un periodo gia completo, elimina o sposta i CSV esistenti oppure imposta temporaneamente `overwrite_exports: true`.

## Esecuzione Monthly E Always

I notebook con celle taggate `monthly` e `always` vengono eseguiti separando le metriche mensili da quelle complessive:

- `exports/db/monthly/<reference_month>/` per metriche mensili;
- `exports/db/always/<reference_month>/` per metriche complessive;
- `exports/matomo/monthly/<reference_month>/` per metriche Matomo del mese;
- `exports/matomo/always/<reference_month>/` per metriche Matomo complessive.

Le celle `monthly` vengono eseguite per tutti i mesi selezionati. Le celle `always` vengono eseguite una sola volta, usando `run.always_reference_month` se presente, altrimenti `run.reference_month`, altrimenti il mese corrente del giorno di avvio.

Le query mensili devono usare `REPORT_MONTH_DATE` e `REPORT_AS_OF_DATE`, non `CURRENT_DATE`, quando la metrica dipende dal periodo selezionato.

## Report Statici E Dashboard

La strategia consigliata per la fase successiva separa tre livelli:

1. i notebook producono i CSV in `exports/`;
2. gli script di reportistica leggono gli export e generano output finali in `reports/`;
3. una futura dashboard esplorera gli export storici e rendera consultabili i report gia prodotti, senza duplicare la logica di calcolo.

Questa separazione mantiene una distinzione intenzionale:

- `exports/` contiene solo CSV, divisi per origine, scope e periodo;
- `reports/` contiene solo prodotti finali: pagine HTML, immagini, metadati e in futuro eventuali PDF.

In questo modo si ottengono sia:

- report mensili archiviabili e condivisibili;
- immagini salvate durante la generazione dei report;
- una futura esplorazione interattiva dello storico.

Il catalogo delle metriche e delle sezioni analitiche previste si trova in:

```text
reports/metrics_catalog.md
```

### Struttura Prevista Dei Report

```text
reports/
  index.html
  assets/
    branding/
      logo.png
  monthly/
    2026-04/
      report.html
      manifest.json
      figures/
        monthly_overview.png
        top_collections.png
        top_countries.png
  always/
    2026-05/
      report.html
```

### Branding Del Centro

Per riportare il logo del centro nei report e, in futuro, nella dashboard:

1. crea la cartella:

```text
assets/branding/
```

2. salva il logo al suo interno, per esempio:

```text
assets/branding/logo.png
```

3. configura il percorso in `config/settings.local.yaml`:

```yaml
reporting:
  institution_name: "ILC4CLARIN"
  institution_subtitle: "DSpace monthly institutional report"
  archive_title: "Archivio dei report mensili"
  logo_path: "assets/branding/logo.png"
```

Formati supportati:

- `SVG`, formato preferito;
- `PNG`, consigliato per immagini raster con sfondo trasparente;
- `JPG` / `JPEG`, ammessi come fallback.

Raccomandazioni per file raster:

- larghezza minima consigliata: `300 px`;
- larghezza ideale: `600-1200 px`;
- dimensione massima consigliata: `2 MB`;
- preferire un logo orizzontale, indicativamente con rapporto tra `2:1` e `5:1`.

### Generare I Report Statici

Prima installa le dipendenze aggiornate:

```powershell
python -m pip install -r requirements.txt
```

Poi genera i report per tutti i mesi risolti dalla configurazione `run`, con la stessa logica generale usata per gli export:

```powershell
python -m dspace_reporting.runners.build_reports
```

Per verificare cosa verrebbe generato senza scrivere file:

```powershell
python -m dspace_reporting.runners.build_reports --dry-run
```

Per generare uno o piu mesi espliciti:

```powershell
python -m dspace_reporting.runners.build_reports --month 2026-04
```

oppure:

```powershell
python -m dspace_reporting.runners.build_reports --month 2026-03 2026-04
```

Per rigenerare un report gia esistente senza modificare il file YAML:

```powershell
python -m dspace_reporting.runners.build_reports --month 2026-04 --overwrite-reports
```

Il report generator crea, per ogni mese:

- `report.html`, report istituzionale leggibile in browser;
- `manifest.json`, con metadati del report generato;
- immagini in `figures/`, riutilizzabili anche fuori dalla dashboard.

Il file sorgente del logo resta configurato in `assets/branding/`, ma durante la
generazione viene copiato in `reports/assets/branding/`. Gli HTML dei report
referenziano la copia pubblicata sotto `reports/`, cosi l'intera cartella dei
report puo essere servita o copiata come sito statico autonomo.

### Pubblicare I Report Su Un Web Server

Per pubblicare il sito statico, e sufficiente servire il contenuto della cartella:

```text
reports/
```

La cartella contiene:

- `index.html`, pagina di ingresso;
- `monthly/` e `always/`, con i report HTML generati;
- `assets/`, con gli asset statici condivisi usati dal sito;
- `figures/` dentro i singoli report mensili, con i grafici locali.

In questo modo il sito puo essere esposto direttamente da Apache senza dipendere
da percorsi esterni al document root per logo o immagini generate.

Nota: al momento Bootstrap viene caricato da CDN. Se serve un deployment
completamente offline, conviene copiare anche Bootstrap sotto `reports/assets/`
e referenziarlo localmente dagli HTML.

Ad ogni esecuzione viene inoltre aggiornato `reports/index.html`, che funge da
archivio navigabile dei report mensili gia prodotti. Ogni report include anche
collegamenti al mese precedente, al mese successivo e all'archivio generale.
I collegamenti precedente/successivo vengono calcolati solo sui report HTML gia
esistenti o generati nella build corrente, cosi non puntano a mesi per cui una
pagina non e ancora disponibile.
Il titolo mostrato nella pagina archivio e nel tag HTML `<title>` viene letto da
`reporting.archive_title` nel file di configurazione.

Il report HTML mensile include:

- una sintesi generale con KPI principali;
- un grafico di andamento mensile;
- una vista sulle collection piu attive;
- una vista sulla provenienza geografica delle visite;
- una vista sulle tipologie di pagina piu consultate;
- una sezione sul profilo complessivo del repository basata sulle metriche `always`;
- una sezione sull'uso dei contenuti, con top item e distribuzione dei download;
- una sezione sull'acquisizione del traffico;
- un riepilogo di qualita e conformita basato sull'ultimo snapshot `always` disponibile;
- brevi testi descrittivi delle analisi e una nota metodologica.

Le sezioni dei report HTML sono espandibili/comprimibili. Il report `always`,
piu ricco di sezioni tecniche e amministrative, usa inoltre una barra di
`navtab` orizzontale scorrevole: ogni tab mostra una sezione alla volta e rende
piu agevole la consultazione quando il numero di blocchi cresce.

Se un report mensile esiste gia e `run.overwrite_reports` e `false`, il runner lo salta. Per rigenerarlo, imposta temporaneamente `run.overwrite_reports: true`, usa `--overwrite-reports`, oppure sposta/elimina la cartella del mese.

Questa e una prima base istituzionale: il motore di reportistica e separato in moduli riusabili dentro `src/dspace_reporting/reporting/`, cosi la futura dashboard potra riutilizzare la stessa logica senza cambiare il ruolo di `exports/` e `reports/`.

### Metriche `always` Nei Report

Gli export `always` restano salvati separatamente in:

```text
exports/<source>/always/<reference_month>/
```

La reportistica genera anche una famiglia separata:

```text
reports/always/<reference_month>/
```

Le metriche `always` vengono quindi usate in due modi:

- come snapshot di stato incorporati nei report mensili, per contestualizzare il mese;
- come report autonomi di stato complessivo del repository sotto `reports/always/`.

Il report autonomo `always` raccoglie sezioni dedicate a:

- organizzazione del repository;
- stato degli item e qualita dei metadati;
- esposizione OAI e indicizzazione Solr;
- uso storico del repository;
- accessi, referrer e traffico Matomo;
- geografia, dispositivi e tecnologia;
- utenti, gruppi, workflow e integrita tecnica.

## Test Rapidi

Per verificare la logica dei periodi:

```powershell
python -m pytest tests
```

Se `pytest` non e installato:

```bash
pip install pytest
```

In alternativa, test minimo senza `pytest`:

```powershell
python -c "from datetime import date; from dspace_reporting.periods import resolve_months; print(resolve_months('2026', None, today=date(2026,5,11)))"
```

Output:

```text
['2026-01', '2026-02', '2026-03', '2026-04']
```
