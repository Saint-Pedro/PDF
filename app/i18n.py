"""Translations of server messages. Messages are written in English in the code;
``translate`` maps them to the language requested by the UI (X-Lang header)."""
from __future__ import annotations

import re

LANGS = ("en", "fr", "es", "de", "it")

# (English regex, {lang: replacement})
MESSAGES: list[tuple[str, dict[str, str]]] = [
    (r"Add at least one element to the document\.", {
        "fr": "Ajoutez au moins un élément sur le document.", "es": "Añada al menos un elemento al documento.",
        "de": "Fügen Sie dem Dokument mindestens ein Element hinzu.", "it": "Aggiungi almeno un elemento al documento."}),
    (r"No file was produced\.", {"fr": "Aucun fichier produit.", "es": "No se ha generado ningún archivo.", "de": "Es wurde keine Datei erzeugt.", "it": "Nessun file prodotto."}),
    (r"No images found in this PDF\.", {"fr": "Aucune image trouvée dans ce PDF.", "es": "No se encontraron imágenes en este PDF.", "de": "Keine Bilder in diesem PDF gefunden.", "it": "Nessuna immagine trovata in questo PDF."}),
    (r"No matches found\.", {"fr": "Aucune occurrence trouvée.", "es": "No se encontraron coincidencias.", "de": "Keine Treffer gefunden.", "it": "Nessuna corrispondenza trovata."}),
    (r"No pages specified\.", {"fr": "Aucune page indiquée.", "es": "No se indicaron páginas.", "de": "Keine Seiten angegeben.", "it": "Nessuna pagina indicata."}),
    (r"Invalid format\.", {"fr": "Format invalide.", "es": "Formato no válido.", "de": "Ungültiges Format.", "it": "Formato non valido."}),
    (r"Ghostscript is required for PDF/A conversion\.", {"fr": "Ghostscript est nécessaire pour la conversion PDF/A.", "es": "Se necesita Ghostscript para convertir a PDF/A.", "de": "Für die PDF/A-Konvertierung wird Ghostscript benötigt.", "it": "Ghostscript è necessario per la conversione PDF/A."}),
    (r"Unable to read this PDF\.", {"fr": "Impossible de lire ce PDF.", "es": "No se puede leer este PDF.", "de": "Dieses PDF kann nicht gelesen werden.", "it": "Impossibile leggere questo PDF."}),
    (r"You cannot remove every page\.", {"fr": "Impossible de supprimer toutes les pages.", "es": "No puede eliminar todas las páginas.", "de": "Sie können nicht alle Seiten entfernen.", "it": "Non puoi eliminare tutte le pagine."}),
    (r"Enter words to redact or draw areas\.", {"fr": "Indiquez des mots à caviarder ou dessinez des zones.", "es": "Indique palabras que ocultar o dibuje zonas.", "de": "Geben Sie zu schwärzende Wörter ein oder zeichnen Sie Bereiche.", "it": "Indica parole da oscurare o disegna delle aree."}),
    (r"Enter a password\.", {"fr": "Indiquez un mot de passe.", "es": "Introduzca una contraseña.", "de": "Geben Sie ein Passwort ein.", "it": "Inserisci una password."}),
    (r"The resulting document would be empty\.", {"fr": "Le document résultant serait vide.", "es": "El documento resultante estaría vacío.", "de": "Das resultierende Dokument wäre leer.", "it": "Il documento risultante sarebbe vuoto."}),
    (r"The file is too damaged to be repaired\.", {"fr": "Le fichier est trop endommagé pour être réparé.", "es": "El archivo está demasiado dañado para repararlo.", "de": "Die Datei ist zu stark beschädigt, um repariert zu werden.", "it": "Il file è troppo danneggiato per essere riparato."}),
    (r"Passwords do not match\.", {"fr": "Les mots de passe ne correspondent pas.", "es": "Las contraseñas no coinciden.", "de": "Die Passwörter stimmen nicht überein.", "it": "Le password non corrispondono."}),
    (r"LibreOffice produced no file\.", {"fr": "LibreOffice n'a produit aucun fichier.", "es": "LibreOffice no generó ningún archivo.", "de": "LibreOffice hat keine Datei erzeugt.", "it": "LibreOffice non ha prodotto alcun file."}),
    (r"LibreOffice is not installed\.", {"fr": "LibreOffice n'est pas installé.", "es": "LibreOffice no está instalado.", "de": "LibreOffice ist nicht installiert.", "it": "LibreOffice non è installato."}),
    (r"Margins are too large for the page\.", {"fr": "Marges trop grandes pour la page.", "es": "Los márgenes son demasiado grandes para la página.", "de": "Die Ränder sind zu groß für die Seite.", "it": "I margini sono troppo grandi per la pagina."}),
    (r"Admin password required\.", {"fr": "Mot de passe administrateur requis.", "es": "Se requiere la contraseña de administrador.", "de": "Administratorpasswort erforderlich.", "it": "Password di amministratore richiesta."}),
    (r"Incorrect password\.", {"fr": "Mot de passe incorrect.", "es": "Contraseña incorrecta.", "de": "Falsches Passwort.", "it": "Password errata."}),
    (r"OCRmyPDF \(and Tesseract\) must be installed for OCR\.", {"fr": "OCRmyPDF (et Tesseract) doit être installé pour l'OCR.", "es": "Para el OCR hay que instalar OCRmyPDF (y Tesseract).", "de": "Für OCR muss OCRmyPDF (und Tesseract) installiert sein.", "it": "Per l'OCR è necessario installare OCRmyPDF (e Tesseract)."}),
    (r"Invalid options\.", {"fr": "Options invalides.", "es": "Opciones no válidas.", "de": "Ungültige Optionen.", "it": "Opzioni non valide."}),
    (r"Unknown tool\.", {"fr": "Outil inconnu.", "es": "Herramienta desconocida.", "de": "Unbekanntes Werkzeug.", "it": "Strumento sconosciuto."}),
    (r"No file received\.", {"fr": "Aucun fichier reçu.", "es": "No se recibió ningún archivo.", "de": "Keine Datei empfangen.", "it": "Nessun file ricevuto."}),
    (r"Too many files \(max (\d+)\)\.", {"fr": r"Trop de fichiers (max \1).", "es": r"Demasiados archivos (máx. \1).", "de": r"Zu viele Dateien (max. \1).", "it": r"Troppi file (max \1)."}),
    (r"The server is busy, please try again in a moment\.", {"fr": "Le serveur est occupé, réessayez dans un instant.", "es": "El servidor está ocupado, inténtelo de nuevo en un momento.", "de": "Der Server ist ausgelastet, bitte versuchen Sie es gleich noch einmal.", "it": "Il server è occupato, riprova tra un momento."}),
    (r"This job no longer exists \(its files have been deleted\)\.", {"fr": "Ce traitement n'existe plus (ses fichiers ont été supprimés).", "es": "Esta tarea ya no existe (sus archivos se han eliminado).", "de": "Dieser Auftrag existiert nicht mehr (seine Dateien wurden gelöscht).", "it": "Questa elaborazione non esiste più (i suoi file sono stati eliminati)."}),
    (r"File rejected: image too large\.", {"fr": "Fichier refusé : image trop grande.", "es": "Archivo rechazado: imagen demasiado grande.", "de": "Datei abgelehnt: Bild zu groß.", "it": "File rifiutato: immagine troppo grande."}),
    (r'"(.+)" was rejected \(suspicious compressed content\)\.', {"fr": r"« \1 » a été refusé (contenu compressé suspect).", "es": r"«\1» fue rechazado (contenido comprimido sospechoso).", "de": r"„\1“ wurde abgelehnt (verdächtiger komprimierter Inhalt).", "it": r"«\1» è stato rifiutato (contenuto compresso sospetto)."}),
    (r'"(.+)" is corrupted or not a valid document\.', {"fr": r"« \1 » est endommagé ou n'est pas un document valide.", "es": r"«\1» está dañado o no es un documento válido.", "de": r"„\1“ ist beschädigt oder kein gültiges Dokument.", "it": r"«\1» è danneggiato o non è un documento valido."}),
    (r'"(.+)" has too many pages \(max (\d+)\)\.', {"fr": r"« \1 » a trop de pages (max \2).", "es": r"«\1» tiene demasiadas páginas (máx. \2).", "de": r"„\1“ hat zu viele Seiten (max. \2).", "it": r"«\1» ha troppe pagine (max \2)."}),
    (r"Processing took too long and was stopped\.", {"fr": "Le traitement a pris trop de temps et a été arrêté.", "es": "El proceso tardó demasiado y se detuvo.", "de": "Die Verarbeitung hat zu lange gedauert und wurde abgebrochen.", "it": "L'elaborazione ha richiesto troppo tempo ed è stata interrotta."}),
    (r"Unexpected error: the worker stopped\.", {"fr": "Erreur inattendue : le traitement s'est arrêté.", "es": "Error inesperado: el proceso se detuvo.", "de": "Unerwarteter Fehler: die Verarbeitung wurde beendet.", "it": "Errore imprevisto: l'elaborazione si è interrotta."}),
    (r"A Chrome-based browser \(Chrome, Edge, Chromium or Brave\) is required\.", {"fr": "Un navigateur basé sur Chrome (Chrome, Edge, Chromium ou Brave) est nécessaire.", "es": "Se necesita un navegador basado en Chrome (Chrome, Edge, Chromium o Brave).", "de": "Ein Chrome-basierter Browser (Chrome, Edge, Chromium oder Brave) wird benötigt.", "it": "È necessario un browser basato su Chrome (Chrome, Edge, Chromium o Brave)."}),
    (r"The browser could not be started\.", {"fr": "Le navigateur n'a pas pu être lancé.", "es": "No se pudo iniciar el navegador.", "de": "Der Browser konnte nicht gestartet werden.", "it": "Impossibile avviare il browser."}),
    (r"The browser did not respond in time\.", {"fr": "Le navigateur n'a pas répondu à temps.", "es": "El navegador no respondió a tiempo.", "de": "Der Browser hat nicht rechtzeitig geantwortet.", "it": "Il browser non ha risposto in tempo."}),
    (r"Browser connection (failed|closed)\.", {"fr": "Connexion au navigateur interrompue.", "es": "Conexión con el navegador interrumpida.", "de": "Verbindung zum Browser unterbrochen.", "it": "Connessione al browser interrotta."}),
    (r"Unable to open the page \((.*)\)\.", {"fr": r"Impossible d'ouvrir la page (\1).", "es": r"No se puede abrir la página (\1).", "de": r"Die Seite kann nicht geöffnet werden (\1).", "it": r"Impossibile aprire la pagina (\1)."}),
    (r"Enter a web address\.", {"fr": "Indiquez une adresse web.", "es": "Introduzca una dirección web.", "de": "Geben Sie eine Webadresse ein.", "it": "Inserisci un indirizzo web."}),
    (r"Enter a valid web address \(http or https\)\.", {"fr": "Indiquez une adresse web valide (http ou https).", "es": "Introduzca una dirección web válida (http o https).", "de": "Geben Sie eine gültige Webadresse ein (http oder https).", "it": "Inserisci un indirizzo web valido (http o https)."}),
    (r"This tool requires (.+)\.", {"fr": r"Cet outil nécessite \1.", "es": r"Esta herramienta requiere \1.", "de": r"Dieses Werkzeug benötigt \1.", "it": r"Questo strumento richiede \1."}),
    (r"Unexpected error\.", {"fr": "Erreur inattendue.", "es": "Error inesperado.", "de": "Unerwarteter Fehler.", "it": "Errore imprevisto."}),
    (r"Unexpected error: (.*)", {"fr": r"Erreur inattendue : \1", "es": r"Error inesperado: \1", "de": r"Unerwarteter Fehler: \1", "it": r"Errore imprevisto: \1"}),
    (r"File too large \(max (\d+) MB\)\.", {"fr": r"Fichier trop volumineux (max \1 Mo).", "es": r"Archivo demasiado grande (máx. \1 MB).", "de": r"Datei zu groß (max. \1 MB).", "it": r"File troppo grande (max \1 MB)."}),
    (r"Unsupported format: \.(\w+)", {"fr": r"Format .\1 non pris en charge.", "es": r"Formato .\1 no compatible.", "de": r"Nicht unterstütztes Format: .\1", "it": r"Formato .\1 non supportato."}),
    (r"Install LibreOffice to convert \.(\w+) files\.", {"fr": r"Installez LibreOffice pour convertir les fichiers .\1.", "es": r"Instale LibreOffice para convertir archivos .\1.", "de": r"Installieren Sie LibreOffice, um .\1-Dateien zu konvertieren.", "it": r"Installa LibreOffice per convertire i file .\1."}),
    (r'Invalid range: "(.*)"', {"fr": r"Plage invalide : « \1 »", "es": r"Intervalo no válido: «\1»", "de": r"Ungültiger Bereich: „\1“", "it": r"Intervallo non valido: «\1»"}),
    (r'Empty range: "(.*)"', {"fr": r"Plage vide : « \1 »", "es": r"Intervalo vacío: «\1»", "de": r"Leerer Bereich: „\1“", "it": r"Intervallo vuoto: «\1»"}),
    (r'"(.+)" is not a format accepted by this tool\.', {"fr": r"« \1 » n'est pas un format accepté par cet outil.", "es": r"«\1» no es un formato admitido por esta herramienta.", "de": r"„\1“ ist kein von diesem Werkzeug akzeptiertes Format.", "it": r"«\1» non è un formato accettato da questo strumento."}),
    (r'"(.+)" is password-protected\.', {"fr": r"« \1 » est protégé par mot de passe.", "es": r"«\1» está protegido con contraseña.", "de": r"„\1“ ist passwortgeschützt.", "it": r"«\1» è protetto da password."}),
    (r"(\S+) failed: (.*)", {"fr": r"\1 a échoué : \2", "es": r"\1 falló: \2", "de": r"\1 ist fehlgeschlagen: \2", "it": r"\1 non è riuscito: \2"}),
]
_COMPILED = [(re.compile(p, re.S), r) for p, r in MESSAGES]


def translate(msg: str, lang: str | None) -> str:
    lang = (lang or "en").lower()[:2]
    if not msg or lang == "en" or lang not in LANGS:
        return msg
    for rx, reps in _COMPILED:
        if rx.fullmatch(msg) and lang in reps:
            return rx.sub(reps[lang], msg)
    return msg
