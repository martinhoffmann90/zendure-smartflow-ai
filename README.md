# Zendure SmartFlow AI

Eine intelligente Home-Assistant-Integration zur **automatischen Steuerung von Zendure SolarFlow (AC)**  
– optimiert für **Autarkie**, **PV-Überschuss** und **Strompreis-Spitzen**.

---

## ✨ Funktionen

- 🔋 Intelligente Batterie-Steuerung
- ☀️ PV-Überschuss laden
- 🌙 Abends & nachts dynamisch entladen
- 💸 Peak-Shaving bei hohen Strompreisen
- 🧠 Mehrere AI-Modi direkt in der Integration
- 🚫 **Keine externen Helper notwendig**
- 🔧 Volle Kontrolle über Lade-/Entladegrenzen

---

## 🧠 AI-Modi

### 🔄 Automatik
- Wählt automatisch zwischen **Sommer** und **Winter**
- Sommer: April – September  
- Winter: Oktober – März

---

### ☀️ Sommer
Ziel: **Maximale Autarkie**
- PV-Überschuss → Akku laden
- Abends / nachts → Akku entlädt dynamisch nach Hausverbrauch
- Schutz vor Tiefentladung

---

### ❄️ Winter
Ziel: **Kosten senken**
- Entladung bei **hohen Strompreisen**
- PV-Überschuss wird weiterhin geladen
- Peak-Shaving bei Netzbezug

---

### ✋ Manuell
- **AI greift nicht ein**
- Zendure kann komplett manuell oder per anderer Automation gesteuert werden

---

## 🧩 Entitäten

### Select
- **Zendure SmartFlow AI – Moduswahl**

### Number
- SoC Minimum
- SoC Maximum (Standard: **100 %**)
- Max. Ladeleistung
- Max. Entladeleistung
- Teuer-Schwelle (€/kWh)

### Sensor
- AI Status
- Steuerungsempfehlung
- AI Debug (mit Entscheidungsdetails)

---

## ⚙️ Installation

### 🔹 Über HACS (empfohlen)
1. HACS → Integrationen
2. „Zendure SmartFlow AI“ suchen
3. Installieren
4. Home Assistant neu starten
5. Integration hinzufügen

### 🔹 Manuell
1. Repository nach  
   `/config/custom_components/zendure_smartflow_ai/` kopieren
2. Home Assistant neu starten
3. Integration hinzufügen

---

## 🛠️ Einrichtung

Beim Einrichten wählst du:
- Akku-SoC-Sensor
- PV-Leistung
- Hausverbrauch
- (optional) Tibber Strompreis-Export
- Zendure AC Mode (input/output)
- Zendure Input / Output Limit

👉 Die Integration erstellt **alle Regler selbst**

---

## ⚠️ Wichtige Hinweise

- Nach Updates ggf. **Integration neu hinzufügen**
- Im **Manuellen Modus** erfolgt **keine Hardware-Steuerung**
- Diese Integration ersetzt bestehende Automationen vollständig

---

## 🧪 Unterstützte Systeme

- Zendure SolarFlow AC
- Home Assistant ≥ 2024.12
- Tibber (Diagramm-Datenexport)

---

## 📄 Lizenz
MIT

---

## 🙌 Dank & Feedback
Entwickelt mit ❤️ für die Home-Assistant-Community  
Feedback & Issues:  
👉 https://github.com/PalmManiac/zendure-smartflow-ai/issues
