# Zendure SmartFlow AI

Intelligente Home-Assistant-Integration zur **automatischen Steuerung von Zendure SolarFlow**
– basierend auf PV-Ertrag, Hausverbrauch, Akkustand und optional Strompreis.

> Entwickelt für reale Setups – ohne externe Helper, vollständig integriert.

---

## ✨ Features

- 🔋 Dynamisches Laden & Entladen
- ☀️ PV-Überschuss intelligent nutzen
- 🧠 Mehrere Betriebsmodi (Automatic / Summer / Winter / Manual)
- 💶 Preisbasierte Steuerung (Tibber Datenexport)
- 🛠️ Direkte Hardware-Ansteuerung (AC Mode, Input/Output Limit)
- 🧩 Komplett ohne externe Helper
- 📊 Transparente Sensoren & Debug-Daten

---

## 🔧 Voraussetzungen

- Home Assistant ≥ 2024.x
- Zendure SolarFlow (AC)
- Verfügbare Entitäten:
  - Akku-SoC (%)
  - PV-Leistung (W)
  - Hausverbrauch (W)
  - Zendure AC Mode (Select)
  - Zendure Input/Output Limit (Number)
- Optional:
  - Tibber Datenexport Sensor (`attributes.data`)

---

## ⚙️ Installation

### Über HACS (empfohlen)
1. Benutzerdefiniertes Repository hinzufügen
2. „Zendure SmartFlow AI“ installieren
3. Home Assistant neu starten

### Manuell
1. Ordner `zendure_smartflow_ai` nach  
   `config/custom_components/` kopieren
2. Home Assistant neu starten

---

## 🧭 Einrichtung

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. „Zendure SmartFlow AI“ auswählen
3. Benötigte Sensoren & Zendure-Entitäten auswählen
4. Fertig – die Integration erstellt automatisch:
   - Regler
   - Modi
   - Status- & Debug-Sensoren

---

## 🎛️ Bedienung

- Moduswahl über:
  **Zendure SmartFlow AI Moduswahl**
- Feinjustierung über integrierte Number-Entitäten
- Status & Empfehlung über Sensoren einsehbar

---

## 🧪 Status

- Aktuelle Version: **v0.5.0**
- Stabil & einsatzbereit
- Weitere Erweiterungen geplant

---

## 🤝 Mitmachen

Feedback, Logs & Ideen gerne als Issue im Repository.
Diese Integration lebt von Praxis-Erfahrungen.

---

**Viel Erfolg beim Optimieren deiner Energie! 🔋☀️**
