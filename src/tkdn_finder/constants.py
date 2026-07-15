# src/tkdn_finder/constants.py
"""All magic values live here. Never inline constants in business logic."""

P3DN_HOMEPAGE_URL = "https://p3dn.kemenperin.go.id/rekap.php"
P3DN_BASE_URL = "https://p3dn.kemenperin.go.id"
P3DN_SEARCH_URL = "https://p3dn.kemenperin.go.id/search.php"
P3DN_DETAIL_BASE_URL = "https://p3dn.kemenperin.go.id/sertifikat_perush.php"
P3DN_SEARCH_DETAIL_FETCH_CONCURRENCY = 5
EXPORT_LINK_HREF_PATTERN = r"export_excel\.php"
YEAR_EXTRACTION_PATTERN = r"(\d{4})"
KBLI_PATTERN = r"^\d{5}$"
DEFAULT_USER_AGENT = "TKDN-Finder/0.1 (procurement tooling)"

SCRAPER_TIMEOUT_SECONDS = 60
DOWNLOAD_TIMEOUT_SECONDS = 120
DOWNLOAD_RETRY_COUNT = 3
DOWNLOAD_RETRY_BACKOFF_SECONDS = 5
RAW_RETENTION_COUNT = 7

# Source column header (from P3DN HTML) -> internal field name.
# P3DN exports 12 columns, order fixed. When headers change, edit ONLY here.
HTML_COLUMN_MAP: dict[str, str] = {
    "Kode HS": "kode_hs",
    "KBLI": "kbli",
    "Kelompok Barang": "kelompok_barang",
    "Nama Perusahaan": "nama_perusahaan",
    "Alamat": "alamat",
    "Provinsi": "provinsi",
    "Produk": "nama_produk",
    "Spesifikasi": "spesifikasi",
    "Tipe": "tipe",
    "Merk": "merek",
    "Nilai TKDN (%)": "nilai_tkdn",
    "Tanggal Kadaluarsa Sertifikat": "masa_berlaku_akhir",
}

REQUIRED_FIELDS: tuple[str, ...] = ("nama_perusahaan", "nama_produk")
DATE_FORMAT = "%Y-%m-%d"

FTS_TOKENIZER = "porter unicode61 remove_diacritics 2"

VALIDITY_EXPIRING_SOON_DAYS = 60
TKDN_DEFAULT_MIN_FILTER = 0.0

SEARCH_RESULT_LIMIT_DEFAULT = 50
SEARCH_RESULT_LIMIT_MAX = 500
SEARCH_DEBOUNCE_MS = 250

RERANK_WEIGHT_FUZZY = 0.50
RERANK_WEIGHT_TKDN = 0.20
RERANK_WEIGHT_RECENCY = 0.15
RERANK_WEIGHT_VALIDITY = 0.15
FTS_CANDIDATE_LIMIT = 500

# TKDN value sentinel meaning "not applicable" in the source data
TKDN_SENTINEL_VALUE = 999.99

DEFAULT_SYNONYM_SEEDS: dict[str, list[str]] = {
    # ── Valves ────────────────────────────────────────────────────────────────
    "valve": ["katup", "valv"],
    "gate valve": ["katup gate", "katup pintu", "gate"],
    "ball valve": ["katup bola"],
    "butterfly valve": ["katup kupu-kupu", "katup butterfly"],
    "check valve": ["katup cek", "non-return valve", "NRV"],
    "globe valve": ["katup globe", "katup glob"],
    "safety valve": ["katup pengaman", "safety relief valve", "SRV", "PSV", "pressure safety valve"],
    "control valve": ["katup kontrol", "CV"],
    "needle valve": ["katup jarum"],
    "plug valve": ["katup sumbat"],
    "pressure relief valve": ["katup pelepas tekanan", "PRV", "relief valve"],
    "solenoid valve": ["katup solenoid", "solenoid"],
    # ── Pumps ─────────────────────────────────────────────────────────────────
    "pump": ["pompa"],
    "centrifugal pump": ["pompa sentrifugal", "pompa centrifugal"],
    "reciprocating pump": ["pompa reciprocating", "pompa bolak-balik", "pompa piston"],
    "submersible pump": ["pompa submersible", "pompa celup", "ESP", "electric submersible pump"],
    "dosing pump": ["pompa dosing", "chemical injection pump", "pompa injeksi kimia", "metering pump"],
    "booster pump": ["pompa booster", "pompa pendorong"],
    # ── Compressors ───────────────────────────────────────────────────────────
    "compressor": ["kompresor"],
    "gas compressor": ["kompresor gas"],
    "air compressor": ["kompresor udara", "kompresor angin"],
    "reciprocating compressor": ["kompresor reciprocating", "kompresor torak"],
    "screw compressor": ["kompresor screw", "kompresor ulir"],
    "centrifugal compressor": ["kompresor sentrifugal"],
    # ── Heat Exchangers ───────────────────────────────────────────────────────
    "heat exchanger": ["penukar panas", "HE", "alat penukar kalor", "APK"],
    "air cooler": ["pendingin udara", "fin fan cooler", "aerial cooler", "ACC"],
    # ── Vessels & Tanks ───────────────────────────────────────────────────────
    "pressure vessel": ["bejana tekan", "vessel bertekanan"],
    "separator": ["pemisah", "oil separator", "gas separator"],
    "storage tank": ["tangki penyimpanan", "tangki timbun"],
    "scrubber": ["penggosok gas", "gas scrubber"],
    # ── Pipes & Fittings ──────────────────────────────────────────────────────
    "pipe": ["pipa"],
    "elbow": ["belokan pipa", "siku pipa", "elbow pipa"],
    "flange": ["flanges", "flens"],
    "gasket": ["paking", "seal gasket", "perapat"],
    "reducer": ["reducer pipa", "reduktor pipa"],
    "fitting": ["fitting pipa", "sambungan pipa"],
    # ── Electrical ────────────────────────────────────────────────────────────
    "cable": ["kabel"],
    "wire": ["kawat", "kabel listrik"],
    "transformer": ["trafo"],
    "electric motor": ["motor listrik", "motor induksi", "motor elektrik"],
    "generator": ["genset", "diesel generator", "generator listrik"],
    "switchgear": ["panel listrik", "panel hubung bagi", "PHB"],
    "motor control center": ["MCC", "panel MCC", "pusat kendali motor"],
    "variable frequency drive": ["VFD", "inverter", "pengatur frekuensi", "variable speed drive", "VSD"],
    "UPS": ["uninterruptible power supply", "catu daya tak terputus"],
    # ── Instrumentation ───────────────────────────────────────────────────────
    "flow meter": ["alat ukur aliran", "flowmeter", "meter aliran", "flow measurement"],
    "pressure gauge": ["pengukur tekanan", "manometer", "pressure indicator", "PI"],
    "transmitter": ["pemancar sinyal", "pressure transmitter", "temperature transmitter"],
    "temperature gauge": ["pengukur suhu", "thermometer", "termometer"],
    # ── Mechanical Components ─────────────────────────────────────────────────
    "bearing": ["bantalan", "ball bearing", "roller bearing"],
    "coupling": ["kopling", "penyambung poros", "shaft coupling"],
    "seal": ["perapat", "mechanical seal", "segel", "oil seal"],
    "gear": ["roda gigi", "gearbox", "gear box"],
    "belt": ["sabuk", "v-belt", "fan belt"],
    # ── Well Equipment ────────────────────────────────────────────────────────
    "wellhead": ["kepala sumur", "well head"],
    "christmas tree": ["x-mas tree", "xmas tree", "pohon natal sumur"],
    "casing": ["selubung sumur", "pipa selubung", "OCTG casing", "casing pipa baja"],
    "tubing": ["pipa produksi", "production tubing", "OCTG tubing"],
    "pup joint": ["pup joint casing", "pup joint tubing", "pup joint pipa"],
    "OCTG": ["oil country tubular goods", "casing tubing", "drill pipe"],
    "drill pipe": ["pipa bor", "drill string"],
    "drill bit": ["mata bor", "pahat bor", "bit pemboran"],
    "BOP": ["blowout preventer", "pencegah semburan liar"],
    "choke valve": ["katup choke", "choke manifold"],
    "wellbore": ["lubang sumur", "bore hole"],
    "cementing": ["sementasi", "primary cementing", "primary cementing equipment", "peralatan sementasi"],
    "perforating": ["perforasi", "gun perforating", "peralatan perforasi"],
    "mud pump": ["pompa lumpur", "pompa pemboran"],
    # ── Piping — Oil & Gas Specific ───────────────────────────────────────────
    "line pipe": ["pipa saluran", "pipa transmisi", "pipeline"],
    "seamless pipe": ["pipa tanpa sambungan", "pipa seamless", "pipa baja tanpa kampuh", "seamless steel pipe"],
    "ERW pipe": ["pipa ERW", "pipa HFW", "pipa HF-ERW", "electric resistance welded", "high frequency welded", "pipa baja erw"],
    "spiral pipe": ["pipa spiral", "pipa LSAW", "spiral welded pipe"],
    "coated pipe": ["pipa berlapis", "pipa coated", "pipa baja berlapis", "anti-corrosion pipe"],
    "cable tray": ["tray kabel", "kabel tray", "cable ladder", "cable duct"],
    "stud bolt": ["baut stud", "alloy steel stud bolt", "studbolt", "baut dan mur", "stud bolt and nut"],
    "fitting forging": ["forged fitting", "fitting tempa", "socket weld fitting", "butt weld fitting"],
    "connector": ["konektor", "coupling connector", "sambungan"],
    "manifold": ["manifold pipa", "header pipa", "junction manifold"],
    "pig launcher": ["pig launcher receiver", "pigging", "peralatan pigging"],
    # ── Electrical — Oil & Gas ────────────────────────────────────────────────
    "distribution panel": ["panel distribusi", "panel hubung bagi tegangan rendah", "PHBTR", "LV panel", "low voltage distribution panel", "panel box distribusi"],
    "circuit breaker": ["MCB", "miniature circuit breaker", "pemutus sirkit", "MCCB", "ACB", "air circuit breaker"],
    "current transformer": ["CT", "trafo arus", "instrument transformer", "current transformer (ct)"],
    "battery": ["aki", "baterai", "lead acid battery", "UPS battery", "accumulator"],
    "street light": ["lampu jalan", "PJU", "tiang penerangan jalan umum", "tiang lampu PJU", "luminaire jalan"],
    "transmission tower": ["tower transmisi", "tower SUTET", "tiang transmisi", "tower listrik"],
    # ── Safety Equipment ──────────────────────────────────────────────────────
    "fire extinguisher": ["alat pemadam api ringan", "APAR", "tabung pemadam"],
    "safety harness": ["sabuk pengaman", "full body harness", "harness"],
    "fire detector": ["detektor api", "fire alarm", "smoke detector", "detektor asap"],
    "gas detector": ["detektor gas", "gas detection system", "H2S detector", "LEL detector"],
    "SCBA": ["self contained breathing apparatus", "alat bantu pernapasan", "breathing apparatus"],
    # ── Structural & Access ───────────────────────────────────────────────────
    "scaffold": ["perancah", "scaffolding"],
    "grating": ["kisi-kisi lantai", "floor grating", "jeruji lantai"],
    "crane": ["derek", "alat angkat", "overhead crane"],
    "hoist": ["kerekan", "chain block", "chain hoist", "alat angkut"],
    "skid": ["skid mounted", "paket skid", "module skid"],
    # ── Coatings & Insulation ─────────────────────────────────────────────────
    "insulation": ["insulasi", "isolasi panas", "lagging", "thermal insulation"],
    "coating": ["pelapis", "cat pelindung", "anti-corrosion coating"],
    "cathodic protection": ["proteksi katodik", "anoda korban", "impressed current"],
    # ── Electrical — Power Cables ─────────────────────────────────────────────
    "LV cable": ["kabel tegangan rendah", "low voltage cable", "kabel listrik low voltage", "kabel LV", "kabel listrik TR"],
    "MV cable": ["kabel tegangan menengah", "medium voltage cable", "kabel listrik medium voltage", "kabel MV", "kabel listrik TM"],
    "HV cable": ["kabel tegangan tinggi", "high voltage cable", "kabel listrik high voltage", "kabel HV"],
    "armoured cable": ["kabel berperisai", "kabel berpelindung baja", "kabel armour", "kabel XLPE armoured", "kabel NYFGbY"],
    "fiber optic cable": ["kabel serat optik", "kabel FO", "kabel fiber", "optical cable"],
    "cable accessories": ["aksesori kabel", "cable termination", "cable joint", "terminasi kabel", "mof kabel"],
    # ── Electrical — Protection & Switching ──────────────────────────────────
    "HV circuit breaker": ["pemutus sirkit tegangan tinggi", "high voltage circuit breaker", "SF6 circuit breaker", "OCB", "VCB", "vacuum circuit breaker"],
    "MCCB": ["molded case circuit breaker", "pemutus sirkit mold", "circuit breaker MCCB"],
    "fuse": ["sekering", "pengaman lebur", "HRC fuse", "fuse cutout"],
    "surge arrester": ["penangkal petir", "lightning arrester", "surge protector", "arrester tegangan lebih"],
    "relay protection": ["relai proteksi", "protection relay", "over current relay", "OCR", "differential relay"],
    "contactor": ["kontaktor", "magnetic contactor", "kontaktor magnetik"],
    # ── Electrical — Metering & Power Quality ────────────────────────────────
    "energy meter": ["kwh meter", "meteran listrik", "smart meter", "AMI", "AMR meter"],
    "capacitor bank": ["bank kapasitor", "power factor correction", "perbaikan faktor daya", "PFC"],
    "busbar": ["rel busbar", "busbar trunking", "busway", "batang penghantar"],
    "grounding": ["pentanahan", "pembumian", "earthing system", "ground rod"],
    # ── Electrical — Generation ───────────────────────────────────────────────
    "diesel genset": ["diesel generator set", "generating set", "genset diesel", "pembangkit diesel"],
    "solar panel": ["panel surya", "modul surya", "PV module", "photovoltaic", "panel fotovoltaik"],
    "inverter": ["inverter solar", "solar inverter", "string inverter", "grid tie inverter"],
    "EV charger": ["SPKLU", "stasiun pengisian kendaraan listrik", "electric vehicle charger", "charging station"],
    # ── Electrical — Lighting ─────────────────────────────────────────────────
    "LED streetlight": ["lampu jalan LED", "PJU LED", "lampu PJU", "luminaire jalan umum", "street light LED", "luminer jalan"],
    "floodlight": ["lampu sorot", "lampu sorot LED", "flood light", "lampu sorot halogen"],
    "industrial lighting": ["lampu industri", "highbay LED", "lampu highbay", "explosion proof lamp", "lampu explosion proof"],
    # ── Mechanical — Pumps Extended ──────────────────────────────────────────
    "pump package": ["paket pompa", "centrifugal pump package", "pump set", "pompa air set", "pompa industri"],
    "fire pump": ["pompa kebakaran", "pompa pemadam", "fire fighting pump", "pompa hydrant"],
    "jet pump": ["pompa jet", "self priming pump", "pompa self priming"],
    "turbine pump": ["pompa turbin", "vertical turbine pump", "pompa sumur dalam"],
    # ── Mechanical — Rotating Equipment ──────────────────────────────────────
    "diesel engine": ["mesin diesel", "motor diesel", "horizontal diesel engine", "diesel motor"],
    "gearbox": ["roda gigi", "gear reducer", "speed reducer", "reduktor kecepatan"],
    "actuator": ["aktuator", "electric actuator", "pneumatic actuator", "hydraulic actuator", "valve actuator"],
    "blower": ["kipas industri", "industrial fan", "centrifugal blower", "axial fan"],
    "agitator": ["pengaduk", "mixer industri", "industrial mixer", "stirrer"],
    "conveyor": ["konveyor", "belt conveyor", "roller conveyor", "screw conveyor", "konveyor sabuk"],
    "expansion joint": ["sambungan ekspansi", "flexible joint", "bellow expansion joint", "flexible hose"],
    # ── Mechanical — Static Equipment ────────────────────────────────────────
    "filter": ["saringan", "strainer", "basket strainer", "Y-strainer", "filter housing", "bag filter"],
    "heat tracing": ["pemanas pipa", "electric heat tracing", "steam tracing", "trace heating"],
    "pipe support": ["penyangga pipa", "pipe hanger", "spring hanger", "pipe clamp", "pipe bracket"],
    "flange blind": ["blind flange", "flange penutup", "plate flange"],
    "orifice plate": ["pelat orifis", "orifice fitting", "restriction orifice", "flow orifice"],
    # ── Instrumentation — Pressure ────────────────────────────────────────────
    "pressure transmitter": ["transmiter tekanan", "PT", "pressure sensor", "differential pressure transmitter", "DP transmitter"],
    "pressure switch": ["saklar tekanan", "pressure sensing switch", "high pressure switch"],
    "pressure safety valve": ["PSV", "PRV", "safety valve", "pressure relief valve", "katup pengaman tekanan"],
    # ── Instrumentation — Temperature ─────────────────────────────────────────
    "thermocouple": ["termokopel", "TC", "temperature element", "elemen suhu"],
    "RTD": ["resistance temperature detector", "termistor suhu", "PT100", "temperature sensor RTD"],
    "temperature transmitter": ["TT", "transmiter suhu", "temperature indicator transmitter", "TIT"],
    # ── Instrumentation — Flow ────────────────────────────────────────────────
    "orifice flow meter": ["flow meter orifis", "differential pressure flow meter", "DP flow meter"],
    "magnetic flow meter": ["flow meter elektromagnetik", "electromagnetic flow meter", "magmeter"],
    "ultrasonic flow meter": ["flow meter ultrasonik", "clamp on flow meter"],
    "coriolis flow meter": ["flow meter coriolis", "mass flow meter", "coriolis meter"],
    "turbine flow meter": ["flow meter turbin"],
    "flow indicator": ["FI", "flow indicator controller", "FIC", "rotameter"],
    # ── Instrumentation — Level ───────────────────────────────────────────────
    "level transmitter": ["LT", "transmiter level", "radar level", "ultrasonic level", "level sensor"],
    "level gauge": ["gelas penduga", "sight glass", "level glass", "gauge glass", "indikator level", "level indicator", "penunjuk level"],
    "level switch": ["saklar level", "float switch", "level detector"],
    # ── Instrumentation — Analyzers ───────────────────────────────────────────
    "gas analyzer": ["analisator gas", "gas chromatograph", "GC", "gas detector analyzer"],
    "H2S detector": ["detektor H2S", "hydrogen sulfide detector", "H2S monitor"],
    "oxygen analyzer": ["analisator oksigen", "O2 analyzer", "dissolved oxygen meter"],
    "water quality analyzer": ["analisator kualitas air", "pH meter", "turbidity meter"],
    # ── Instrumentation — Control Systems ────────────────────────────────────
    "DCS": ["distributed control system", "sistem kontrol terdistribusi", "process control system"],
    "PLC": ["programmable logic controller", "kontroler logika terprogram", "program logic controller"],
    "SCADA": ["supervisory control and data acquisition", "sistem SCADA", "telemetri"],
    "ESD": ["emergency shutdown system", "safety instrumented system", "SIS", "sistem penutupan darurat"],
    "fire and gas system": ["sistem fire and gas", "F&G system", "fire gas detection", "sistem deteksi kebakaran gas"],
    "control panel": ["panel kontrol", "instrument panel", "control room panel", "marshalling cabinet", "junction box"],
    "HMI": ["human machine interface", "operator interface", "SCADA HMI", "touch panel HMI"],
    # ── Chemicals — O&G Production ────────────────────────────────────────────
    "demulsifier": ["bahan demulsifier", "kimia demulsifier", "chemical demulsifier", "pemecah emulsi"],
    "corrosion inhibitor": ["inhibitor korosi", "bahan kimia anti korosi", "corrosion protection chemical"],
    "scale inhibitor": ["inhibitor scale", "anti scale chemical", "kimia anti kerak"],
    "biocide": ["biosida", "bahan kimia biocide", "microbicide", "penghambat mikroba"],
    "drilling fluid": ["lumpur bor", "drilling mud", "mud drilling", "oil based mud", "water based mud"],
    "lubricant": ["pelumas", "minyak pelumas", "oli", "grease", "lubrication oil"],
    # ── Well Equipment — Artificial Lift & Downhole ──────────────────────────
    "sucker rod pump": ["pompa angguk", "rod pump", "SRP", "pumping unit", "sucker rod"],
    "progressive cavity pump": ["PCP", "pompa cavity", "screw pump", "pompa ulir"],
    "packer": ["production packer", "packer sumur", "packer completion"],
    "drilling rig": ["rig pemboran", "menara bor", "workover rig", "rig service"],
    # ── Rotating — Turbines ───────────────────────────────────────────────────
    "gas turbine": ["turbin gas", "gas turbine generator", "GTG"],
    "steam turbine": ["turbin uap", "steam turbine generator", "STG"],
    # ── Process & Utility Equipment ───────────────────────────────────────────
    "flare": ["flare stack", "flare tip", "suar bakar", "flare system"],
    "metering system": ["metering skid", "sistem metering", "custody metering", "gas metering system", "metering station"],
    "pressure regulator": ["regulator tekanan", "gas pressure regulator", "regulator gas"],
    "boiler": ["ketel uap", "steam boiler", "steam generator"],
    "heater": ["pemanas", "electric heater", "immersion heater", "water bath heater"],
    "air dryer": ["pengering udara", "desiccant dryer", "refrigerated air dryer"],
    "air receiver": ["tangki udara", "air receiver tank", "tangki angin"],
    "nitrogen generator": ["generator nitrogen", "N2 generator", "nitrogen plant"],
    "water treatment": ["pengolahan air", "WTP", "water treatment plant", "IPAL", "sewage treatment"],
    "RO membrane": ["membran RO", "reverse osmosis", "membran reverse osmosis"],
    # ── Piping — Non-metallic ─────────────────────────────────────────────────
    "GRE pipe": ["pipa GRE", "GRP pipe", "pipa fiberglass", "fiberglass pipe", "FRP pipe", "pipa komposit"],
    "HDPE pipe": ["pipa HDPE", "pipa polyethylene", "PE pipe", "pipa PE"],
    "PVC pipe": ["pipa PVC", "pipa paralon", "pipa uPVC"],
    "hose": ["selang", "hydraulic hose", "selang hidrolik", "rubber hose", "selang industri"],
    # ── Materials & Fabrication ───────────────────────────────────────────────
    "steel plate": ["pelat baja", "plat baja", "besi plat", "steel sheet"],
    "structural steel": ["baja profil", "besi profil", "konstruksi baja", "steel structure", "H beam", "WF beam", "wide flange"],
    "bolt": ["baut", "mur baut", "baut mur", "fastener", "anchor bolt", "baut angkur"],
    "wire rope": ["tali kawat baja", "sling", "wire rope sling", "kawat seling"],
    "welding machine": ["mesin las", "trafo las", "welding inverter"],
    "welding electrode": ["kawat las", "elektroda las", "welding wire", "filler wire"],
    # ── Instrumentation — Valves & Fittings ──────────────────────────────────
    "motor operated valve": ["MOV", "motorized valve", "katup motor", "motorised valve"],
    "valve positioner": ["positioner", "smart positioner", "pengatur posisi katup"],
    "instrument tube fitting": ["tube fitting", "instrument tubing", "compression fitting", "ferrule fitting"],
    "instrument cable": ["kabel instrumen", "kabel instrument", "instrumentation cable", "kabel kontrol", "control cable"],
    "junction box": ["kotak sambung", "terminal box", "junction box explosion proof", "kotak terminal"],
    "explosion proof": ["explosion-proof", "flameproof", "tahan ledakan", "Ex proof"],
    # ── Electrical — Transformers & Switchgear ───────────────────────────────
    "power transformer": ["trafo daya", "trafo tenaga", "distribution transformer", "trafo distribusi", "oil immersed transformer"],
    "MV switchgear": ["kubikel", "cubicle", "kubikel tegangan menengah", "MV cubicle", "medium voltage switchgear"],
    "cable gland": ["gland kabel", "kabel gland", "cable gland explosion proof", "Ex gland"],
    "terminal block": ["blok terminal", "terminal blok", "terminal strip"],
}
