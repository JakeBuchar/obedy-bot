# obedy-bot

Malý nástroj, který každý všední den ráno posbírá polední/denní menu z
vybraných restaurací a pošle je e-mailem jako jeden přehledný souhrn.

## Jak to funguje

- `config/restaurants.yaml` – seznam restaurací a jejich "adaptér".
- `scrapers/menubot.py` – adaptér pro restaurace používající widget
  [menubot.cz](https://www.menubot.cz) (velmi rozšířené u českých restaurací –
  FUZE Praha i Han.sik ho oba používají, jen s jiným vzhledem šablony).
- `scrapers/generic_html.py` – záložní adaptér pro restaurace, které mají
  menu přímo ve vlastním HTML (bez widgetu), ovládaný CSS selektory.
- `render.py` – poskládá HTML/text e-mail ze všech restaurací.
- `email_sender.py` – odešle e-mail přes SMTP.
- `main.py` – vše spustí a odešle.
- `.github/workflows/daily-menu.yml` – naplánuje spuštění každý všední den
  v 10:00 (léto) / 9:00 (zima) přes GitHub Actions – běží zadarmo, i když je
  počítač vypnutý.

## Jak přidat další restauraci

**Pokud restaurace používá menubot.cz** (nejčastější případ – zkuste to
první): otevřete stránku s denním menu, zobrazte zdrojový kód (Ctrl+U) a
vyhledejte `menubot.cz/app/users/`. Hash je část za `/users/` a před
`/export` nebo `/images`. Vložte do `config/restaurants.yaml`:

```yaml
  - name: "Nová restaurace"
    url: "https://..."
    adapter: "menubot"
    menubot_hash: "xxxxxxxxxxxxxxxxxxxxxxxxx"
```

**Pokud restaurace menubot.cz nepoužívá**, použijte obecný HTML adaptér a
najděte CSS selektor obalující jednu položku menu (přes DevTools → Inspect):

```yaml
  - name: "Jiná restaurace"
    url: "https://..."
    adapter: "html"
    item_selector: ".menu-item"      # obaluje jednu položku
    name_selector: ".menu-item-name" # název položky (volitelné)
    price_selector: ".menu-item-price" # cena (volitelné)
```

Pokud parsování selže úplně, e-mail pro danou restauraci ukáže alespoň
prvních ~500 znaků surového textu stránky, ať máte vždy nějakou informaci.

## Lokální test

```powershell
git clone <tento repo>
cd obedy-bot
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# jen vypsat do konzole, bez odeslání e-mailu:
python main.py --dry-run

# skutečné odeslání e-mailu (nastavte proměnné prostředí):
$env:SMTP_HOST="smtp.gmail.com"
$env:SMTP_PORT="465"
$env:SMTP_USER="vas@gmail.com"
$env:SMTP_PASSWORD="<app password, ne běžné heslo>"
$env:MAIL_FROM="vas@gmail.com"
$env:MAIL_TO="vas@gmail.com"
python main.py
```

### SMTP nastavení

- **Gmail**: `smtp.gmail.com`, port `465`. Nutné vygenerovat
  [App Password](https://myaccount.google.com/apppasswords) (běžné heslo
  s SMTP nefunguje, pokud máte 2FA).
- **Seznam.cz**: `smtp.seznam.cz`, port `465`, přihlašovací údaje jako do
  webmailu (případně je nutné povolit SMTP přístup v nastavení schránky).

## Nasazení na GitHub Actions (běží zadarmo, denně, i s vypnutým PC)

1. Vytvořte repozitář na GitHubu a nahrajte do něj tento kód:

   ```powershell
   git add .
   git commit -m "Initial obedy-bot setup"
   git remote add origin <URL repozitáře>
   git push -u origin master
   ```

2. V repozitáři: **Settings → Secrets and variables → Actions → New
   repository secret** a vytvořte tyto secrets: `SMTP_HOST`, `SMTP_PORT`,
   `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_TO`.

3. V záložce **Actions** můžete workflow "Daily lunch menu email" spustit
   manuálně (`workflow_dispatch` / tlačítko "Run workflow") a hned zkontrolovat,
   že e-mail dorazí. Jinak se spustí automaticky v 8:00 UTC každý všední den.

## Známá omezení

- Čas cronu je v UTC, takže se čas doručení v Česku posune o hodinu při
  přechodu na letní/zimní čas (max. rozdíl 1 h, pro tento účel není kritické).
- Pokud restaurace změní šablonu svého webu/widgetu, parser pro ni může
  přestat fungovat – v tom případě e-mail zobrazí chybu nebo surový text
  a je potřeba upravit `scrapers/menubot.py` nebo `generic_html.py`.
