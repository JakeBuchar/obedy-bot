# obedy-bot

Malý nástroj, který každý všední den ráno posbírá polední/denní menu z
vybraných restaurací a pošle je e-mailem jako jeden přehledný souhrn.

## Jak to funguje

- `config/praha.yaml` – restaurace pro Prahu (původní seznam).
- `config/kolin.yaml` – restaurace pro Kolín (Vodní svět, Farina, La Musica,
  Arco, Obecní dům, Na Sídlišti 1962, Stoletá).
- `scrapers/menubot.py` – adaptér pro restaurace používající widget
  [menubot.cz](https://www.menubot.cz) (velmi rozšířené u českých restaurací –
  FUZE Praha i Han.sik ho oba používají, jen s jiným vzhledem šablony).
- `scrapers/generic_html.py` – záložní adaptér pro restaurace, které mají
  menu přímo ve vlastním HTML (bez widgetu), ovládaný CSS selektory.
- `render.py` – poskládá HTML/text e-mail ze všech restaurací.
- `logos.py` – stáhne loga restaurací, převede je na PNG a přiloží je do
  e-mailu (Outlook neumí WebP ani ICO, ve kterých je některé weby mají).
- `email_sender.py` – odešle e-mail přes SMTP.
- `main.py` – vše spustí a odešle.
- `.github/workflows/daily-menu.yml` – Praha.
- `.github/workflows/daily-menu-kolin.yml` – Kolín.

Obě města běží ze stejného kódu. Liší se jen YAML, příjemce (`MAIL_TO` /
`MAIL_TO_KOLIN`) a předmět e-mailu.

## Jak přidat další restauraci

**Pokud restaurace používá menubot.cz** (nejčastější případ – zkuste to
první): otevřete stránku s denním menu, zobrazte zdrojový kód (Ctrl+U) a
vyhledejte `menubot.cz/app/users/`. Hash je část za `/users/` a před
`/export` nebo `/images`. Vložte do `config/praha.yaml` (Praha) nebo
`config/kolin.yaml` (Kolín):

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

# jen vypsat text do konzole + přepsat email_preview.html (bez odeslání):
python main.py --dry-run
# pak otevřete email_preview.html v prohlížeči (dvojklik / Open with)

# totéž pro Kolín:
$env:CONFIG_PATH="config/kolin.yaml"
$env:CITY="Kolín"
python main.py --dry-run

# totéž co --dry-run, navíc otevře email_preview.html v prohlížeči:
python main.py --preview

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
   `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_TO`. Pro Kolín přidejte
   ještě `MAIL_TO_KOLIN` (příjemci kolínského e-mailu; SMTP může zůstat
   stejné).

3. V záložce **Actions** můžete workflow "Daily lunch menu email" spustit
   manuálně (`workflow_dispatch` / tlačítko "Run workflow") a hned zkontrolovat,
   že e-mail dorazí. Jinak se e-mail odesílá automaticky každý všední den
   ráno.

   **Proč čas doručení neřídí cron:** cron v GitHub Actions se ukázal jako
   nepoužitelný. GitHub garantuje jen to, že běh spustí *nejdřív* v zadaný
   čas, a od 27. 8. 2026 startují naplánované běhy o **3,5 až 12 hodin
   později** – první odeslání dne padlo mezi 13:43 a 15:02, tedy po obědě.
   27. 8. se crony nespustily vůbec a e-mail nepřišel. Naproti tomu běh
   spuštěný přes API (`workflow_dispatch`) startuje během několika sekund.

   Doručení proto řídí **externí plánovač**, který workflow spustí přes
   API (návod níže). Žádné z obou workflow už cron nemá – jako záchranná
   brzda stejně doručoval až po obědě a 10. 9. 2026 poslal navíc druhý
   e-mail ve 13:50: ranní odeslání toho dne skončilo červeně kvůli dvěma
   nedostupným webům, takže se nepočítalo jako „už odesláno“. Když externí
   spouštění vypadne, spusťte workflow ručně v Actions.

   **Aby nepřišlo víc e-mailů najednou:** běh spuštěný plánovačem se nejdřív
   zeptá Actions API, jestli dnes už nějaký běh **úspěšně** proběhl (viz
   `already_sent.py`); pokud ano, během pár sekund skončí. Pozor, že běh
   ukončený červeně se za odeslaný nepovažuje, i když e-mail odešel. Ruční
   spuštění tlačítkem pošle vždycky.

### Externí spouštění (hlavní cesta doručení)

1. **Vytvořte token**: GitHub → Settings → Developer settings → Personal
   access tokens → **Fine-grained tokens** → Generate new token. Repository
   access omezte na `obedy-bot`, v Permissions dejte **Actions: Read and
   write**. Nic víc token neumožní – s kódem v repozitáři nemůže hýbat.

2. **Otestujte spuštění** (nahraďte `<TOKEN>`):

   ```bash
   curl -X POST \
     -H "Accept: application/vnd.github+json" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "X-GitHub-Api-Version: 2022-11-28" \
     https://api.github.com/repos/JakeBuchar/obedy-bot/actions/workflows/daily-menu.yml/dispatches \
     -d '{"ref":"master","inputs":{"skip_if_sent":"true"}}'
   ```

   Odpověď `204 No Content` znamená úspěch – běh naskočí v Actions během
   pár sekund. `skip_if_sent: "true"` zajistí, že opakované zavolání
   (retry plánovače) už druhý e-mail nepošle.

3. **Naplánujte to** v jakékoli službě, která umí poslat POST s hlavičkami
   – např. [cron-job.org](https://cron-job.org) (zdarma, umí custom headers
   i tělo požadavku) nebo Google Apps Script s time-driven triggerem:

   ```javascript
   function sendMenu() {
     UrlFetchApp.fetch(
       "https://api.github.com/repos/JakeBuchar/obedy-bot/actions/workflows/daily-menu.yml/dispatches",
       {
         method: "post",
         headers: {
           Authorization: "Bearer " + PropertiesService.getScriptProperties().getProperty("GH_TOKEN"),
           Accept: "application/vnd.github+json",
         },
         payload: JSON.stringify({ ref: "master", inputs: { skip_if_sent: "true" } }),
         contentType: "application/json",
       },
     );
   }
   ```

   Stejný skript, druhá funkce pro Kolín (stejný `GH_TOKEN`, jiné workflow):

   ```javascript
   function sendMenuKolin() {
     UrlFetchApp.fetch(
       "https://api.github.com/repos/JakeBuchar/obedy-bot/actions/workflows/daily-menu-kolin.yml/dispatches",
       {
         method: "post",
         headers: {
           Authorization: "Bearer " + PropertiesService.getScriptProperties().getProperty("GH_TOKEN"),
           Accept: "application/vnd.github+json",
         },
         payload: JSON.stringify({ ref: "master", inputs: { skip_if_sent: "true" } }),
         contentType: "application/json",
       },
     );
   }
   ```

   Stejné triggery Po–Pá, tentokrát na `sendMenuKolin`. Secret `MAIL_TO_KOLIN`
   musí existovat a `config/kolin.yaml` nesmí být prázdný, jinak běh skončí
   chybou a nic neodešle.

   Čas nastavte na požadovanou hodinu v zóně Europe/Prague, po–pá. Plánovač
   běží mimo GitHub, takže se ho zpoždění Actions netýká.

   Když se e-mail nepodaří odeslat (SMTP, chybějící secrets) nebo když
   u některé restaurace scrapování spadne, workflow skončí červeně, i
   když zbytek menu v e-mailu odejde. GitHub pak pošle notifikaci o
   failed runu (Settings → Notifications → Actions).

## Známá omezení

- Pokud restaurace změní šablonu svého webu/widgetu, parser pro ni může
  přestat fungovat – v tom případě e-mail zobrazí chybu nebo surový text
  a je potřeba upravit `scrapers/menubot.py` nebo `generic_html.py`.
