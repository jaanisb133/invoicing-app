# V-Rēķini — Offline instalācija

Šī instrukcija paredzēta, lai uzstādītu V-Rēķini bezsaistes režīmā uz Windows vai Mac datora.

---

## 1. solis: Lejupielādēt Python

### Windows
1. Atveriet https://www.python.org/downloads/
2. Nospiediet **"Download Python 3.x.x"**
3. Palaidiet instalētāju
4. **SVARĪGI:** Atzīmējiet ✅ **"Add Python to PATH"** pirms nospiežat "Install Now"
5. Nospiediet **"Install Now"**

### Mac
1. Atveriet https://www.python.org/downloads/
2. Nospiediet **"Download Python 3.x.x"**
3. Atveriet lejupielādēto `.pkg` failu un sekojiet instrukcijām

#### Pārbaude
Atveriet termināli (Mac: Terminal / Windows: Command Prompt) un ierakstiet:
```
python --version
```
Jābūt atbildei `Python 3.9.x` vai jaunākam.

---

## 2. solis: Lejupielādēt V-Rēķini

Saņemsiet `.zip` failu ar programmu. Izpakojiet to jebkurā mapē, piemēram:

- **Windows:** `C:\V-Rekini\`
- **Mac:** `/Users/jusu-vards/V-Rekini/`

---

## 3. solis: Palaist programmu

### Windows
Atveriet mapi `V-Rekini` un veiciet dubultklikšķi uz **`start.bat`**

### Mac
Atveriet mapi `V-Rekini` un veiciet dubultklikšķi uz **`start.command`**

> Ja Mac parāda brīdinājumu "nevar atvērt, jo izstrādātājs nav identificēts":
> 1. Atveriet **System Settings → Privacy & Security**
> 2. Ritiniet uz leju un nospiediet **"Open Anyway"**

---

## Kas notiek pirmajā palaišanā?

1. Automātiski instalējas nepieciešamās bibliotēkas (nepieciešams internets)
2. Lejupielādējas 3 nelieli faili (~200 KB kopā) priekš diagrammām un datumu izvēles
3. Atveras pārlūks ar adresi `http://localhost:8000`
4. Automātiski izveido sākotnējo datubāzi

**Pēc pirmās palaišanas internets vairs nav nepieciešams.**

---

## Ikdienas lietošana

1. Dubultklikšķis uz `start.bat` (Windows) vai `start.command` (Mac)
2. Pārlūkā atvērsies V-Rēķini
3. Kad beidzat darbu — aizveriet termināļa logu (vai nospiediet `Ctrl+C`)

---

## Datu glabāšana

Visi dati tiek glabāti lokāli failā `data/offline.db` jūsu datorā.

**SVARĪGI: Regulāri kopējiet failu `data/offline.db` uz USB vai mākoņkrātuvi kā rezerves kopiju!**

---

## Problēmu novēršana

| Problēma | Risinājums |
|-----------|------------|
| `python nav atrasts` | Pārinstalējiet Python ar "Add to PATH" atzīmi |
| `pip nav atrasts` | Palaidiet: `python -m ensurepip --upgrade` |
| Pārlūks neatveras | Manuāli atveriet: `http://localhost:8000` |
| Ports aizņemts | Aizveriet iepriekšējo V-Rēķini logu vai iestatiet: `set PORT=8080` pirms palaišanas |
