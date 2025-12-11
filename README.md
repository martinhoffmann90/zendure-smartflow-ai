# Zendure SmartFlow AI

**Version 0.1.0 – Early Preview**

Zendure SmartFlow AI ist eine intelligente Steuerungs-Integration für Home Assistant, die
den Zendure SolarFlow AC (SF2400/SF3000) mit dynamischer Tibber-Preisprognose verbindet
und optimierte Lade- und Entladeentscheidungen trifft.

### Funktionen
- KI-Analyse der nächsten 48h Strompreise (Tibber Export)
- Erkennung von Peak-Phasen / teuersten Zeitblöcken
- Ermittlung der günstigsten Ladezeit vor Peak
- Mehrsprachige Statusmeldungen (de/en)
- Übergabe der Empfehlung an Home-Assistant Automationen

### Installation
1. Repository clonen oder als ZIP herunterladen  
2. Ordner `custom_components/zendure_smartflow_ai` in Home Assistant kopieren  
3. Home Assistant neu starten  
4. Integration erscheint in *Einstellungen → Geräte & Dienste → Integration hinzufügen*

### TODO – geplanter Ausbau
- Offizielle HACS-Einreichung  
- Config-Flow  
- UI-Konfiguration  
- Historische Analyse  
- Automatische Zendure-API-Anbindung  

---

# 📄 **LICENSE (MIT)**

```text
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
...
